"""Sensoren je Zähler: Periode, Ablesung, Tageswerte (0.5) und Ergebnis (0.6: Kosten, Abschläge, Prognose, Saldo,
Urteil, empfohlener Abschlag, Qualität, Kennwert). Dazu der Gesamtsaldo am Gerät "Haushalt" und je Wärmeerzeuger
(0.8) eingesetzte Energie, Wärme, Entlastung, Betriebsstunden/-tage, beim Kaminofen Holz und Holzkosten (geschätzt).
Aktualisierung über das Dispatcher-Signal des Coordinators.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfPower, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import TarifConfigEntry
from .const import DOMAIN, VERSION, signal_updated
from .engine import billing

NOTICE_HINT_DAYS = 42  # Hinweis in der Karte ab sechs Wochen vor dem letzten Kündigungstag
from .engine.consumption import latest_reading
from .engine.balance import MeterResult
from .engine.generators import GeneratorResult
from .engine.model import GeneratorKind, HeatGenerator, Medium, Meter
from .engine.regression import ModelQuality
from .engine.quality import Quality, usable
from .runtime import TarifRuntime


async def async_setup_entry(hass: HomeAssistant, entry: TarifConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    rt = entry.runtime_data
    async_add_entities([TotalSaldoSensor(rt)])
    for meter in rt.meters.values():
        classes: list[type[TarifSensor]] = [PeriodEndSensor, LastReadingSensor, MeterValueSensor, DailyQualitySensor]
        if meter.entity:
            classes.append(ReconcileSensor)
        if meter.entity and meter.pulse_constant and meter.medium == Medium.GAS:
            classes += [GasPowerSensor, BurnerHoursSensor, BurnerStartsSensor]
        if meter.role == "main" or rt.contracts(meter.meter_id):
            classes += [CostSoFarSensor, AdvancesPaidSensor, CurrentAdvanceSensor, AdvancesPeriodSensor, ForecastConsumptionSensor, ForecastCostSensor,
                        SaldoSensor, VerdictSensor, RecommendedAdvanceSensor, ForecastQualitySensor]
            # 1.2: Zeitfenster, dynamischer Tarif, Vergleich (Sensoren nur, wenn eingerichtet; Änderung lädt neu)
            kinds = rt.price_kinds(meter.meter_id)
            if "windows" in kinds:
                classes.append(WindowUsageSensor)
            if "dynamic" in kinds:
                classes.append(MeanPriceSensor)
            if meter.comparison is not None:
                classes.append(ComparisonSensor)
            if meter.medium in HEAT:
                classes += [HeatCoefficientSensor, HotWaterSensor, IndoorCoefficientSensor]
            elif meter.medium == Medium.STROM and _heats_with_power(rt, meter):
                classes += [HeatCoefficientSensor]  # kWh Strom je Gradtag (Wärmepumpe, Split-Klima)
        async_add_entities([cls(rt, meter) for cls in classes], config_subentry_id=meter.meter_id)
    for gen in rt.generators.values():
        gclasses: list[type[GeneratorSensor]] = [GenInputSensor, GenHeatSensor, GenAvoidedSensor, GenHoursSensor, GenDaysSensor]
        if gen.kind == GeneratorKind.FIREPLACE:
            gclasses += [GenWoodSensor, GenWoodCostSensor, GenStovePowerSensor]
        if gen.kind in (GeneratorKind.GAS_BOILER, GeneratorKind.DISTRICT_HEATING):
            gclasses.append(HeatLoadSensor)  # 1.1
        async_add_entities([cls(rt, gen) for cls in gclasses], config_subentry_id=gen.generator_id)


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
        current = billing.contract_on(self.rt.contracts(self.meter.meter_id), today)
        if current is not None:
            deadline, end, kind = billing.notice_deadline(current, today)
            self._attr_extra_state_attributes.update({
                "kuendigung_bis": deadline.isoformat() if deadline else None,
                "tage_bis_kuendigung": (deadline - today).days if deadline else None,
                "kuendigung_hinweis": bool(deadline and 0 <= (deadline - today).days < NOTICE_HINT_DAYS),
                "vertragsende": end.isoformat() if end else None,
                "kuendigung": kind,
            })


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

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.balance is not None and res.balance.forecast_cost_cold is not None:
            attrs.update(kalt=res.balance.forecast_cost_cold, warm=res.balance.forecast_cost_warm)
        return attrs


class SaldoSensor(ResultSensor):
    key = "saldo"
    money = True

    def value(self, res):
        return res.balance.saldo if res.balance else None

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.balance is not None and res.balance.saldo_cold is not None:
            attrs.update(saldo_kalt=res.balance.saldo_cold, saldo_warm=res.balance.saldo_warm)
        return attrs


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
        coord = self.rt.coordinator
        if coord is not None:
            # 1.1: Prognosegüte über die abgeschlossenen Perioden und der Vergleich mit der letzten Rechnung
            acc = coord.accuracy.get(self.meter.meter_id)
            if acc and acc.get("perioden"):
                attrs["prognoseguete"] = acc
            checks = coord.invoice_checks.get(self.meter.meter_id) or []
            if checks:
                attrs["rechnung_letzte"] = checks[-1].as_dict()
        return attrs


class HeatCoefficientSensor(ResultSensor):
    key = "kennwert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "kWh/Kd"
    _attr_suggested_display_precision = 2

    def value(self, res):
        m = res.heat_model or res.power_heat_model
        return round(m.heat_coefficient, 3) if m is not None and m.usable else None

    def attributes(self, res):
        m = res.heat_model or res.power_heat_model
        return m.as_dict() if m is not None else {}


class HotWaterSensor(ResultSensor):
    key = "ww_grundlast"
    _attr_state_class = SensorStateClass.MEASUREMENT
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



class IndoorCoefficientSensor(ResultSensor):
    """Kennwert temperaturbereinigt: Gradtage aus der gemessenen Innentemperatur; Attribute %/K und Aufteilung zum Vorjahr."""

    key = "kennwert_temperaturbereinigt"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "kWh/Kd"
    _attr_suggested_display_precision = 2

    def value(self, res):
        m = res.heat_model
        return round(m.heat_coefficient_indoor, 3) if m is not None and m.heat_coefficient_indoor is not None else None

    def attributes(self, res):
        m = res.heat_model
        if m is None:
            return {}
        attrs = {
            "qualitaet": m.indoor_confidence.value if m.indoor_confidence else None,
            "prozent_je_kelvin": None if m.indoor_pct_per_k is None else round(m.indoor_pct_per_k, 2),
            "prozent_je_kelvin_qualitaet": m.indoor_pct_quality.value if m.indoor_pct_quality else None,
            "innentemperatur_mittel": None if m.indoor_mean is None else round(m.indoor_mean, 2),
        }
        if res.indoor_split:
            attrs["vorjahr"] = res.indoor_split
        return attrs


# ---------------------------------------------------------------- Wärmeerzeuger (0.8)

GEN_MODELS = {
    GeneratorKind.GAS_BOILER: "Gastherme", GeneratorKind.AIR_AIR_HP: "Split-Klima / Luft-Luft-Wärmepumpe",
    GeneratorKind.WATER_HP: "Wärmepumpe", GeneratorKind.DISTRICT_HEATING: "Fernwärme", GeneratorKind.FIREPLACE: "Kaminofen",
    GeneratorKind.ELECTRIC: "Elektroheizung",
}


class GeneratorSensor(SensorEntity):
    """Sensor je Wärmeerzeuger (eigenes Gerät). Werte der laufenden Periode bis gestern, aus dem Coordinator."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    key: str = ""

    def __init__(self, rt: TarifRuntime, gen: HeatGenerator) -> None:
        self.rt = rt
        self.gen = gen
        self._attr_translation_key = self.key
        self._attr_unique_id = f"{gen.generator_id}_{self.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gen.generator_id)},
            name=gen.name or GEN_MODELS.get(gen.kind, gen.kind.value),
            manufacturer="Tarif-Cockpit",
            model=f"Wärmeerzeuger {GEN_MODELS.get(gen.kind, gen.kind.value)}",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._update()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, signal_updated(self.rt.entry.entry_id), self._refresh))

    @callback
    def _refresh(self, *_: Any) -> None:
        self._update()
        self.async_write_ha_state()

    def _result(self) -> GeneratorResult | None:
        coord = self.rt.coordinator
        return coord.gen_results.get(self.gen.generator_id) if coord is not None else None

    def value(self, res: GeneratorResult) -> Any:
        raise NotImplementedError

    def attributes(self, res: GeneratorResult) -> dict[str, Any]:
        attrs: dict[str, Any] = {"messqualitaet": res.measurement_quality.value, "tage_mit_daten": res.days_with_data,
                                 "tage": res.days_total}
        if res.flags:
            attrs["hinweise"] = res.flags
        return attrs

    def _update(self) -> None:
        res = self._result()
        self._attr_native_value = None if res is None else self.value(res)
        self._attr_extra_state_attributes = {} if res is None else self.attributes(res)


