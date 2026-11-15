"""Binäre Sensoren (1.2): Leckage-Verdacht je Wasserzähler mit Sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TarifConfigEntry
from .const import DOMAIN, VERSION, signal_updated
from .engine.model import Medium, Meter
from .runtime import TarifRuntime


async def async_setup_entry(hass: HomeAssistant, entry: TarifConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    rt = entry.runtime_data
    for meter in rt.meters.values():
        if meter.medium == Medium.WASSER and meter.entity and meter.role == "main":
            async_add_entities([LeakSensor(rt, meter)], config_subentry_id=meter.meter_id)


class LeakSensor(BinarySensorEntity):
    """Leckage-Verdacht aus den Stundenwerten (Nachtminimum oder Dauerfluss), täglich nach dem Tageslauf."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "leckage"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, rt: TarifRuntime, meter: Meter) -> None:
        self.rt = rt
        self.meter = meter
        self._attr_unique_id = f"{meter.meter_id}_leckage"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, meter.meter_id)}, name=meter.name or meter.meter_id,
                                            manufacturer="Tarif-Cockpit", model=f"Zähler {meter.medium.value}", sw_version=VERSION,
                                            entry_type=DeviceEntryType.SERVICE)
        self._update()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, signal_updated(self.rt.entry.entry_id), self._refresh))

    @callback
    def _refresh(self, *_: Any) -> None:
        self._update()
        self.async_write_ha_state()

    def _update(self) -> None:
        coord = self.rt.coordinator
        res = coord.leaks.get(self.meter.meter_id) if coord is not None else None
        self._attr_is_on = None if res is None or res.checked_days == 0 else res.suspect
        self._attr_extra_state_attributes = {} if res is None else res.as_dict()
