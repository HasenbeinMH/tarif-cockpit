"""0.6: Ergebnis-Sensoren, Coordinator, Aktionen für Preise/Abschläge/Zahlungen/Rechnungen, Schnappschüsse, Migration 1.3."""

from __future__ import annotations

import copy
from datetime import date

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError

from custom_components.tarif_cockpit.const import DOMAIN, SUBENTRY_METER

from .conftest import make_entry, meter_device_id, meter_subentry, setup

KEY = f"{DOMAIN}.testentry"


def strom_entry(entity: str | None = "sensor.zaehler", price=None, plan=None):
    sub = meter_subentry(
        "m1", "Strom", "strom", "kWh", entity=entity,
        contract={"supplier": "Stadtwerke", "start_date": "2026-06-30", "billing_rule": "fixed_day", "fixed_day": "30.06"},
        reading={"timestamp": "2026-06-30T00:00:00+02:00", "value": 5645.0, "quality": "real"},
    )
    sub["data"]["initial_price"] = price or {"work_price": 0.3154, "base_price": 13.09}
    sub["data"]["initial_plan"] = plan or {"amount": 165.0, "pay_day": 1, "rhythm": 1}
    return make_entry(sub)


def state(hass: HomeAssistant, key: str):
    for s in hass.states.async_all("sensor"):
        ent = s.entity_id
        if ent.endswith(key) or s.attributes.get("friendly_name", "").lower().endswith(key.replace("_", " ")):
            return s
    raise AssertionError(f"Sensor {key} fehlt: {[s.entity_id for s in hass.states.async_all('sensor')]}")


def result(entry):
    return entry.runtime_data.coordinator.results["m1"]


