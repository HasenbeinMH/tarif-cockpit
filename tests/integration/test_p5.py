"""0.8: Wärmeerzeuger (Subentry, Sensoren, Coordinator), Fernwärme je MWh, WebSocket mit Erzeugern und Reihen."""

from __future__ import annotations

from datetime import date, timedelta

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.tarif_cockpit.const import DOMAIN, SUBENTRY_GENERATOR, SUBENTRY_METER
from custom_components.tarif_cockpit.engine.model import GeneratorDaily, GeneratorKind
from custom_components.tarif_cockpit.engine.quality import Quality

from .conftest import HOUSEHOLD, generator_subentry, make_entry, meter_device_id, meter_subentry, setup

HEATED = {**HOUSEHOLD, "situation": {"heating": ["gas", "kaminofen"], "hot_water": "heizung", "extras": [], "tenure": "eigentuemer", "rhythm": 1}}


def gas_sub():
    sub = meter_subentry("g1", "Gas", "gas", "kWh", entity="sensor.gas",
                         contract={"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year"})
    sub["data"]["initial_price"] = {"work_price": 0.10, "base_price": 15.0}
    sub["data"]["initial_plan"] = {"amount": 150.0, "pay_day": 1, "rhythm": 1}
    return sub


async def test_household_summary_names_generators(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "Haus", "heating": ["gas", "kaminofen"], "hot_water": "heizung", "tenure": "eigentuemer", "rhythm": "1"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"heating_limit": 15, "indoor_ref": 20})
    assert r["step_id"] == "abschluss"
    assert r["description_placeholders"]["erzeuger"] == "Gastherme, Kaminofen"


async def test_generator_flow_fireplace(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_sub(), household=HEATED)
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_GENERATOR), context={"source": SOURCE_USER})
    assert r["step_id"] == "user"
    kind_default = next(k.default() for k in r["data_schema"].schema if str(k) == "kind")
    assert kind_default == "gas_boiler"  # erster Vorschlag aus der Situation
    r = await flow.async_configure(r["flow_id"], {"kind": "fireplace", "name": "Kaminofen"})
    assert r["step_id"] == "leistung"  # Kaminofen: kein Zähler, keine Zuordnung
    r = await flow.async_configure(r["flow_id"], {"nominal_kw": 6, "efficiency": 0.75})
    assert r["step_id"] == "entitaeten"
    r = await flow.async_configure(r["flow_id"], {"room": "sensor.wohnzimmer"})
    assert r["step_id"] == "ofen"
    base = {"stove_threshold_k": 1.5, "effective_share": 0.6, "wood_price_unit": "rm", "kg_per_rm": 400}
    r = await flow.async_configure(r["flow_id"], {"stove_detection": "entity", **base})
    assert r["errors"] == {"stove_detection": "state_entity_missing"}
    r = await flow.async_configure(r["flow_id"], {"stove_detection": "room", "wood_price": 120, **base})
    assert r["step_id"] == "zusammenfassung" and "Ofenstunde" in r["description_placeholders"]["annahmen"]
    r = await flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    rt = hass.config_entries.async_get_entry(entry.entry_id).runtime_data
    gen = next(iter(rt.generators.values()))
    assert gen.kind == GeneratorKind.FIREPLACE and gen.stove_detection == "room" and gen.wood_price == 120.0
    assert gen.entities == {"room": "sensor.wohnzimmer"} and gen.meter_id is None


async def test_generator_flow_gas_boiler_on_own_meter_and_reconfigure(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_sub(), household=HEATED)
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_GENERATOR), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"kind": "gas_boiler", "name": "Therme"})
    assert r["step_id"] == "zuordnung"
    r = await flow.async_configure(r["flow_id"], {"source": "g1"})
    keys = {str(k): k for k in r["data_schema"].schema}
    assert "power_basis" in keys and keys["central_dhw"].default() is True  # Warmwasser über die Heizung
    r = await flow.async_configure(r["flow_id"], {"nominal_kw": 5, "min_kw": 8, "power_basis": "input", "efficiency": 0.9, "central_dhw": True})
    assert r["errors"] == {"min_kw": "min_above_nominal"}
    r = await flow.async_configure(r["flow_id"], {"nominal_kw": 20, "power_basis": "input", "efficiency": 0.9, "central_dhw": True})
    r = await flow.async_configure(r["flow_id"], {})
    assert r["step_id"] == "zusammenfassung" and "22,2 kWh" in r["description_placeholders"]["annahmen"]
    r = await flow.async_configure(r["flow_id"], {})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    sub_id = next(s for s, sub in entry.subentries.items() if sub.subentry_type == SUBENTRY_GENERATOR)
    gen = entry.runtime_data.generators[sub_id]
    assert gen.meter_id == "g1" and not gen.on_household_power and gen.central_dhw
    # Neu konfigurieren
    r = await flow.async_init((entry.entry_id, SUBENTRY_GENERATOR), context={"source": "reconfigure", "subentry_id": sub_id})
    r = await flow.async_configure(r["flow_id"], {"name": "Therme EG", "nominal_kw": 18, "power_basis": "output", "efficiency": 0.92, "central_dhw": True})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    gen = hass.config_entries.async_get_entry(entry.entry_id).runtime_data.generators[sub_id]
    assert gen.nominal_kw == 18.0 and gen.name == "Therme EG"


