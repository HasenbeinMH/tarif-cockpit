"""1.1: Rechnung erfassen (Aktion und Dialog), Vergleich, Reparatur „Übernehmen“, Staffel/Rundung, Heizlast, Speicher 1.5."""

from __future__ import annotations

from datetime import date

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.tarif_cockpit.const import DOMAIN, EVENT_INVOICE, ISSUE_INVOICE, signal_updated
from custom_components.tarif_cockpit.engine.model import ReadingSource
from custom_components.tarif_cockpit.engine.regression import HeatModel, ModelQuality

from .conftest import generator_subentry, make_entry, meter_device_id, meter_subentry, setup
from .test_init import KEY, stored


def gas(start="2026-03-15", **meter):
    sub = meter_subentry("g1", contract={"supplier": "SW", "start_date": start, "billing_rule": "calendar_year"},
                         reading={"timestamp": f"{start}T00:00:00+01:00", "value": 1000.0, "quality": "real"})
    sub["data"]["meter"]["conversion"] = {"calorific": 11.0, "z_factor": 0.95}
    sub["data"]["meter"].update(meter)
    sub["data"]["initial_price"] = {"work_price": 0.10, "base_price": 15.0}
    return sub


async def _call(hass, service, data):
    return await hass.services.async_call(DOMAIN, service, data, blocking=True, return_response=True)


async def test_invoice_before_contract_is_stored_at_meter(hass: HomeAssistant, hass_storage) -> None:
    entry = make_entry(gas())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "g1")
    out = await _call(hass, "add_rechnung", {"zaehler": dev, "datum": date(2026, 1, 20), "von": date(2025, 1, 1), "bis": date(2025, 12, 31),
                                             "betrag": 1650.0, "menge_kwh": 14200.0})
    inv = rt.invoices("g1")[0]
    assert inv.contract_id is None and inv.meter_id == "g1" and inv.quantity_kwh == 14200.0
    assert out["ablesungen"] == [] and "ohne_vertrag" in out["vergleich"]["flags"]
    await hass.config_entries.async_reload(entry.entry_id)  # Rechnung ohne Vertrag übersteht das Laden
    await hass.async_block_till_done()
    assert entry.runtime_data.invoices("g1")[0].invoice_id == inv.invoice_id


async def test_invoice_readings_not_duplicated(hass: HomeAssistant) -> None:
    entry = make_entry(gas())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "g1")
    data = {"zaehler": dev, "datum": date(2026, 11, 5), "von": date(2026, 3, 15), "bis": date(2026, 10, 31), "betrag": 700.0,
            "stand_anfang": 1000.0, "stand_ende": 1500.0}
    out = await _call(hass, "add_rechnung", data)
    assert len(out["ablesungen"]) == 1  # Anfangsstand = Startstand der Einrichtung
    readings = rt.readings("g1")
    assert [r.value for r in readings] == [1000.0, 1500.0] and readings[-1].source == ReadingSource.INVOICE
    again = await _call(hass, "add_rechnung", {**data, "datum": date(2026, 11, 6)})
    assert again["ablesungen"] == [] and len(rt.readings("g1")) == 2