class _GenEnergy(GeneratorSensor):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 0


class GenInputSensor(_GenEnergy):
    key = "energie_eingang"

    def value(self, res):
        return res.energy_input


class GenHeatSensor(_GenEnergy):
    """Wärme: gemessen (Wärmemengenzähler), sonst geschätzt (Attribut ``geschaetzt``)."""

    key = "waerme"

    def value(self, res):
        return res.thermal_output if res.thermal_output is not None else res.estimated_thermal_output

    def attributes(self, res):
        return {**super().attributes(res), "geschaetzt": res.thermal_output is None and res.estimated_thermal_output is not None}


class GenAvoidedSensor(_GenEnergy):
    """Entlastung des Wärmezählers; leer, solange sie nicht gelernt ist (Kaminofen: vorher Annahme, so gekennzeichnet)."""

    key = "entlastung"

    def value(self, res):
        return res.avoided_energy

    def attributes(self, res):
        return {**super().attributes(res), "qualitaet": res.avoided_quality}


class GenHoursSensor(GeneratorSensor):
    key = "betriebsstunden"
    _attr_native_unit_of_measurement = "h"
    _attr_suggested_display_precision = 1

    def value(self, res):
        return res.hours


class GenDaysSensor(GeneratorSensor):
    key = "betriebstage"
    _attr_native_unit_of_measurement = "d"

    def value(self, res):
        return res.days_on if res.hours is not None else None


