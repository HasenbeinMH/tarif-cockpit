"""0.9: Impulszähler im Dialog, Abgleich mit Ablesungen (Aktion, Reparatur, Sensor), Stand mit Impulskonstante, Gasleistung."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from custom_components.tarif_cockpit.const import DOMAIN, ISSUE_RECONCILE, SUBENTRY_METER
from custom_components.tarif_cockpit.engine.model import DailyConsumption
from custom_components.tarif_cockpit.engine.quality import Quality

from .conftest import HOUSEHOLD, make_entry, meter_device_id, meter_subentry, setup

TZ = ZoneInfo("Europe/Berlin")


def gas_meter(entity="sensor.gas", pulse=None):
    sub = meter_subentry("g1", "Gas", "gas", "kWh", entity=entity,
                         contract={"supplier": "SW", "start_date": "2026-09-01", "billing_rule": "calendar_year"},
                         reading={"timestamp": "2026-09-01T00:00:00+02:00", "value": 1000.0, "quality": "real"})
    if pulse:
        sub["data"]["meter"].update(pulse_constant=pulse[0], pulse_mode=pulse[1])
    sub["data"]["initial_price"] = {"work_price": 0.1, "base_price": 10.0}
    return sub


def _sensor_days(rt, n=70, per_day=10.0, ratio=0.95, start_sensor=500.0):
    d0 = date(2026, 9, 1)
    s = start_sensor
    days = [DailyConsumption("g1", d0 - timedelta(days=1), per_day * ratio, end_value=s, quality=Quality.REAL)]
    for i in range(n):
        s += per_day * ratio
        days.append(DailyConsumption("g1", d0 + timedelta(days=i), per_day * ratio, end_value=s, quality=Quality.REAL))
    rt.put_daily(days)


async def test_pulse_meter_flow(hass: HomeAssistant) -> None:
    hass.states.async_set("counter.gas_impulse", "12345")
    entry = make_entry(household={**HOUSEHOLD, "situation": {"heating": ["gas"], "hot_water": "heizung", "extras": [], "tenure": "eigentuemer", "rhythm": 1}})
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, SUBENTRY_METER), context={"source": SOURCE_USER})
    r = await flow.async_configure(r["flow_id"], {"medium": "gas"})
    r = await flow.async_configure(r["flow_id"], {"name": "Gas", "entity": "sensor.x", "pulse_entity": "counter.gas_impulse"})
    assert r["errors"] == {"base": "entity_or_pulses"}
    r = await flow.async_configure(r["flow_id"], {"name": "Gas", "pulse_entity": "counter.gas_impulse"})
    assert r["step_id"] == "einheit" and "pulse_constant" in {str(k) for k in r["data_schema"].schema}
    r = await flow.async_configure(r["flow_id"], {"unit": "m³", "calorific": 11.4, "z_factor": 0.95, "pulse_constant": 0.01, "pulse_mode": "per_pulse"})
    r = await flow.async_configure(r["flow_id"], {"supplier": "SW", "start_date": "2026-09-01", "billing_rule": "calendar_year", "vat_mode": "gross", "vat_rate": 19})
    r = await flow.async_configure(r["flow_id"], {"work_price": 0.1, "base_price": 10})
    r = await flow.async_configure(r["flow_id"], {"pay_day": 1, "rhythm": "1"})
    r = await flow.async_configure(r["flow_id"], {"quality": "real"})
    r = await flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    rt = hass.config_entries.async_get_entry(entry.entry_id).runtime_data
    m = next(iter(rt.meters.values()))
    assert m.entity == "counter.gas_impulse" and m.pulse_constant == 0.01 and m.pulse_mode == "per_pulse" and m.data_level == 2
    # aktueller Stand = Impulse × 0,01 m³
    assert rt.coordinator.sensor_raw(m.meter_id) == 123.45


async def test_reconcile_via_reading_service_issue_and_sensor(hass: HomeAssistant) -> None:
    """Abnahme P6 in der Integration: verlorene Impulse (5 %) → Ablesung per Aktion → angeglichen, Hinweis, Sensor."""
    hass.config.language = "de"
    hass.states.async_set("sensor.gas", "1165", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_meter(), household=HOUSEHOLD)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    _sensor_days(rt)
    # Ablesung zum 01.10. (30 Tage × 10 = 300 echte Einheiten, der Sensor zählte 285)
    await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": meter_device_id(hass, "g1"), "stand": 1300.0,
                                                           "zeitpunkt": datetime(2026, 10, 1, tzinfo=TZ)}, blocking=True, return_response=True)
    await hass.async_block_till_done()
    daily = rt.daily("g1")
    assert sum(daily[date(2026, 9, 1) + timedelta(days=i)].consumption for i in range(30)) == 300.0 or \
        abs(sum(daily[date(2026, 9, 1) + timedelta(days=i)].consumption for i in range(30)) - 300.0) < 1e-6
    assert "abgeglichen" in daily[date(2026, 9, 10)].quality_flags
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_RECONCILE}_g1")
    assert issue is not None and issue.translation_placeholders["pct"] == "-5,0"
    ent = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "g1_abgleich")
    state = hass.states.get(ent)
    assert float(state.state) == -5.0 and state.attributes["angeglichen"] is True and abs(state.attributes["fehlende_menge"] - 15.0) < 1e-6
    # nächste Ablesung passt zum Sensor (≤ 2 %): Hinweis verschwindet
    await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": meter_device_id(hass, "g1"), "stand": 1300.0 + 30 * 9.5 * 1.01,
                                                           "zeitpunkt": datetime(2026, 10, 31, tzinfo=TZ)}, blocking=True, return_response=True)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_RECONCILE}_g1") is None


async def test_sensor_value_stored_with_reading_now_and_offset(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gas", "1165", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_meter(), household=HOUSEHOLD)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    _sensor_days(rt)
    await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": meter_device_id(hass, "g1"), "stand": 1700.0},
                                   blocking=True, return_response=True)
    await hass.async_block_till_done()
    last = rt.readings("g1")[-1]
    assert last.sensor_value == 1165.0
    rec = rt.coordinator.reconciliations["g1"]
    assert rec.offset == 1700.0 - 1165.0
    res = rt.coordinator.results["g1"]
    assert "abgleich_offset" in res.consumption.flags and res.consumption.used == 700.0


async def test_gas_power_from_pulses(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set("sensor.gas_impulse", "0")
    entry = make_entry(gas_meter("sensor.gas_impulse", pulse=(100.0, "per_unit")), household=HOUSEHOLD)
    assert await setup(hass, entry)
    t = dt0 = datetime(2026, 11, 13, 12, tzinfo=TZ)
    for i in range(1, 6):  # 10 kWh/m³ (kWh-Zähler: Faktor 1) → 1 Impuls (0,01) je 36 s = 1 kWh/h
        t = dt0 + timedelta(seconds=36 * i)
        freezer.move_to(t)
        hass.states.async_set("sensor.gas_impulse", str(i))
        await hass.async_block_till_done()
    rt = entry.runtime_data
    assert abs(rt.coordinator.gas_power("g1") - 1.0) < 0.01
    ent = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "g1_gasleistung")
    assert ent is not None
    freezer.move_to(t + timedelta(minutes=10))
    assert rt.coordinator.gas_power("g1") == 0.0



async def test_pulse_counter_reset_continues(hass: HomeAssistant, freezer) -> None:
    """Der Impulszähler startet neu (Stand fällt auf 0): der Stand läuft weiter, kein Rückwärts-Verbrauch."""
    hass.states.async_set("sensor.gas_impulse", "120000")
    entry = make_entry(gas_meter("sensor.gas_impulse", pulse=(100.0, "per_unit")), household=HOUSEHOLD)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    hass.states.async_set("sensor.gas_impulse", "120500")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=5))
    hass.states.async_set("sensor.gas_impulse", "300")  # Neustart des ESP
    await hass.async_block_till_done()
    assert len(rt.data.sensor_resets) == 1 and rt.data.sensor_resets[0].prev_raw == 1205.0
    assert rt.coordinator.sensor_raw("g1") == 1205.0 + 3.0


async def test_reconcile_on_start_without_new_days_and_english_placeholders(hass: HomeAssistant) -> None:
    hass.config.language = "en"
    hass.states.async_set("sensor.gas", "1165", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_meter(), household=HOUSEHOLD)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    _sensor_days(rt)
    rt.add_reading("g1", datetime(2026, 10, 1, tzinfo=TZ), 1300.0)
    await rt.aggregator.async_run(start=date(2026, 9, 1), end=date(2026, 9, 1))  # keine neuen Tage
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_RECONCILE}_g1")
    assert issue is not None and issue.translation_placeholders["pct"] == "-5.0" and issue.translation_placeholders["angeglichen"] == "yes"
    assert issue.translation_placeholders["von"] == "2026-09-01"


async def test_recalculate_keeps_burner_data(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.gas", "1165", {"unit_of_measurement": "kWh"})
    entry = make_entry(gas_meter(), household=HOUSEHOLD)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    d = date(2026, 9, 5)
    rt.put_daily([DailyConsumption("g1", d, 9.0, end_value=540.0, heating_hours=3.5, burner_starts=7, quality=Quality.REAL)])
    rt.put_daily([DailyConsumption("g1", d, 9.1, end_value=540.1, quality=Quality.REAL)])  # Verlauf schon gelöscht
    v = rt.daily("g1")[d]
    assert v.consumption == 9.1 and v.heating_hours == 3.5 and v.burner_starts == 7
