"""Sensoren je Zähler (0.5): laufende Periode, letzte Ablesung, Zählerstand, Qualität der Tageswerte.

Kosten-, Prognose- und Urteils-Sensoren folgen in 0.6. Aktualisierung über ein Dispatcher-Signal nach jeder
Datenänderung und einmal täglich (Periodenwechsel).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from . import TarifConfigEntry
from .const import DOMAIN, VERSION, signal_updated
from .engine.consumption import latest_reading
from .engine.model import Meter
from .engine.quality import Quality, usable
from .runtime import TarifRuntime


async def async_setup_entry(hass: HomeAssistant, entry: TarifConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    rt = entry.runtime_data
    for meter in rt.meters.values():
        async_add_entities(
            [cls(rt, meter) for cls in (PeriodEndSensor, LastReadingSensor, MeterValueSensor, DailyQualitySensor)],
            config_subentry_id=meter.meter_id,
        )


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