class GenWoodSensor(GeneratorSensor):
    key = "holz_geschaetzt"
    _attr_native_unit_of_measurement = "kg"
    _attr_suggested_display_precision = 0

    def value(self, res):
        return res.wood_kg

    def attributes(self, res):
        attrs = {**super().attributes(res), "annahme": "Eingesetzte Energie ÷ 4,2 kWh/kg"}
        if res.wood_days or res.wood_rate:
            # 1.2.2: gewogene Tage zählen mit ihrer Menge, die übrigen mit der gelernten Menge je Brennstunde
            attrs.update({"gewogen_kg": res.wood_weighed_kg, "tage_gewogen": res.wood_days,
                          "rate_qualitaet": res.wood_rate.quality if res.wood_rate else None,
                          "annahme": ("Gewogene Tage: gewogene Menge; übrige Tage: Brennstunden × gelernte kg je Brennstunde"
                                      if res.wood_rate else "Gewogene Tage: gewogene Menge; übrige Tage: Brennstunden × Nennleistung")})
        return attrs


class GenWoodCostSensor(GeneratorSensor):
    key = "holzkosten_geschaetzt"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2

    def __init__(self, rt: TarifRuntime, gen: HeatGenerator) -> None:
        self._attr_native_unit_of_measurement = rt.hass.config.currency
        super().__init__(rt, gen)

    def value(self, res):
        return res.wood_cost