async def test_generator_sensors_and_websocket(hass: HomeAssistant, hass_ws_client) -> None:
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    stove = generator_subentry("o1", "fireplace", "Kaminofen", nominal_kw=6.0, efficiency=0.75, effective_share=0.6,
                               wood_price=0.3, wood_price_unit="kg", entities={"state": "binary_sensor.ofen"})
    entry = make_entry(gas_sub(), stove, household=HEATED)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    for i in range(5):
        d = date(2026, 11, 1) + timedelta(days=i)
        rt.put_generator_daily([GeneratorDaily("o1", d, energy_input=16.0, estimated_thermal_output=12.0,
                                               measurement_quality=Quality.ASSUMPTION, hours=2.0)])
    rt.coordinator.async_refresh_now()
    await hass.async_block_till_done()
    ent = er.async_get(hass)
    hours = ent.async_get_entity_id("sensor", DOMAIN, "o1_betriebsstunden")
    wood = ent.async_get_entity_id("sensor", DOMAIN, "o1_holzkosten_geschaetzt")
    assert float(hass.states.get(hours).state) == 10.0
    assert abs(float(hass.states.get(wood).state) - 80 / 4.2 * 0.3) < 0.05
    dev = dr.async_get(hass).async_get(meter_device_id(hass, "o1"))
    assert dev is not None and "Kaminofen" in dev.model
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "tarif_cockpit/zaehler"})
    msg = await client.receive_json()
    hh = msg["result"]["haushalte"][0]
    assert hh["waermeerzeuger"][0]["typ"] == "fireplace" and hh["waermeerzeuger"][0]["sensoren"]["betriebsstunden"] == hours
    assert hh["warmwasser"] == "heizung"
    await client.send_json({"id": 2, "type": "tarif_cockpit/reihen", "zaehler": "g1"})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["kosten"]["abschlaege"][-1][1] == 12 * 150.0
    await client.send_json({"id": 3, "type": "tarif_cockpit/reihen", "zaehler": "gibt_es_nicht"})
    msg = await client.receive_json()
    assert not msg["success"]


async def test_district_heating_price_per_mwh(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_sub(), household=HEATED)
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "fernwaerme"})
    r = await flow.async_configure(r["flow_id"], {"name": "Fernwärme"})
    r = await flow.async_configure(r["flow_id"], {"unit": "MWh"})
    r = await flow.async_configure(r["flow_id"], {"supplier": "FW", "start_date": "2026-01-01", "billing_rule": "calendar_year", "vat_mode": "gross", "vat_rate": 19})
    assert "price_unit" in {str(k) for k in r["data_schema"].schema}
    r = await flow.async_configure(r["flow_id"], {"price_unit": "mwh", "work_price": 120.0, "base_price": 20, "demand_price": 30, "demand_kw": 10})
    r = await flow.async_configure(r["flow_id"], {"amount": 100, "pay_day": 1, "rhythm": "1"})
    r = await flow.async_configure(r["flow_id"], {"value": 10.0, "timestamp": "2026-01-01 00:00:00", "quality": "real"})
    r = await flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    rt = hass.config_entries.async_get_entry(entry.entry_id).runtime_data
    fw = next(m for m in rt.meters.values() if m.medium.value == "fernwaerme")
    ids = {c.contract_id for c in rt.contracts(fw.meter_id)}
    seg = next(p for p in rt.data.prices if p.contract_id in ids)
    assert seg.work_price == 0.12 and seg.demand_price == 30.0 and seg.demand_kw == 10.0


# ---------------------------------------------------------------- Befunde der Prüfung (0.8)


def _gas_year(rt, stove_every=3):
    """Ein Jahr Gas-Tageswerte (Kennwert 6, WW 8) mit Ofentagen und Ofen-Tageswerten (bekannt: 0 oder 4 h)."""
    import math

    from custom_components.tarif_cockpit.engine.model import DailyConsumption

    start = date(2025, 11, 1)
    days, gens, heat = [], [], 0
    for i in range(377):
        d = start + timedelta(days=i)
        doy = d.timetuple().tm_yday
        t = 9.0 - 9.0 * math.cos(2 * math.pi * (doy - 20) / 365.0) + 1.5 * math.sin(doy * 0.9)
        dd = round(20.0 - t, 3) if t < 15 else 0.0
        v = 8.0 + 6.0 * dd
        h = 0.0
        if dd > 0:
            heat += 1
            if heat % stove_every == 0:
                h = 4.0
                v -= 6.0 * h
        days.append(DailyConsumption("g1", d, v, degree_days=dd, outdoor_temperature=t, quality=Quality.REAL))
        gens.append(GeneratorDaily("o1", d, hours=h if dd > 0 else 0.0, measurement_quality=Quality.ASSUMPTION))
    rt.put_daily(days)
    rt.put_generator_daily(gens)


