"""Sensoren je Zähler: Periode, Ablesung, Tageswerte (0.5) und Ergebnis (0.6: Kosten, Abschläge, Prognose, Saldo,
Urteil, empfohlener Abschlag, Qualität, Kennwert). Dazu der Gesamtsaldo am Gerät "Haushalt".
Aktualisierung über das Dispatcher-Signal des Coordinators.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import TarifConfigEntry
from .const import DOMAIN, VERSION, signal_updated
from .engine.consumption import latest_reading
from .engine.balance import MeterResult
from .engine.model import Medium, Meter
from .engine.regression import ModelQuality
from .engine.quality import Quality, usable
from .runtime import TarifRuntime


async def async_setup_entry(hass: HomeAssistant, entry: TarifConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    rt = entry.runtime_data
    async_add_entities([TotalSaldoSensor(rt)])
    for meter in rt.meters.values():
        classes: list[type[TarifSensor]] = [PeriodEndSensor, LastReadingSensor, MeterValueSensor, DailyQualitySensor]
        if meter.role == "main" or rt.contracts(meter.meter_id):
            classes += [CostSoFarSensor, AdvancesPaidSensor, CurrentAdvanceSensor, AdvancesPeriodSensor, ForecastConsumptionSensor, ForecastCostSensor,
                        SaldoSensor, VerdictSensor, RecommendedAdvanceSensor, ForecastQualitySensor]
            if meter.medium in HEAT:
                classes += [HeatCoefficientSensor, HotWaterSensor]
        async_add_entities([cls(rt, meter) for cls in classes], config_subentry_id=meter.meter_id)


class TarifSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    key: str = ""

    def __init__(self, rt: TarifRuntime, meter: Meter) -> None:
        self.rt = rt
        self.meter = meter
        self._attr_translation_key = self.key
        self._attr_unique_id = f"{meter.meter_id}_{self.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.meter_id)},
            name=meter.name or meter.meter_id,
            manufacturer="Tarif-Cockpit",
            model=f"Zähler {meter.medium.value}",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._update()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, signal_updated(self.rt.entry.entry_id), self._refresh))
        self.async_on_remove(async_track_time_change(self.hass, self._refresh, hour=0, minute=1, second=0))

    @callback
    def _refresh(self, *_: Any) -> None:
        self._update()
        self.async_write_ha_state()

    def _update(self) -> None:
        raise NotImplementedError


class PeriodEndSensor(TarifSensor):
    """Ende der laufenden Abrechnungsperiode; Attribute beschreiben Periode und Vertrag."""

    key = "periode_ende"
    _attr_device_class = SensorDeviceClass.DATE

    def _update(self) -> None:
        spec = self.rt.current_period(self.meter.meter_id)
        if spec is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        contract = next((c for c in self.rt.data.contracts if c.contract_id == spec.contract_id), None)
        stored = self.rt.stored_period(spec.period_id)
        today = self.rt.today()
        status = stored.status.value if stored else ("open" if today <= spec.end_date else "closing")
        self._attr_native_value = spec.end_date
        self._attr_extra_state_attributes = {
            "beginn": spec.start_date.isoformat(),
            "rumpfjahr": spec.is_partial,
            "schlussperiode": spec.is_final,
            "status": status,
            "periode_id": spec.period_id,
            "regel": contract.billing_rule.value if contract else None,
            "stichtag": contract.fixed_day if contract else None,
            "lieferant": contract.supplier if contract else None,
            "tarif": contract.tariff if contract else None,
            "tage_bis_ende": (spec.end_date - today).days,
        }


class LastReadingSensor(TarifSensor):
    key = "letzte_ablesung"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def _update(self) -> None:
        r = latest_reading(self.rt.data.readings, self.meter.meter_id)
        self._attr_native_value = r.timestamp if r else None
        self._attr_extra_state_attributes = (
            {"stand": r.value, "qualitaet": r.quality.value, "quelle": r.source.value, "ablesung_id": r.reading_id, "notiz": r.note}
            if r else {}
        )


class MeterValueSensor(TarifSensor):
    """Letzter gültiger abgelesener Stand (bei Zählern mit Sensor zeigt der Sensor selbst den aktuellen Stand)."""

    key = "zaehlerstand"

    def _update(self) -> None:
        r = latest_reading(self.rt.data.readings, self.meter.meter_id)
        self._attr_native_unit_of_measurement = self.meter.unit
        self._attr_native_value = r.value if r else None
        self._attr_extra_state_attributes = {"zeitpunkt": r.timestamp.isoformat(), "qualitaet": r.quality.value} if r else {}


class DailyQualitySensor(TarifSensor):
    """Diagnose: Anteil verwendbarer Tageswerte der letzten 30 Tage, mit Anzahl je Qualität."""

    key = "tageswerte_qualitaet"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE

    def _update(self) -> None:
        today = self.rt.today()
        days = [today - timedelta(days=i) for i in range(1, 31)]
        chain = self.rt.contracts(self.meter.meter_id)
        if chain:
            days = [d for d in days if d >= chain[0].start_date]
        daily = self.rt.daily(self.meter.meter_id)
        counts: dict[str, int] = {q.value: 0 for q in Quality}
        for d in days:
            dv = daily.get(d)
            counts[(dv.quality if dv else Quality.MISSING).value] += 1
        good = sum(n for q, n in counts.items() if usable(q))
        self._attr_native_value = round(100 * good / len(days)) if days else None
        self._attr_extra_state_attributes = {"tage": len(days), **{k: v for k, v in counts.items() if v}}


# ---------------------------------------------------------------- Ergebnis-Sensoren (0.6)

HEAT = (Medium.GAS, Medium.FERNWAERME)
VERDICTS = ["passt", "rueckzahlung", "nachzahlung"]
QUALITIES = [q.value for q in ModelQuality]


class ResultSensor(TarifSensor):
    """Sensor aus dem Ergebnis des Coordinators (MeterResult). ``value(res)`` liefert den Zustand."""

    money = False

    def __init__(self, rt: TarifRuntime, meter: Meter) -> None:
        if self.money:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = rt.hass.config.currency
            self._attr_suggested_display_precision = 2
        super().__init__(rt, meter)

    def _result(self) -> MeterResult | None:
        coord = self.rt.coordinator
        return coord.results.get(self.meter.meter_id) if coord is not None else None

    def value(self, res: MeterResult) -> Any:
        raise NotImplementedError

    def _update(self) -> None:
        res = self._result()
        self._attr_native_value = None if res is None else self.value(res)
        self._attr_extra_state_attributes = {} if res is None else self.attributes(res)

    def attributes(self, res: MeterResult) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if res.period is not None:
            attrs["periode_beginn"] = res.period.start_date.isoformat()
            attrs["periode_ende"] = res.period.end_date.isoformat()
        if res.contract is not None:
            attrs["lieferant"] = res.contract.supplier
        if res.forecast is not None:
            attrs["prognose_qualitaet"] = res.forecast.quality.value
            attrs["prognose_methode"] = res.forecast.method
        if res.flags:
            attrs["hinweise"] = res.flags
        return attrs


class CostSoFarSensor(ResultSensor):
    key = "kosten_bisher"
    money = True

    def value(self, res):
        return res.balance.actual_cost if res.balance else None

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.actual is not None:
            attrs.update({"arbeitspreis_anteil": res.actual.energy, "grundpreis_anteil": round(res.actual.base, 2),
                          "abwasser_anteil": res.actual.wastewater, "menge": res.actual.quantity})
        if res.consumption is not None:
            attrs.update({"verbrauch_bisher": res.consumption.used, "startwert": res.consumption.start_value,
                          "bekannt_bis": res.consumption.known_until.isoformat() if res.consumption.known_until else None})
        return attrs


class AdvancesPaidSensor(ResultSensor):
    key = "abschlaege_bisher"
    money = True

    def value(self, res):
        return res.payments.paid_to_date if res.payments else None


class CurrentAdvanceSensor(ResultSensor):
    """Aktueller Abschlag je Zahltag (für die Karte im Sensor-Modus: Abschlag × Anzahl)."""

    key = "abschlag"
    money = True

    def value(self, res):
        if res.payments is None or not res.payments.installments:
            return None
        today = dt_util.now(self.rt.tz).date()
        nxt = next((i for i in res.payments.installments if i.date > today and i.status != "storniert"), None)
        last = next((i for i in reversed(res.payments.installments) if i.status != "storniert"), None)
        return (nxt or last).amount if (nxt or last) else None

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.payments is not None:
            attrs["anzahl_je_periode"] = res.payments.per_period
        return attrs


class AdvancesPeriodSensor(ResultSensor):
    key = "abschlaege_periode"
    money = True

    def value(self, res):
        return res.payments.period_total if res.payments else None

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.payments is not None:
            attrs["anzahl"] = res.payments.per_period
            attrs["abschlaege"] = [{"datum": i.date.isoformat(), "betrag": i.amount, "status": i.status} for i in res.payments.installments]
        return attrs


class ForecastConsumptionSensor(ResultSensor):
    key = "prognose_verbrauch"

    def __init__(self, rt: TarifRuntime, meter: Meter) -> None:
        if meter.medium == Medium.WASSER:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        else:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 0
        super().__init__(rt, meter)

    def value(self, res):
        return res.forecast_total

    def attributes(self, res):
        attrs = super().attributes(res)
        attrs["verbrauch_bisher"] = res.used_billing
        if res.forecast is not None:
            attrs["rest"] = res.forecast.rest
            attrs.update({k: v for k, v in res.forecast.details.items() if not isinstance(v, (list, dict))})
        return attrs


class ForecastCostSensor(ResultSensor):
    key = "prognose_kosten"
    money = True

    def value(self, res):
        return res.balance.forecast_cost if res.balance else None


class SaldoSensor(ResultSensor):
    key = "saldo"
    money = True

    def value(self, res):
        return res.balance.saldo if res.balance else None


class VerdictSensor(ResultSensor):
    key = "urteil"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = VERDICTS

    def value(self, res):
        return res.balance.verdict if res.balance else None

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.balance is not None:
            attrs.update({"saldo": res.balance.saldo, "abschlag_passend": res.balance.fitting_advance,
                          "toleranz_pct": self.rt.household.tolerance_pct})
        return attrs


class RecommendedAdvanceSensor(ResultSensor):
    key = "abschlag_empfohlen"
    money = True

    def value(self, res):
        return res.balance.recommended_advance if res.balance else None

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.balance is not None:
            attrs.update({"ab": res.balance.next_pay_date.isoformat() if res.balance.next_pay_date else None,
                          "offene_abschlaege": res.balance.remaining_installments,
                          "abschlag_passend": res.balance.fitting_advance,
                          "vorlaeufig": res.forecast is not None and res.forecast.quality not in (ModelQuality.GOOD, ModelQuality.VERY_GOOD)})
        return attrs


class ForecastQualitySensor(ResultSensor):
    key = "prognose_qualitaet"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = QUALITIES
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def value(self, res):
        return res.forecast.quality.value if res.forecast else ModelQuality.INSUFFICIENT.value

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.heat_model is not None:
            attrs.update(res.heat_model.as_dict())
        return attrs


class HeatCoefficientSensor(ResultSensor):
    key = "kennwert"
    _attr_native_unit_of_measurement = "kWh/Kd"
    _attr_suggested_display_precision = 2

    def value(self, res):
        m = res.heat_model
        return round(m.heat_coefficient, 3) if m is not None and m.usable else None

    def attributes(self, res):
        return res.heat_model.as_dict() if res.heat_model is not None else {}


class HotWaterSensor(ResultSensor):
    key = "ww_grundlast"
    _attr_native_unit_of_measurement = "kWh/d"
    _attr_suggested_display_precision = 1

    def value(self, res):
        m = res.heat_model
        return round(m.hot_water_baseload, 3) if m is not None and m.usable else None


class TotalSaldoSensor(SensorEntity):
    """Saldo über alle Zähler (Gerät "Haushalt")."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "saldo_gesamt"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2

    def __init__(self, rt: TarifRuntime) -> None:
        self.rt = rt
        self._attr_unique_id = f"{rt.entry.entry_id}_saldo_gesamt"
        self._attr_native_unit_of_measurement = rt.hass.config.currency
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, rt.entry.entry_id)}, name=rt.household.name, manufacturer="Tarif-Cockpit",
            model="Haushalt", sw_version=VERSION, entry_type=DeviceEntryType.SERVICE,
        )
        self._update()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, signal_updated(self.rt.entry.entry_id), self._refresh))

    @callback
    def _refresh(self, *_: Any) -> None:
        self._update()
        self.async_write_ha_state()

    def _update(self) -> None:
        coord = self.rt.coordinator
        results = list(coord.results.items()) if coord is not None else []
        parts = {self.rt.meters[mid].name or mid: r.balance.saldo for mid, r in results if r.balance and r.balance.saldo is not None}
        missing = [self.rt.meters[mid].name or mid for mid, r in results if not (r.balance and r.balance.saldo is not None)]
        # Unvollständig ist keine Summe: fehlt ein Zähler, gibt es keinen Gesamtsaldo (Regel 10)
        self._attr_native_value = round(sum(parts.values()), 2) if parts and not missing else None
        self._attr_extra_state_attributes = {"zaehler": parts, "ohne_prognose": missing, "vollstaendig": not missing}