class GenStovePowerSensor(GeneratorSensor):
    """Kaminofen (1.2.2): aus gewogenem Holz gelernte Wärme je Brennstunde (kW). Ohne genug gewogene Tage unbekannt."""

    key = "ofenleistung"
    _attr_native_unit_of_measurement = "kW"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_suggested_display_precision = 1

    def value(self, res):
        return res.wood_rate.heat_kw if res.wood_rate else None

    def attributes(self, res):
        r = res.wood_rate
        attrs = {"tage_gewogen_gesamt": len(self.rt.wood(self.gen.generator_id)), "nennleistung_kw": self.gen.nominal_kw,
                 "annahme": "kg je Brennstunde × 4,2 kWh/kg × Wirkungsgrad"}
        if r is not None:
            attrs.update({"kg_je_brennstunde": r.kg_per_hour, "tage": r.days, "brennstunden": r.hours, "kg": r.kg, "qualitaet": r.quality})
        return attrs



def _heats_with_power(rt: TarifRuntime, meter: Meter) -> bool:
    """Strom-Hauptzähler, an dem eine Wärmepumpe/ein Split-Klima hängt (eigener Zähler oder Haushaltsstrom)."""
    if meter.role != "main":
        return False
    kinds = (GeneratorKind.AIR_AIR_HP, GeneratorKind.WATER_HP, GeneratorKind.ELECTRIC)
    gens = [g for g in rt.generators.values() if g.kind in kinds]
    if any(g.meter_id == meter.meter_id for g in gens):
        return True
    # Haushaltsstrom: nur der Strom-Hauptzähler, den der Coordinator dafür nimmt
    main = rt.coordinator.main_power_id() if rt.coordinator is not None else None
    return meter.meter_id == main and any(g.on_household_power for g in gens)



# ---------------------------------------------------------------- Abgleich und Impulse (0.9)


class ReconcileSensor(TarifSensor):
    """Abgleich des Zähler-Sensors mit den Ablesungen: Abweichung des letzten Intervalls in % (negativ: Sensor zählt zu
    wenig, z. B. verlorene Impulse). Attribute: Faktor, Offset, fehlende Menge, Intervalle."""

    key = "abgleich"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 1

    def _update(self) -> None:
        coord = self.rt.coordinator
        rec = coord.reconciliations.get(self.meter.meter_id) if coord is not None else None
        last = rec.last if rec is not None else None
        self._attr_native_value = last.deviation_pct if last is not None else None
        if rec is None:
            self._attr_extra_state_attributes = {}
            return
        tz = self.rt.tz
        self._attr_extra_state_attributes = {
            "faktor": None if last is None or last.factor is None else round(last.factor, 4),
            "fehlende_menge": None if last is None else last.missing,
            "angeglichen": bool(last and last.applied),
            "hinweis": rec.notice,
            "offset": rec.offset,
            "faktor_median": rec.factor_median,
            "letzte_ablesung": rec.last_reading.timestamp.isoformat() if rec.last_reading else None,
            "intervalle": [
                {"von": i.start.astimezone(tz).date().isoformat(), "bis": i.end.astimezone(tz).date().isoformat(), "abgelesen": i.read,
                 "gemessen": i.measured, "abweichung": i.deviation_pct, "angeglichen": i.applied, "hinweise": i.flags}
                for i in rec.intervals[-5:]
            ],
        }


class GasPowerSensor(TarifSensor):
    """Momentanleistung aus den Impulsen (m³/h × Brennwert × Zustandszahl); 0, wenn einige Minuten kein Impuls kam."""

    key = "gasleistung"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "kW"
    _attr_suggested_display_precision = 1

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        from homeassistant.helpers.event import async_track_time_interval  # noqa: PLC0415

        self.async_on_remove(async_track_time_interval(self.hass, self._refresh, timedelta(minutes=1)))

    def _update(self) -> None:
        coord = self.rt.coordinator
        self._attr_native_value = coord.gas_power(self.meter.meter_id) if coord is not None else None


