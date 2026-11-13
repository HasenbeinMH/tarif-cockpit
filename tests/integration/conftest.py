"""Gemeinsame Hilfen der Integrationstests (pytest-homeassistant, echte HA-Testumgebung)."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant

from custom_components.tarif_cockpit.const import (
    CONF_HOUSEHOLD, CONF_INITIAL_CONTRACT, CONF_INITIAL_READING, CONF_METER, CONF_STORE_CREATED, DOMAIN, SUBENTRY_METER,
)

TODAY = "2026-11-13 12:00:00+01:00"
HOUSEHOLD = {"name": "Testhaus", "outdoor_temp_entity": None, "weather_entity": None, "heating_limit": 15.0, "indoor_ref": 20.0, "tolerance_pct": 5.0, "rooms": []}


@pytest.fixture(autouse=True)
async def berlin(hass: HomeAssistant, freezer):
    """Feste Zeitzone und fester Tag für reproduzierbare Perioden."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(TODAY)


def meter_subentry(
    subentry_id: str,
    title: str = "Gas",
    medium: str = "gas",
    unit: str = "m³",
    entity: str | None = None,
    contract: dict[str, Any] | None = None,
    reading: dict[str, Any] | None = None,
) -> ConfigSubentryData:
    contract = contract or {"supplier": "Stadtwerke", "start_date": "2026-03-15", "billing_rule": "calendar_year"}
    return ConfigSubentryData(
        data={
            CONF_METER: {"medium": medium, "unit": unit, "entity": entity, "name": title, "data_level": 2 if entity else 1, "conversion": {}},
            CONF_INITIAL_CONTRACT: contract,
            CONF_INITIAL_READING: reading if reading is not None else (None if entity else {"timestamp": "2026-03-15T00:00:00+01:00", "value": 1000.0, "quality": "real"}),
        },
        subentry_id=subentry_id,
        subentry_type=SUBENTRY_METER,
        title=title,
        unique_id=entity,
    )


def make_entry(*subentries: ConfigSubentryData, store_created: bool = False, minor_version: int = 2, household: dict | None = None) -> MockConfigEntry:
    data: dict[str, Any] = {CONF_HOUSEHOLD: household or dict(HOUSEHOLD)}
    if store_created:
        data[CONF_STORE_CREATED] = True
    return MockConfigEntry(
        domain=DOMAIN, title="Testhaus", data=data, version=1, minor_version=minor_version,
        subentries_data=list(subentries), entry_id="testentry",
    )


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    entry.add_to_hass(hass)
    ok = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return ok


def meter_device_id(hass: HomeAssistant, meter_id: str) -> str:
    from homeassistant.helpers import device_registry as dr

    reg = dr.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        for dev in dr.async_entries_for_config_entry(reg, entry.entry_id):
            if (DOMAIN, meter_id) in dev.identifiers:
                return dev.id
    raise AssertionError(f"kein Gerät für {meter_id}")