async def test_invoice_calorific_repair_applies_calibration(hass: HomeAssistant, freezer) -> None:
    from pytest_homeassistant.common import async_fire_time_changed  # noqa: PLC0415

    events = []
    hass.bus.async_listen(EVENT_INVOICE, lambda e: events.append(e.data))
    entry = make_entry(gas())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "g1")
    out = await _call(hass, "add_rechnung", {"zaehler": dev, "datum": date(2026, 11, 5), "von": date(2026, 3, 15), "bis": date(2026, 10, 31),
                                             "betrag": 700.0, "stand_anfang": 1000.0, "stand_ende": 1500.0, "brennwert": 11.4, "zustandszahl": 0.95})
    await hass.async_block_till_done()
    inv_id = out["rechnung_id"]
    assert [p["art"] for p in out["vergleich"]["vorschlaege"]] == ["brennwert"]
    issue_id = f"{ISSUE_INVOICE}_{inv_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None and issue.is_fixable and issue.data["invoice_id"] == inv_id
    assert len(events) == 1 and events[0]["rechnung"] == inv_id
    kwh_before = rt.coordinator.results["g1"].used_billing
    from homeassistant.components.repairs import repairs_flow_manager  # noqa: PLC0415
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()  # HA lädt repairs.py der Integration selbst
    manager = repairs_flow_manager(hass)
    r = await manager.async_init(DOMAIN, data={"issue_id": issue_id})
    assert r["step_id"] == "confirm" and "11,4000" in r["description_placeholders"]["vorschlaege"]
    r = await manager.async_configure(r["flow_id"], {})
    assert r["type"] == "create_entry"
    freezer.tick(2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    cal = rt.data.calibrations[0]
    assert (cal.kind, cal.value, cal.valid_from, cal.valid_to) == ("brennwert", 11.4, date(2026, 3, 15), date(2026, 10, 31))
    after = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    # Brennwert passt jetzt; übrig bleibt nur der Hinweis zum Betrag (ohne Knopf), denn 700 € sind frei gewählt
    assert after is not None and not after.is_fixable and after.translation_key == f"{ISSUE_INVOICE}_hinweis"
    assert rt.coordinator.results["g1"].used_billing > kwh_before  # Brennwert der Rechnung gilt im Zeitraum
    rt.coordinator.check_invoices()
    assert len(events) == 1  # Event je Rechnung nur einmal


async def test_invoice_dialog(hass: HomeAssistant) -> None:
    entry = make_entry(gas())
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "g1"})
    assert "rechnung_erfassen" in r["menu_options"]
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "rechnung_erfassen"})
    assert r["step_id"] == "rechnung_erfassen" and "calorific" in r["data_schema"].schema
    r = await flow.async_configure(r["flow_id"], {"invoice_date": "2026-11-05", "period_from": "2026-10-31", "period_to": "2026-03-15", "amount": 700})
    assert r["errors"] == {"period_to": "period_order"}
    r = await flow.async_configure(r["flow_id"], {"invoice_date": "2026-11-05", "period_from": "2026-03-15", "period_to": "2026-10-31",
                                                 "amount": 700, "end_reading": 1500, "readings_estimated": True})
    assert r["reason"] == "invoice_saved" and r["description_placeholders"]["ablesungen"] == "1"
    rt = entry.runtime_data
    assert rt.readings("g1")[-1].quality.value == "estimated"


async def test_price_tiers_and_rounding(hass: HomeAssistant) -> None:
    entry = make_entry(gas())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "g1")
    await _call(hass, "set_preis", {"zaehler": dev, "ab": date(2026, 6, 1), "arbeitspreis": 0.11, "grundpreis": 15.0,
                                    "staffel": [{"bis": 10000, "preis": 0.11}, {"preis": 0.09}], "rundung_grundpreis": "month",
                                    "rundung_betrag_stellen": 2})
    seg = next(p for p in rt.data.prices if p.valid_from == date(2026, 6, 1))
    assert [(t.upto, t.work_price) for t in seg.tiers] == [(10000.0, 0.11), (None, 0.09)]
    assert seg.rounding.base_by == "month" and seg.rounding.money_decimals == 2
    # Dialog ohne Haken, aber der laufende Preis hat eine Staffel: der Staffel-Schritt folgt trotzdem, vorbelegt
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "g1"})
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "preis_aendern"})
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-11-01", "work_price": 12.0, "base_price": 15.0})
    assert r["step_id"] == "staffel_rundung"
    r = await flow.async_configure(r["flow_id"], {"tier1_upto": 10000, "tier1_price": 12.0, "tier3_price": 9.0, "tier_mode": "block",
                                                 "days_per_year": "average", "base_by": "month", "money_decimals": 2})
    assert r["reason"] == "price_saved"
    seg = next(p for p in rt.data.prices if p.valid_from == date(2026, 11, 1))
    assert [round(t.work_price, 4) for t in seg.tiers] == [0.12, 0.09] and seg.rounding.base_by == "month"
    # mit Haken: eigener Schritt, Preise in Cent
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "g1"})
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "preis_aendern"})
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-11-10", "work_price": 12.0, "base_price": 15.0, "tiers_rounding": True})
    assert r["step_id"] == "staffel_rundung"
    r = await flow.async_configure(r["flow_id"], {"tier1_upto": 5000, "tier1_price": 12.0, "tier2_upto": 4000, "tier2_price": 11.0,
                                                 "tier_mode": "block", "days_per_year": "365", "base_by": "day"})
    assert r["errors"] == {"tier2_upto": "tiers_order"}
    r = await flow.async_configure(r["flow_id"], {"tier1_upto": 5000, "tier_mode": "block", "days_per_year": "365", "base_by": "day"})
    assert r["errors"] == {"tier1_price": "tier_incomplete"}
    r = await flow.async_configure(r["flow_id"], {"tier1_upto": 5000, "tier1_price": 12.0, "tier3_price": 10.0,
                                                 "tier_mode": "total", "days_per_year": "365", "base_by": "day", "quantity_decimals": 0})
    assert r["reason"] == "price_saved"
    seg = next(p for p in rt.data.prices if p.valid_from == date(2026, 11, 10))
    assert [(t.upto, round(t.work_price, 4)) for t in seg.tiers] == [(5000.0, 0.12), (None, 0.10)]
    assert seg.tier_mode == "total" and seg.rounding.days_per_year == "365" and seg.rounding.quantity_decimals == 0
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert next(p for p in entry.runtime_data.data.prices if p.valid_from == date(2026, 11, 10)).tiers[0].upto == 5000.0