async def test_stove_hours_reach_gas_model_and_scatter_survives_price_change(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    stove = generator_subentry("o1", "fireplace", "Kaminofen", nominal_kw=6.0, efficiency=0.75, effective_share=0.6,
                               entities={"state": "binary_sensor.ofen"})
    entry = make_entry(gas_sub(), stove, household=HEATED)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    _gas_year(rt)
    rt.changed(meter_id="g1")
    res = rt.coordinator.results["g1"]
    m = res.heat_model
    assert m.usable and abs(m.heat_coefficient - 6.0) < 0.1 and abs(m.stove_coefficient - 6.0) < 0.2
    assert abs(m.hot_water_baseload - 8.0) < 0.2  # Warmwasser über die Heizung (Situation)
    assert res.samples
    # nur eine Preisänderung: kein Refit, Streudiagramm bleibt gefüllt
    rt.set_price("g1", date(2026, 12, 1), work_price=0.12, base_price=15.0)
    rt.changed(meter_id="g1", flags={"costs"})
    assert rt.coordinator.results["g1"].samples
    from custom_components.tarif_cockpit.websocket import build_series
    assert build_series(hass, "g1")["streuung"]["punkte"]
    assert rt.coordinator.gen_results["o1"].avoided_energy is not None


async def test_hot_water_by_instantaneous_heater_switches_off_ww_term(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    hh = {**HEATED, "situation": {**HEATED["situation"], "hot_water": "strom"}}
    entry = make_entry(gas_sub(), household=hh)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    _gas_year(rt, stove_every=10**6)
    rt.changed(meter_id="g1")
    m = rt.coordinator.results["g1"].heat_model
    assert m.hot_water_baseload == 0.0 and "ww_aus" in m.flags
    assert rt.coordinator.hot_water_on(rt.meters["g1"]) is False


async def test_generator_flow_heat_pump_defaults_and_stove_needs_entity(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    strom = meter_subentry("s1", "Strom", "strom", "kWh", contract={"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year"})
    entry = make_entry(gas_sub(), strom, household=HEATED)
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_GENERATOR), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"kind": "water_hp"})  # ohne Namen: Name der Art
    assert r["step_id"] == "zuordnung"
    assert next(k.default() for k in r["data_schema"].schema if str(k) == "source") == "haushaltsstrom"
    r = await flow.async_configure(r["flow_id"], {"source": "s1"})
    r = await flow.async_configure(r["flow_id"], {"nominal_kw": 8, "cop": 3.5, "central_dhw": True})
    r = await flow.async_configure(r["flow_id"], {})
    assert "gilt komplett als Heizstrom" in r["description_placeholders"]["annahmen"]
    r = await flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY and r["title"] == "Wärmepumpe"
    await hass.async_block_till_done()
    # Kaminofen ohne Betriebszustand und Raumtemperatur: Fehler schon bei den Messwerten
    r = await flow.async_init((entry.entry_id, SUBENTRY_GENERATOR), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"kind": "fireplace", "name": "Ofen"})
    r = await flow.async_configure(r["flow_id"], {"nominal_kw": 6, "efficiency": 0.75})
    r = await flow.async_configure(r["flow_id"], {})
    assert r["step_id"] == "entitaeten" and r["errors"] == {"base": "stove_entity_required"}


async def test_generator_reconfigure_checks_min_and_daily_merge(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    boiler = generator_subentry("b1", "gas_boiler", "Therme", meter_id="g1", nominal_kw=20.0, efficiency=0.9, power_basis="output")
    entry = make_entry(gas_sub(), boiler, household=HEATED)
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_GENERATOR), context={"source": "reconfigure", "subentry_id": "b1"})
    r = await flow.async_configure(r["flow_id"], {"name": "Therme", "nominal_kw": 10, "min_kw": 12, "power_basis": "output", "efficiency": 0.9, "central_dhw": True})
    assert r["errors"] == {"min_kw": "min_above_nominal"}
    rt = entry.runtime_data
    d = date(2026, 11, 1)
    rt.put_generator_daily([GeneratorDaily("b1", d, energy_input=50.0, hours=6.0, measurement_quality=Quality.REAL)])
    rt.put_generator_daily([GeneratorDaily("b1", d, energy_input=52.0, measurement_quality=Quality.REAL)])  # Stunden nicht mehr im Recorder
    g = rt.generator_daily("b1")[d]
    assert g.energy_input == 52.0 and g.hours == 6.0
