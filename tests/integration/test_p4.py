"""0.7: Fragen-Assistent steuert die Schritte, Optionen, Menü am Zähler (Preis, Abschlag, Anbieterwechsel), WebSocket."""

from __future__ import annotations

from datetime import date

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er

from custom_components.tarif_cockpit.const import DOMAIN, SUBENTRY_METER

from .conftest import HOUSEHOLD, make_entry, meter_subentry, setup


def strom_sub():
    sub = meter_subentry(
        "m1", "Strom", "strom", "kWh", entity="sensor.zaehler",
        contract={"supplier": "Stadtwerke", "start_date": "2026-06-30", "billing_rule": "fixed_day", "fixed_day": "30.06"},
        reading={"timestamp": "2026-06-30T00:00:00+02:00", "value": 5645.0, "quality": "real"},
    )
    sub["data"]["initial_price"] = {"work_price": 0.3154, "base_price": 13.09}
    sub["data"]["initial_plan"] = {"amount": 165.0, "pay_day": 1, "rhythm": 1}
    return sub


async def test_unheated_household_skips_climate_step(hass: HomeAssistant) -> None:
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "Wohnung", "heating": ["keine"], "hot_water": "strom", "tenure": "mieter", "rhythm": "1"})
    assert r["step_id"] == "abschluss"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"tolerance_pct": 5})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["result"].data["household"]["situation"]["tenure"] == "mieter"


async def test_situation_drives_meter_dialog(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh", "device_class": "energy"})
    hh = {**HOUSEHOLD, "situation": {"heating": ["gas"], "hot_water": "heizung", "extras": [], "tenure": "eigentuemer", "rhythm": 2}}
    entry = make_entry(strom_sub(), household=hh)
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    assert r["description_placeholders"]["fehlen"].startswith("Gas")  # Strom gibt es schon, Gas fehlt
    r = await flow.async_configure(r["flow_id"], {"medium": "strom"})
    schema_keys = [str(k) for k in r["data_schema"].schema]
    assert "role" not in schema_keys  # keine Wallbox angegeben → kein Unterzähler-Schritt
    r = await flow.async_configure(r["flow_id"], {"name": "Strom 2"})
    r = await flow.async_configure(r["flow_id"], {"unit": "kWh"})
    r = await flow.async_configure(r["flow_id"], {"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year", "vat_mode": "gross", "vat_rate": 19})
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.3, "base_price": 10})
    rhythm_default = next(k.default() for k in r["data_schema"].schema if str(k) == "rhythm")
    assert rhythm_default == "2"  # Rhythmus aus der Situation


async def test_options_flow_reloads_and_keeps_data(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {
        "heating": ["gas"], "hot_water": "heizung", "extras": ["pv"], "tenure": "eigentuemer", "rhythm": "1",
        "heating_limit": 14, "indoor_ref": 20, "tolerance_pct": 3,
    })
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    rt = entry.runtime_data
    assert rt.household.tolerance_pct == 3.0 and rt.household.heating_limit == 14.0
    assert rt.household.situation["extras"] == ["pv"]
    assert len(rt.readings("m1")) == 1  # Daten bleiben


async def _menu(hass, entry, step):
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": "reconfigure", "subentry_id": "m1"})
    assert r["type"] is FlowResultType.MENU and step in r["menu_options"]
    return flow, await flow.async_configure(r["flow_id"], {"next_step_id": step})


