"""Einrichtung: Haushalt und Zähler-Subentry mit Vertrag und Startstand."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tarif_cockpit.const import CONF_INITIAL_CONTRACT, CONF_INITIAL_READING, CONF_METER, DOMAIN, SUBENTRY_METER


async def _create_household(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Zuhause", "heating_limit": 15, "indoor_ref": 20, "tolerance_pct": 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_household_and_single_instance(hass: HomeAssistant) -> None:
    entry = await _create_household(hass)
    assert entry.data["household"]["name"] == "Zuhause"
    assert entry.data["household"]["tolerance_pct"] == 5.0
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert again["type"] is FlowResultType.ABORT and again["reason"] == "single_instance_allowed"


async def test_meter_subentry_readings_only(hass: HomeAssistant) -> None:
    entry = await _create_household(hass)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "gas"})
    assert r["step_id"] == "quelle"
    r = await flow.async_configure(r["flow_id"], {"name": "Gas"})
    assert r["step_id"] == "einheit"
    r = await flow.async_configure(r["flow_id"], {"unit": "m³", "calorific": 11.4, "z_factor": 0.95})
    assert r["step_id"] == "vertrag"
    # ungültiger Stichtag
    bad = {"supplier": "Stadtwerke", "start_date": "2026-03-15", "billing_rule": "fixed_day", "fixed_day": "31.02", "vat_mode": "gross", "vat_rate": 19}
    r = await flow.async_configure(r["flow_id"], bad)
    assert r["errors"] == {"fixed_day": "invalid_billing"}
    good = {k: v for k, v in bad.items() if k != "fixed_day"}
    r = await flow.async_configure(r["flow_id"], {**good, "billing_rule": "calendar_year"})
    assert r["step_id"] == "preis"
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.0952, "base_price": 19.04})
    assert r["step_id"] == "abschlag"
    r = await flow.async_configure(r["flow_id"], {"amount": 166, "pay_day": 1, "rhythm": "1"})
    assert r["step_id"] == "startstand"
    assert "15.03.2026 – 31.12.2026 *" in r["description_placeholders"]["preview"]
    # ohne Sensor ist der Startstand Pflicht
    r = await flow.async_configure(r["flow_id"], {"quality": "real"})
    assert r["errors"] == {"value": "required_without_entity"}
    r = await flow.async_configure(r["flow_id"], {"value": 1000.0, "timestamp": "2026-03-15 00:00:00", "quality": "real"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    sub = next(iter(entry.subentries.values()))
    assert sub.data[CONF_METER]["conversion"] == {"calorific": 11.4, "z_factor": 0.95}
    assert sub.data[CONF_INITIAL_CONTRACT]["billing_rule"] == "calendar_year"
    assert sub.data[CONF_INITIAL_READING]["value"] == 1000.0
    assert sub.data["initial_price"] == {"work_price": 0.0952, "base_price": 19.04}
    assert sub.data["initial_plan"] == {"amount": 166.0, "pay_day": 1, "rhythm": 1}
    # nach dem Neuladen: Vertrag und Startstand im Store, Sensor zeigt die Periode
    rt = entry.runtime_data
    assert sub.subentry_id in rt.meters
    assert len(rt.contracts(sub.subentry_id)) == 1
    assert rt.readings(sub.subentry_id)[0].value == 1000.0
    states = [s for s in hass.states.async_all("sensor") if s.attributes.get("periode_id")]
    assert len(states) == 1
    assert states[0].state == "2026-12-31"
    assert states[0].attributes["rumpfjahr"] is True
    assert states[0].attributes["beginn"] == "2026-03-15"


async def test_meter_with_entity_duplicate(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gaszaehler", "9808", {"unit_of_measurement": "m³", "device_class": "gas", "state_class": "total_increasing"})
    entry = await _create_household(hass)
    flow = hass.config_entries.subentries

    async def add() -> dict:
        r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
        r = await flow.async_configure(r["flow_id"], {"medium": "gas"})
        return await flow.async_configure(r["flow_id"], {"name": "Gas", "entity": "sensor.gaszaehler"})

    r = await add()
    assert r["step_id"] == "einheit"
    r = await flow.async_configure(r["flow_id"], {"unit": "m³", "calorific": 11.3, "z_factor": 0.96})
    r = await flow.async_configure(r["flow_id"], {"supplier": "SW", "start_date": "2026-07-30", "billing_rule": "fixed_day", "fixed_day": "30.07", "vat_mode": "gross", "vat_rate": 19})
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.1, "base_price": 10})
    r = await flow.async_configure(r["flow_id"], {"pay_day": 1, "rhythm": "1"})  # ohne Betrag: keine Abschläge
    r = await flow.async_configure(r["flow_id"], {"quality": "real"})  # mit Sensor: Startstand optional
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    r = await add()
    assert r["errors"] == {"entity": "already_configured"}