async def test_result_sensors_with_meter_sensor(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    res = result(entry)
    assert res.consumption.used == pytest.approx(1000.9)
    assert res.payments.paid_to_date == 5 * 165  # 01.07. bis 01.11.
    assert res.payments.period_total == 12 * 165
    cost = res.balance.actual_cost
    assert cost == pytest.approx(1000.9 * 0.3154 + 13.09 * 12 * 136.5 / 365.25, rel=0.01)
    # Ohne Vorjahr und mit über 30 Tagen eigener Daten: Durchschnitt seit Beginn, "vorläufig"
    assert res.forecast.method == "mittel_seit_beginn"
    states = {s.entity_id: s for s in hass.states.async_all("sensor")}
    ids = [e for e in states if e.startswith("sensor.strom_")]
    for key in ("costs_so_far", "advances_paid_so_far", "forecast_consumption", "forecast_costs", "balance", "verdict",
                "recommended_advance", "forecast_quality", "advances_for_the_period", "advance_payment"):
        assert any(e.endswith(key) for e in ids), (key, ids)
    verdict = next(states[e] for e in ids if e.endswith("verdict"))
    assert verdict.state in ("passt", "rueckzahlung", "nachzahlung")
    assert float(states["sensor.strom_advance_payment"].state) == 165.0
    total = states["sensor.testhaus_total_balance"]
    assert float(total.state) == pytest.approx(res.balance.saldo)


async def test_meter_change_is_debounced_and_recomputed(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    hass.states.async_set("sensor.zaehler", "6745.9", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    assert result(entry).consumption.used == pytest.approx(1000.9)  # noch entprellt
    freezer.tick(31)
    from pytest_homeassistant.common import async_fire_time_changed

    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert result(entry).consumption.used == pytest.approx(1100.9)


async def test_price_change_changes_costs_not_quantities(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    before = result(entry)
    await hass.services.async_call(DOMAIN, "set_preis", {"zaehler": dev, "ab": "2026-12-01", "arbeitspreis": 0.40, "grundpreis": 15.0}, blocking=True)
    after = result(entry)
    assert after.forecast_total == before.forecast_total
    assert after.balance.forecast_cost > before.balance.forecast_cost
    assert after.balance.actual_cost == before.balance.actual_cost  # Preis gilt erst ab Dezember
    prices = sorted(entry.runtime_data.data.prices, key=lambda p: p.valid_from)
    assert prices[0].valid_to == date(2026, 11, 30) and prices[1].work_price == 0.40
    with pytest.raises(ServiceValidationError):  # vor Vertragsbeginn läuft kein Vertrag
        await hass.services.async_call(DOMAIN, "set_preis", {"zaehler": dev, "ab": "2026-01-01", "arbeitspreis": 0.3, "grundpreis": 10}, blocking=True)


async def test_advance_payment_invoice_services(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    await hass.services.async_call(DOMAIN, "set_abschlag", {"zaehler": dev, "ab": "2026-12-01", "betrag": 120.0}, blocking=True)
    assert result(entry).payments.period_total == 5 * 165 + 7 * 120
    await hass.services.async_call(DOMAIN, "add_zahlung", {"zaehler": dev, "datum": "2026-11-10", "betrag": 50.0, "art": "credit"}, blocking=True)
    assert result(entry).payments.paid_to_date == 5 * 165 - 50
    resp = await hass.services.async_call(DOMAIN, "add_rechnung", {"zaehler": dev, "datum": "2026-08-01", "von": "2026-06-30", "bis": "2026-07-31", "betrag": 200.0},
                                          blocking=True, return_response=True)
    assert entry.runtime_data.data.invoices[0].invoice_id == resp["rechnung_id"]
    assert result(entry).payments.paid_to_date == 5 * 165 - 50  # Rechnung ist keine Zahlung
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_rechnung", {"zaehler": dev, "datum": "2026-08-01", "von": "2026-06-30", "bis": "2026-07-31", "betrag": 1.0, "korrigiert": "nix"}, blocking=True)


async def test_snapshots_are_frozen(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    coord = entry.runtime_data.coordinator
    assert coord.take_snapshots() == 1
    assert coord.take_snapshots() == 0  # höchstens einer je Periode und Tag
    snap = entry.runtime_data.data.snapshots[0]
    assert snap.forecast_cost == result(entry).balance.forecast_cost
    assert snap.period_id == result(entry).period.period_id


async def test_store_migration_1_2_to_1_3(hass: HomeAssistant, hass_storage) -> None:
    old = {"version": 1, "minor_version": 2, "key": KEY, "data": {
        "readings": [], "contracts": [{"contract_id": "c1", "meter_id": "m1", "supplier": "SW", "start_date": "2026-06-30", "billing_rule": "calendar_year"}],
        "daily": [{"meter_id": "m1", "date": "2026-11-01", "consumption": 3.0, "degree_days": None, "outdoor_temperature": None, "indoor_temperature": None,
                   "heating_hours": None, "fireplace_hours": None, "quality": "real", "quality_flags": [], "source": "statistics"}],
        "periods": [], "prices": [{"contract_id": "c1", "valid_from": "2026-06-30", "work_price": 0.3, "base_price": 10.0, "valid_to": None,
                                   "components": {}, "demand_price": None, "metering_price": None}],
        "advance_plans": [{"contract_id": "c1", "steps": [], "pay_day": 1, "rhythm": 1}],
        "payments": [], "invoices": [], "snapshots": [], "intervals": [], "imported_meters": ["m1"]}}
    hass_storage[KEY] = copy.deepcopy(old)
    entry = make_entry(meter_subentry("m1", entity="sensor.zaehler"), store_created=True)
    assert await setup(hass, entry)
    d = entry.runtime_data.daily("m1")[date(2026, 11, 1)]
    assert d.consumption == 3.0 and d.end_value is None  # verwendbarer Wert bleibt, auch ohne Statistik
    assert "m1" in entry.runtime_data.data.reaggregated_meters  # einmal neu aus der Statistik geholt
    assert entry.runtime_data.data.prices[0].calorific is None


async def test_subentry_flow_wallbox_and_reconfigure(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh", "device_class": "energy"})
    hass.states.async_set("sensor.wallbox", "120", {"unit_of_measurement": "kWh", "device_class": "energy"})
    entry = strom_entry()
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "strom"})
    r = await flow.async_configure(r["flow_id"], {"name": "Wallbox", "entity": "sensor.wallbox", "role": "wallbox"})
    r = await flow.async_configure(r["flow_id"], {"unit": "kWh"})
    assert r["step_id"] == "unterzaehler"
    r = await flow.async_configure(r["flow_id"], {"parent": "m1"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    rt = entry.runtime_data
    wb = next(m for m in rt.meters.values() if m.role == "wallbox")
    assert wb.parent_meter_id == "m1" and not rt.contracts(wb.meter_id)
    # Neu konfigurieren: Ersatzquelle setzen
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": "reconfigure", "subentry_id": "m1"})
    assert r["type"] is FlowResultType.MENU
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "stammdaten"})
    r = await flow.async_configure(r["flow_id"], {"name": "Strom", "history_entity": "sensor.zaehler", "annual_consumption": 3500})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    m1 = entry.runtime_data.meters["m1"]
    assert m1.history_entity == "sensor.zaehler" and m1.annual_consumption == 3500


def strom_sub(price=None, plan=None):
    sub = meter_subentry(
        "m1", "Strom", "strom", "kWh", entity="sensor.zaehler",
        contract={"supplier": "Stadtwerke", "start_date": "2026-06-30", "billing_rule": "fixed_day", "fixed_day": "30.06"},
        reading={"timestamp": "2026-06-30T00:00:00+02:00", "value": 5645.0, "quality": "real"},
    )
    sub["data"]["initial_price"] = price or {"work_price": 0.3154, "base_price": 13.09}
    sub["data"]["initial_plan"] = plan or {"amount": 165.0, "pay_day": 1, "rhythm": 1}
    return sub


# ---------------------------------------------------------------- Befunde der P3-Prüfung


async def test_snapshot_when_period_changes(hass: HomeAssistant, freezer) -> None:
    """Periodenende: letzter Stand der beendeten Periode wird eingefroren, auch nach Zählerstand-Änderungen."""
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    sub = meter_subentry(
        "m1", "Strom", "strom", "kWh", entity="sensor.zaehler",
        contract={"supplier": "SW", "start_date": "2025-11-14", "billing_rule": "contract_year"},
        reading={"timestamp": "2025-11-14T00:00:00+01:00", "value": 4000.0, "quality": "real"},
    )
    sub["data"]["initial_price"] = {"work_price": 0.3, "base_price": 10.0}
    sub["data"]["initial_plan"] = {"amount": 100.0, "pay_day": 1, "rhythm": 1}
    entry = make_entry(sub)
    assert await setup(hass, entry)
    old_pid = result(entry).period.period_id
    freezer.move_to("2026-11-14 00:00:10+01:00")
    hass.states.async_set("sensor.zaehler", "6650.0", {"unit_of_measurement": "kWh"})
    entry.runtime_data.coordinator.mark("m1", {"consumption"})
    await hass.async_block_till_done()
    assert result(entry).period.period_id != old_pid
    snaps = [s for s in entry.runtime_data.data.snapshots if s.period_id == old_pid]
    assert len(snaps) == 1 and snaps[0].quality in ("vorlaeufig", "gut", "sehr_gut", "annahme", "unzureichend")


async def test_rhythm_from_ui_string(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    await hass.services.async_call(DOMAIN, "set_abschlag", {"zaehler": dev, "ab": "2026-12-01", "betrag": 300.0, "rhythmus": "3"}, blocking=True)
    dates = [i.date for i in result(entry).payments.installments if i.date >= date(2026, 12, 1)]
    assert dates == [date(2026, 12, 1), date(2027, 3, 1), date(2027, 6, 1)]


async def test_total_balance_is_empty_when_a_meter_has_no_balance(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    strom = strom_sub()
    gas = meter_subentry("m2", "Gas", "gas", "m³", entity="sensor.gas",
                         contract={"supplier": "SW", "start_date": "2026-06-30", "billing_rule": "calendar_year"})
    entry = make_entry(strom, gas)
    assert await setup(hass, entry)
    total = hass.states.get("sensor.testhaus_total_balance")
    assert total.state == "unknown" and total.attributes["vollstaendig"] is False and "Gas" in total.attributes["ohne_prognose"]


async def test_unavailable_sensor_uses_yesterdays_end_value(hass: HomeAssistant) -> None:
    from custom_components.tarif_cockpit.engine.model import DailyConsumption
    from custom_components.tarif_cockpit.engine.quality import Quality

    hass.states.async_set("sensor.zaehler", "unavailable")
    entry = strom_entry()
    assert await setup(hass, entry)
    rt = entry.runtime_data
    assert result(entry).consumption.used is None  # kein stiller Rückfall auf den Startstand
    rt.put_daily([DailyConsumption("m1", date(2026, 11, 12), 5.0, end_value=6600.0, quality=Quality.REAL)])
    rt.changed(meter_id="m1")
    await hass.async_block_till_done()
    assert result(entry).consumption.used == pytest.approx(6600.0 - 5645.0)


async def test_gas_m3_flow_requires_calorific(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.zaehler", "6645.9", {"unit_of_measurement": "kWh"})
    entry = strom_entry()
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "gas"})
    r = await flow.async_configure(r["flow_id"], {"name": "Gas"})
    r = await flow.async_configure(r["flow_id"], {"unit": "m³"})
    assert r["errors"] == {"calorific": "required_for_m3"}
    r = await flow.async_configure(r["flow_id"], {"unit": "m³", "calorific": 11.3, "z_factor": 0.96})
    assert r["step_id"] == "vertrag"