async def test_menu_price_and_advance(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    flow, r = await _menu(hass, entry, "preis_aendern")
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-12-01", "work_price": 0.40, "base_price": 15})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "price_saved"
    assert max(entry.runtime_data.data.prices, key=lambda p: p.valid_from).work_price == 0.40
    flow, r = await _menu(hass, entry, "abschlag_aendern")
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-12-01", "amount": 120, "pay_day": 1, "rhythm": "1"})
    assert r["reason"] == "advance_saved"
    res = entry.runtime_data.coordinator.results["m1"]
    assert res.payments.period_total == 5 * 165 + 7 * 120
    # vor Vertragsbeginn: Fehler im Formular, nichts gespeichert
    flow, r = await _menu(hass, entry, "preis_aendern")
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-01-01", "work_price": 0.1, "base_price": 1})
    assert r["errors"] == {"base": "billing_error"} and r["description_placeholders"]["error"]


async def test_supplier_switch_flow(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2026-11-13 12:00:00+01:00")
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    flow, r = await _menu(hass, entry, "anbieterwechsel")
    # Stand zu einem Wechsel in der Zukunft: erst nach dem Wechsel eintragen
    r = await flow.async_configure(r["flow_id"], {"switch_date": "2026-12-01", "value": 6700.0, "quality": "estimated"})
    assert r["errors"] == {"value": "switch_reading_future"}
    # Wechsel vor Vertragsbeginn: sofort im ersten Schritt abgelehnt
    r = await flow.async_configure(r["flow_id"], {"switch_date": "2026-01-01", "quality": "real"})
    assert r["errors"] == {"switch_date": "switch_invalid"} and r["description_placeholders"]["error"]
    r = await flow.async_configure(r["flow_id"], {"switch_date": "2026-11-01", "value": 6600.0, "quality": "estimated"})
    assert r["step_id"] == "wechsel_vertrag"
    r = await flow.async_configure(r["flow_id"], {"supplier": "Neu AG", "billing_rule": "contract_year", "vat_mode": "gross", "vat_rate": 19})
    assert r["step_id"] == "wechsel_preis"
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.28, "base_price": 12, "amount": 150, "pay_day": 1, "rhythm": "1", "max_per_period": 11})
    assert r["reason"] == "switch_saved"
    rt = entry.runtime_data
    chain = rt.contracts("m1")
    assert [c.supplier for c in chain] == ["Stadtwerke", "Neu AG"] and chain[0].end_date == date(2026, 10, 31)
    assert any(x.source.value == "switch" and x.quality.value == "estimated" for x in rt.readings("m1"))
    plan = next(p for p in rt.data.advance_plans if p.contract_id == chain[1].contract_id)
    assert plan.max_per_period == 11


async def test_menu_prefills_current_values(hass: HomeAssistant, freezer) -> None:
    """Preis/Abschlag ändern: Formulare mit den laufenden Werten vorbelegt (nur den Betrag ändern ändert nur den Betrag)."""
    freezer.move_to("2026-11-13 12:00:00+01:00")
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    sub = strom_sub()
    sub["data"]["initial_price"] = {"work_price": 0.3154, "base_price": 13.09, "metering_price": 2.5}
    sub["data"]["initial_plan"] = {"amount": 165.0, "pay_day": 15, "rhythm": 3}
    entry = make_entry(sub)
    assert await setup(hass, entry)
    flow, r = await _menu(hass, entry, "preis_aendern")
    keys = {str(k): k for k in r["data_schema"].schema}
    assert keys["work_price"].default() == 0.3154 and keys["base_price"].default() == 13.09
    assert keys["metering_price"].description == {"suggested_value": 2.5}
    flow, r = await _menu(hass, entry, "abschlag_aendern")
    keys = {str(k): k for k in r["data_schema"].schema}
    assert keys["pay_day"].default() == 15 and keys["rhythm"].default() == "3"
    assert keys["amount"].description == {"suggested_value": 165.0}


async def test_menu_aborts_when_not_loaded(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    flow, r = await _menu(hass, entry, "abschlag_aendern")
    assert await hass.config_entries.async_unload(entry.entry_id)
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-12-01", "amount": 120, "pay_day": 1, "rhythm": "1"})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "not_loaded"


async def test_summary_survives_probe_error(hass: HomeAssistant, monkeypatch) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)

    def boom(*args, **kwargs):
        raise RuntimeError("Testfehler")

    monkeypatch.setattr("custom_components.tarif_cockpit.probe.evaluate_meter", boom)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "strom"})
    r = await flow.async_configure(r["flow_id"], {"name": "Strom Keller"})
    r = await flow.async_configure(r["flow_id"], {"unit": "kWh", "annual_consumption": 3500})
    r = await flow.async_configure(r["flow_id"], {"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year", "vat_mode": "gross", "vat_rate": 19})
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.3, "base_price": 10})
    r = await flow.async_configure(r["flow_id"], {"amount": 85, "pay_day": 1, "rhythm": "1"})
    r = await flow.async_configure(r["flow_id"], {"value": 1000.0, "timestamp": "2026-01-01 00:00:00", "quality": "real"})
    assert r["step_id"] == "zusammenfassung" and r["description_placeholders"]["prognose"]
    r = await flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY


async def test_climate_step_saved_and_options_without_invented_answers(hass: HomeAssistant) -> None:
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "Haus", "heating": ["gas"], "hot_water": "heizung", "tenure": "eigentuemer", "rhythm": "1"})
    assert r["step_id"] == "klima"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"outdoor_temp_entity": "sensor.aussen", "heating_limit": 14, "indoor_ref": 21})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"tolerance_pct": 5})
    hh = r["result"].data["household"]
    assert hh["outdoor_temp_entity"] == "sensor.aussen" and hh["heating_limit"] == 14.0 and hh["indoor_ref"] == 21.0
    # migrierter Haushalt (Situation leer): Optionen ohne vorbelegte Antworten
    entry = make_entry(strom_sub())
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry2 = make_entry(strom_sub())
    entry2.add_to_hass(hass)
    r = await hass.config_entries.options.async_init(entry2.entry_id)
    keys = {str(k): k for k in r["data_schema"].schema}
    assert keys["heating"].default is vol.UNDEFINED and keys["hot_water"].default is vol.UNDEFINED
    del entry


async def test_websocket_meters(hass: HomeAssistant, hass_ws_client) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "tarif_cockpit/zaehler"})
    msg = await client.receive_json()
    assert msg["success"]
    hh = msg["result"]["haushalte"][0]
    m = hh["zaehler"][0]
    assert m["name"] == "Strom" and m["medium"] == "strom" and m["device_id"]
    assert m["sensoren"]["urteil"].startswith("sensor.") and m["sensoren"]["kosten_bisher"].startswith("sensor.")
    assert m["vertraege"][0]["lieferant"] == "Stadtwerke"
    assert hh["saldo_gesamt"].startswith("sensor.")


async def test_summary_forecast_without_sensor(hass: HomeAssistant) -> None:
    """Zähler ohne Sensor, aber mit Jahresverbrauch: die Zusammenfassung zeigt schon eine erste Prognose (Annahme)."""
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    hass.config.language = "de"
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "strom"})
    r = await flow.async_configure(r["flow_id"], {"name": "Strom Keller"})
    r = await flow.async_configure(r["flow_id"], {"unit": "kWh", "annual_consumption": 3500})
    r = await flow.async_configure(r["flow_id"], {"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year", "vat_mode": "gross", "vat_rate": 19})
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.3154, "base_price": 13.09})
    r = await flow.async_configure(r["flow_id"], {"amount": 85, "pay_day": 1, "rhythm": "1"})
    r = await flow.async_configure(r["flow_id"], {"value": 1000.0, "timestamp": "2026-01-01 00:00:00", "quality": "real"})
    assert r["step_id"] == "zusammenfassung"
    ph = r["description_placeholders"]
    assert ph["preis"].startswith("0,3154 EUR/kWh") and "13,09" in ph["preis"]
    assert ph["abschlag"] == "85,00 EUR · Zahltag 1 · monatlich"
    assert ph["prognose"].startswith("Kosten der Periode") and "Annahme" in ph["prognose"]


async def test_websocket_rights_and_disabled_sensors(hass: HomeAssistant, hass_ws_client, hass_read_only_access_token, hass_read_only_user) -> None:
    """Lesen darf jeder Benutzer (die Karte sieht jeder); schreibende Aktionen nur Administratoren. Deaktivierte Sensoren fehlen."""
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = make_entry(strom_sub())
    assert await setup(hass, entry)
    ent_reg = er.async_get(hass)
    qual = next(e for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id) if e.unique_id.endswith("_tageswerte_qualitaet"))
    ent_reg.async_update_entity(qual.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json({"id": 1, "type": "tarif_cockpit/zaehler"})
    msg = await client.receive_json()
    assert msg["success"]
    sensors = msg["result"]["haushalte"][0]["zaehler"][0]["sensoren"]
    assert "tageswerte_qualitaet" not in sensors and "urteil" in sensors
    device_id = msg["result"]["haushalte"][0]["zaehler"][0]["device_id"]
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, "set_abschlag", {"zaehler": device_id, "ab": "2026-12-01", "betrag": 100},
                                       blocking=True, context=Context(user_id=hass_read_only_user.id))