class _BurnerSensor(TarifSensor):
    """Summe der laufenden Periode aus den Tageswerten (nur Tage mit Impuls-Verlauf)."""

    attr = "heating_hours"

    def _update(self) -> None:
        spec = self.rt.current_period(self.meter.meter_id)
        daily = self.rt.daily(self.meter.meter_id)
        today = self.rt.today()
        first = spec.start_date if spec else today.replace(day=1)
        vals = [(d, v) for d, v in daily.items() if first <= d < today and getattr(v, self.attr) is not None]
        self._attr_native_value = round(sum(getattr(v, self.attr) for _, v in vals), 1) if vals else None
        cycling = sorted(d.isoformat() for d, v in daily.items() if v.cycling and d >= today - timedelta(days=30))
        last = daily.get(today - timedelta(days=1))
        self._attr_extra_state_attributes = {
            "tage_mit_daten": len(vals), "gestern": getattr(last, self.attr) if last else None,
            "taktet_tage": cycling, "taktet_gestern": bool(last and last.cycling),
        }


class BurnerHoursSensor(_BurnerSensor):
    key = "brennerlaufzeit"
    attr = "heating_hours"
    _attr_native_unit_of_measurement = "h"


class BurnerStartsSensor(_BurnerSensor):
    key = "brennerstarts"
    attr = "burner_starts"


class HeatLoadSensor(GeneratorSensor):
    """Heizlast bei Normaußentemperatur aus dem gelernten Kennwert (1.1), mit Verhältnis zur Nennleistung und Taktgrenze."""

    key = "heizlast"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_suggested_display_precision = 1
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _update(self) -> None:
        coord = self.rt.coordinator
        hl = coord.heat_loads.get(self.gen.generator_id) if coord is not None else None
        self._attr_native_value = None if hl is None else round(hl.heat_load_kw, 2)
        self._attr_extra_state_attributes = {"qualitaet": "unzureichend"} if hl is None else hl.as_dict()


class WindowUsageSensor(ResultSensor):
    """Anteil des ersten Zeitfensters (z. B. HT) an der Menge der Periode bisher (1.2); je Fenster Menge und Anteil."""

    key = "zeitfenster"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def value(self, res):
        usage = res.window_usage or {}
        total = sum(usage.values())
        named = [k for k in usage if k != "standard"]
        if not total or not named:
            return None
        return round(usage[sorted(named)[0]] / total * 100, 1)

    def attributes(self, res):
        attrs = super().attributes(res)
        usage = res.window_usage or {}
        total = sum(usage.values())
        if total:
            attrs["fenster"] = {k: {"menge": round(v, 1), "anteil_pct": round(v / total * 100, 1)} for k, v in usage.items()}
            attrs["quelle"] = res.window_sources
        return attrs


class MeanPriceSensor(ResultSensor):
    """Mittlerer Arbeitspreis der Periode bisher beim dynamischen Tarif (1.2), Euro je kWh."""

    key = "mittelpreis"
    _attr_suggested_display_precision = 4

    def __init__(self, rt: TarifRuntime, meter: Meter) -> None:
        self._attr_native_unit_of_measurement = f"{rt.hass.config.currency}/kWh"
        super().__init__(rt, meter)

    def value(self, res):
        a = res.actual
        if a is None or not a.quantity:
            return None
        vat = 1 + res.contract.vat_rate / 100 if res.contract is not None and res.contract.vat_mode.value == "net" else 1.0
        return round(a.energy * vat / a.quantity, 4)  # brutto wie die Kosten-Sensoren


class ComparisonSensor(ResultSensor):
    """Vergleich mit dem dynamischen Tarif (1.2): tatsächlich − dynamisch über die Tage mit Preisen (positiv = dynamisch
    wäre günstiger gewesen)."""

    key = "vergleich_dynamisch"
    money = True

    def value(self, res):
        c = res.comparison
        return None if c is None or c.diff is None else round(c.diff, 2)

    def attributes(self, res):
        attrs = super().attributes(res)
        if res.comparison is not None:
            attrs.update(res.comparison.as_dict())
        return attrs

