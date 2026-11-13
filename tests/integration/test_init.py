"""Setup, Unload, Neustart, Migrationen, Schutz vor Datenverlust, fehlender Recorder, Frontend, Diagnose."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.tarif_cockpit.const import DOMAIN, ISSUE_OLD_RESOURCE, ISSUE_STORE_INVALID, ISSUE_STORE_LOST
from custom_components.tarif_cockpit.diagnostics import async_get_config_entry_diagnostics
from custom_components.tarif_cockpit.engine.quality import Quality
from custom_components.tarif_cockpit.frontend import CARD_URL, async_check_old_resource

from .conftest import make_entry, meter_subentry, setup

KEY = f"{DOMAIN}.testentry"


def stored(meter_id: str = "m1", minor: int = 2, readings: list[dict] | None = None) -> dict[str, Any]:
    return {
        "version": 1, "minor_version": minor, "key": KEY,
        "data": {
            "readings": readings if readings is not None else [
                {"reading_id": "r0", "meter_id": meter_id, "timestamp": "2026-03-15T00:00:00+01:00", "value": 1000.0,
                 "quality": "real", "source": "initial", "note": None, "superseded_by": None}
            ],
            "daily": [], "contracts": [
                {"contract_id": "c1", "meter_id": meter_id, "supplier": "Stadtwerke", "start_date": "2026-03-15", "billing_rule": "calendar_year"}
            ],
            "periods": [], "prices": [], "advance_plans": [], "payments": [], "invoices": [], "snapshots": [], "intervals": [],
            "imported_meters": [meter_id],
        },
    }


async def test_setup_unload_reload(hass: HomeAssistant, hass_storage) -> None:
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["store_created"] is True
    assert KEY in hass_storage
    assert hass.states.get("sensor.gas_periodenende") is not None or any(
        s.attributes.get("periode_id") for s in hass.states.async_all("sensor")
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    # Startstand wurde genau einmal übernommen
    assert len(entry.runtime_data.readings("m1")) == 1
    assert len(entry.runtime_data.contracts("m1")) == 1


async def test_restart_keeps_data(hass: HomeAssistant, hass_storage) -> None:
    hass_storage[KEY] = stored()
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    from datetime import datetime

    rt.add_reading("m1", datetime.fromisoformat("2026-11-01T08:00:00+01:00"), 1500.0)
    rt.changed()
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[KEY]["data"]["readings"]
    assert [r["value"] for r in saved] == [1000.0, 1500.0]
    # "Neustart": neu laden aus dem Store
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [r.value for r in entry.runtime_data.readings("m1")] == [1000.0, 1500.0]


async def test_store_migration_1_1_to_1_2(hass: HomeAssistant, hass_storage) -> None:
    old = stored(minor=1)
    del old["data"]["readings"][0]["quality"]
    hass_storage[KEY] = old
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert await setup(hass, entry)
    assert entry.runtime_data.readings("m1")[0].quality == Quality.REAL
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[KEY]["minor_version"] == 2
    assert hass_storage[KEY]["data"]["readings"][0]["quality"] == "real"


async def test_config_entry_migration(hass: HomeAssistant) -> None:
    hh = {"name": "Alt", "heating_limit": 15.0, "indoor_ref": 20.0}
    entry = make_entry(meter_subentry("m1"), minor_version=1, household=hh)
    assert await setup(hass, entry)
    assert entry.minor_version == 2
    assert entry.data["household"]["tolerance_pct"] == 5.0


async def test_lost_store_does_not_start_empty(hass: HomeAssistant, hass_storage) -> None:
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert not await setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_STORE_LOST}_testentry") is not None
    assert KEY not in hass_storage  # nichts leer überschrieben


async def test_invalid_store_is_reported_and_untouched(hass: HomeAssistant, hass_storage) -> None:
    bad = stored()
    bad["data"]["readings"][0]["value"] = "kaputt"
    hass_storage[KEY] = copy.deepcopy(bad)
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert not await setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_STORE_INVALID}_testentry")
    assert issue is not None and "Zahl erwartet" in issue.translation_placeholders["errors"]
    assert hass_storage[KEY] == bad


async def test_without_recorder_days_are_missing_not_zero(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "unavailable")
    contract = {"supplier": "SW", "start_date": "2026-11-01", "billing_rule": "calendar_year"}
    entry = make_entry(meter_subentry("m1", "Strom", "strom", "kWh", entity="sensor.zaehler", contract=contract))
    assert await setup(hass, entry)
    assert "recorder" not in hass.config.components
    daily = entry.runtime_data.daily("m1")
    assert len(daily) == 12  # 01.11. bis gestern (12.11.)
    assert all(d.consumption is None and d.quality == Quality.MISSING for d in daily.values())


async def test_frontend_static_path_and_extra_js(hass: HomeAssistant, hass_client) -> None:
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    client = await hass_client()
    resp = await client.get("/tarif_cockpit/tarif-cockpit.js")
    assert resp.status == 200
    assert "tarif-cockpit-card" in await resp.text()
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

        assert CARD_URL in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_old_dashboard_resource_is_reported(hass: HomeAssistant) -> None:
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    class FakeResources:
        def async_items(self):
            return [{"id": "1", "type": "module", "url": "/hacsfiles/tarif-cockpit/tarif-cockpit.js?hacstag=1"}]

    class FakeData:
        resources = FakeResources()

    hass.data[LOVELACE_DATA] = FakeData()
    hass.config.components.add("lovelace")
    assert await async_check_old_resource(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_OLD_RESOURCE) is not None


async def test_diagnostics(hass: HomeAssistant) -> None:
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    m = diag["meters"]["m1"]
    assert m["current_period"] == {"start": "2026-03-15", "end": "2026-12-31", "partial": True, "final": False}
    assert diag["counts"]["contracts"] == 1


async def test_store_from_newer_version_is_untouched(hass: HomeAssistant, hass_storage) -> None:
    newer = stored()
    newer["version"] = 2
    hass_storage[KEY] = copy.deepcopy(newer)
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert not await setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, "store_zu_neu_testentry") is not None
    assert hass_storage[KEY] == newer