async def test_heat_load_sensor(hass: HomeAssistant) -> None:
    entry = make_entry(gas(), generator_subentry("k1", kind="gas_boiler", title="Kessel", nominal_kw=19.5, min_kw=4.7, efficiency=0.97))
    assert await setup(hass, entry)
    from homeassistant.helpers import entity_registry as er  # noqa: PLC0415

    eid = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "k1_heizlast")
    state = hass.states.get(eid)
    assert state.state == "unknown" and state.attributes["qualitaet"] == "unzureichend"
    coord = entry.runtime_data.coordinator
    coord._models["g1"] = HeatModel(heat_coefficient=5.0, hot_water_baseload=8.0, confidence=ModelQuality.GOOD, sample_count=60)
    coord._refresh_generators()
    async_dispatcher_send(hass, signal_updated(entry.entry_id))
    await hass.async_block_till_done()
    state = hass.states.get(state.entity_id)
    assert abs(float(state.state) - 5.83) < 0.01 and state.attributes["einordnung"] == "ueberdimensioniert"
    assert state.attributes["normaussentemperatur"] == -12.0 and state.attributes["unit_of_measurement"] == "kW"


async def test_archive_websocket_has_accuracy_and_invoices(hass: HomeAssistant, hass_ws_client) -> None:
    entry = make_entry(gas())
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "g1")
    await _call(hass, "add_rechnung", {"zaehler": dev, "datum": date(2026, 11, 5), "von": date(2026, 3, 15), "bis": date(2026, 10, 31),
                                       "betrag": 700.0, "stand_ende": 1500.0})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/archiv", "zaehler": "g1"})
    msg = await client.receive_json()
    assert msg["success"]
    res = msg["result"]
    assert res["prognoseguete"]["perioden"] == 0 and len(res["rechnungen"]) == 1 and res["kalibrierungen"] == []


async def test_store_migration_1_4_to_1_5(hass: HomeAssistant, hass_storage) -> None:
    old = stored(minor=4)
    old["data"]["invoices"] = [{"invoice_id": "i1", "contract_id": "c1", "invoice_date": "2026-11-01", "period_from": "2026-03-15",
                                "period_to": "2026-10-31", "amount": 500.0}]
    hass_storage[KEY] = old
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert await setup(hass, entry)
    inv = entry.runtime_data.data.invoices[0]
    assert inv.meter_id == "m1" and inv.quantity is None
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[KEY]["minor_version"] == 5


async def test_invoice_reading_checks(hass: HomeAssistant) -> None:
    from homeassistant.exceptions import ServiceValidationError  # noqa: PLC0415
    import pytest  # noqa: PLC0415

    entry = make_entry(gas())
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "g1")
    base = {"zaehler": dev, "datum": date(2026, 11, 5), "von": date(2026, 3, 15), "betrag": 700.0}
    with pytest.raises(ServiceValidationError):
        await _call(hass, "add_rechnung", {**base, "bis": date(2026, 10, 31), "stand_anfang": 1500.0, "stand_ende": 1400.0})
    with pytest.raises(ServiceValidationError):
        await _call(hass, "add_rechnung", {**base, "bis": date(2026, 12, 31), "stand_ende": 1600.0})  # Ende in der Zukunft
    # eine echte Ablesung am selben Tag geht einem geschätzten Rechnungsstand vor
    rt = entry.runtime_data
    await _call(hass, "add_ablesung", {"zaehler": dev, "stand": 1480.0, "zeitpunkt": "2026-11-01T08:00:00+01:00"})
    out = await _call(hass, "add_rechnung", {**base, "bis": date(2026, 10, 31), "stand_ende": 1477.0, "staende_geschaetzt": True})
    assert out["ablesungen"] == [] and [r.value for r in rt.readings("g1")] == [1000.0, 1480.0]

