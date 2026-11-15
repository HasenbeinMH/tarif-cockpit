"""1.2: Stundenwerte, Viertelstunden und Preise, Zeitfenster (Dialog, Aktion), Vergleich dynamisch, Leckage, Speicher 1.6."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from custom_components.tarif_cockpit.aggregation import prices_from_attribute
from custom_components.tarif_cockpit.const import DOMAIN, EVENT_LEAK, ISSUE_LEAK
from custom_components.tarif_cockpit.engine.model import DailyConsumption, DayIntervals
from custom_components.tarif_cockpit.engine.quality import Quality
from custom_components.tarif_cockpit.engine.windows import slot_starts

from .conftest import make_entry, meter_device_id, meter_subentry, setup
from .test_init import KEY, stored

TZ = ZoneInfo("Europe/Berlin")


def strom(entity=None, **meter):
    sub = meter_subentry("s1", "Strom", "strom", "kWh", entity=entity,
                         contract={"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year"},
                         reading={"timestamp": "2026-01-01T00:00:00+01:00", "value": 1000.0, "quality": "real"})
    sub["data"]["initial_price"] = {"work_price": 0.30, "base_price": 10.0}
    sub["data"]["meter"].update(meter)
    return sub


async def _call(hass, service, data):
    return await hass.services.async_call(DOMAIN, service, data, blocking=True, return_response=True)


def _eid(hass, uid, domain="sensor"):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, uid)


async def test_htnt_dialog_creates_window_sensor(hass: HomeAssistant) -> None:
    entry = make_entry(strom())
    assert await setup(hass, entry)
    assert _eid(hass, "s1_zeitfenster") is None
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "s1"})
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "preis_aendern"})
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-11-01", "work_price": 25.0, "base_price": 10.0, "windows_14a": True})
    assert r["step_id"] == "zeitfenster"
    r = await flow.async_configure(r["flow_id"], {"mode": "htnt", "ht_start": "6:0x", "ht_end": "22:00", "ht_price": 35.0})
    assert r["errors"] == {"ht_start": "time_format"}
    r = await flow.async_configure(r["flow_id"], {"mode": "htnt", "ht_start": "06:00", "ht_end": "22:00", "ht_price": 35.0,
                                                 "ht_days": ["0", "1", "2", "3", "4"], "rebate_14a": 110.0})
    assert r["reason"] == "price_saved"
    await hass.async_block_till_done()  # neu geladen: Sensor „Zeitfenster“ kommt dazu
    rt = entry.runtime_data
    seg = next(p for p in rt.data.prices if p.valid_from == date(2026, 11, 1))
    assert seg.work_price == 0.25 and seg.windows[0].work_price == 0.35 and seg.windows[0].weekdays == [0, 1, 2, 3, 4]
    assert seg.rebate_yearly == 110.0
    assert _eid(hass, "s1_zeitfenster") is not None
    # „Preis ändern“ ohne Haken: Fenster bleiben, der Schritt folgt trotzdem (vorbelegt)
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "s1"})
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "preis_aendern"})
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-11-10", "work_price": 26.0, "base_price": 10.0})
    assert r["step_id"] == "zeitfenster"


async def test_set_preis_with_windows_and_dynamic(hass: HomeAssistant) -> None:
    entry = make_entry(strom())
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "s1")
    await _call(hass, "set_preis", {"zaehler": dev, "ab": date(2026, 11, 1), "arbeitspreis": 0.30, "grundpreis": 10.0,
                                    "fenster": [{"name": "NT", "von": "22:00", "bis": "06:00", "monate": [1, 2, 3], "aufschlag": -0.08}],
                                    "dynamisch_entitaet": "sensor.epex", "dynamisch_aufschlag": 0.15})
    await hass.async_block_till_done()
    seg = next(p for p in entry.runtime_data.data.prices if p.valid_from == date(2026, 11, 1))
    assert seg.windows[0].delta == -0.08 and seg.windows[0].months == [1, 2, 3]
    assert seg.dynamic.entity == "sensor.epex" and seg.dynamic.markup == 0.15
    assert _eid(hass, "s1_mittelpreis") is not None and _eid(hass, "s1_zeitfenster") is not None


def test_prices_from_epex_attribute():
    day = date(2026, 11, 14)
    items = [{"start_time": q.astimezone(TZ).isoformat(), "end_time": (q + timedelta(minutes=15)).astimezone(TZ).isoformat(),
              "price_per_kwh": 0.10 + i / 1000} for i, q in enumerate(slot_starts(day, TZ, 15))]
    out = prices_from_attribute({"data": items[:-1] + items[-1:]}, None, TZ)
    assert list(out) == [day] and len(out[day]) == 96 and abs(out[day][5] - 0.105) < 1e-9
    partial = prices_from_attribute({"data": items[:50]}, None, TZ)
    assert partial == {}  # unvollständiger Tag wird nicht gespeichert
    hourly = [{"startsAt": h.astimezone(TZ).isoformat(), "total": 0.30} for h in slot_starts(day, TZ, 60)]
    assert prices_from_attribute({"today": hourly}, None, TZ)[day][3] == 0.30  # Tibber-Format, je Stunde


async def test_intervals_prices_and_comparison(hass: HomeAssistant) -> None:
    entry = make_entry(strom("sensor.strom", comparison={"entity": "sensor.epex", "markup": 0.15, "attribute": None},
                             comparison_base_price=12.0))
    assert await setup(hass, entry)
    rt = entry.runtime_data
    assert _eid(hass, "s1_vergleich_dynamisch") is not None
    y = rt.today() - timedelta(days=1)
    hass.states.async_set("sensor.epex", "0.12", {"unit_of_measurement": "ct/kWh", "data": [
        {"start_time": q.astimezone(TZ).isoformat(), "price_per_kwh": 10.0} for q in slot_starts(y, TZ, 15)]})
    agg = rt.aggregator

    async def fake_fetch(ids, start, end, kind, units=None, period="hour"):
        assert period == "5minute"
        t, out, v = start, {}, 0.0
        while t <= end:
            out[t] = v
            v += 0.1
            t += timedelta(minutes=5)
        return {"sensor.strom": out}

    agg._fetch = fake_fetch
    assert await agg.async_run_intervals(days_back=1) == 2
    energy = rt.day_intervals("s1", "energy")[y]
    price = rt.day_intervals("sensor.epex", "price")[y]
    assert len(energy) == 96 and abs(energy[0] - 0.3) < 1e-9 and price[0] == 0.10  # ct → €
    # Tageswert und Zählerstand dazu, dann rechnet der Vergleich
    hass.states.async_set("sensor.strom", "4000", {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"})
    rt.put_daily([DailyConsumption("s1", y, consumption=28.8, quality=Quality.REAL, hourly=[1.2] * 24)])
    rt.changed()
    await hass.async_block_till_done()
    cmp_ = rt.coordinator.results["s1"].comparison
    assert cmp_.days == 1 and cmp_.interval_days == 1
    own = 28.8 * 0.30 + 10.0 * 12 / 365.25
    dyn = 28.8 * 0.25 + 12.0 * 12 / 365.25
    assert abs(cmp_.diff - (own - dyn)) < 1e-3  # je Tag auf 4 Stellen gerundet
    st = hass.states.get(_eid(hass, "s1_vergleich_dynamisch"))
    assert abs(float(st.state) - round(own - dyn, 2)) < 0.011 and st.attributes["tage"] == 1


async def test_leak_issue_event_and_binary_sensor(hass: HomeAssistant) -> None:
    events = []
    hass.bus.async_listen(EVENT_LEAK, callback(lambda e: events.append(e.data)))
    sub = meter_subentry("w1", "Wasser", "wasser", "m³", entity="sensor.wasser",
                         contract={"supplier": "WW", "start_date": "2026-01-01", "billing_rule": "calendar_year"})
    entry = make_entry(sub)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    eid = _eid(hass, "w1_leckage", "binary_sensor")
    assert eid is not None
    today = rt.today()
    drip = [0.008] * 24  # 8 L/h rund um die Uhr
    rt.put_daily([DailyConsumption("w1", today - timedelta(days=i), consumption=0.192, quality=Quality.REAL, hourly=drip) for i in range(1, 5)])
    rt.coordinator.check_leaks()
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_LEAK}_w1") is not None
    assert hass.states.get(eid).state == "on" and len(events) == 1 and events[0]["art"] == "nachtminimum"
    rt.coordinator.check_leaks()
    await hass.async_block_till_done()
    assert len(events) == 1  # je Verdacht nur einmal
    normal = [0.0] * 6 + [0.02] * 16 + [0.0] * 2
    rt.put_daily([DailyConsumption("w1", today - timedelta(days=i), consumption=0.32, quality=Quality.REAL, hourly=normal) for i in range(1, 5)])
    rt.coordinator.check_leaks()
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_LEAK}_w1") is None and hass.states.get(eid).state == "off"


async def test_stammdaten_comparison_and_cooling_limit(hass: HomeAssistant) -> None:
    entry = make_entry(strom("sensor.strom"))
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "s1"})
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "stammdaten"})
    assert "comparison_entity" in r["data_schema"].schema
    r = await flow.async_configure(r["flow_id"], {"name": "Strom", "comparison_entity": "sensor.epex_market", "comparison_markup": 15.0,
                                                 "comparison_base": 12.0})
    assert r["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    m = entry.runtime_data.meters["s1"]
    assert m.comparison.entity == "sensor.epex_market" and m.comparison.markup == 0.15 and m.comparison_base_price == 12.0
    assert _eid(hass, "s1_vergleich_dynamisch") is not None


async def test_store_migration_1_5_to_1_6(hass: HomeAssistant, hass_storage) -> None:
    hass_storage[KEY] = stored(minor=5)
    entry = make_entry(meter_subentry("m1"), store_created=True)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    assert rt.data.day_intervals == [] and rt.data.leaks_notified == []
    rt.put_day_interval(DayIntervals("m1", date(2026, 11, 12), "energy", 15, [0.1] * 96, "5minute"))
    rt.changed()
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[KEY]["minor_version"] == 6 and len(hass_storage[KEY]["data"]["day_intervals"]) == 1


async def test_history_prices_sampled_mid_quarter(hass: HomeAssistant) -> None:
    """Preis-Sensoren schalten kurz nach der Grenze um: es gilt der Wert in der Mitte der Viertelstunde."""
    entry = make_entry(strom("sensor.strom", comparison={"entity": "sensor.preis", "markup": 0.0, "attribute": None}))
    assert await setup(hass, entry)
    agg = entry.runtime_data.aggregator
    y = entry.runtime_data.today() - timedelta(days=1)
    starts = slot_starts(y, TZ, 15)
    changes = [(starts[0] - timedelta(minutes=5), 0.05)] + [(q + timedelta(seconds=3), 0.10 + i / 1000) for i, q in enumerate(starts)]

    async def fake_changes(entity_id, start, end):
        return [(t.astimezone(TZ), v) for t, v in changes]

    agg._numeric_changes = fake_changes
    vals = await agg._prices_from_history("sensor.preis", y)
    assert abs(vals[0] - 0.10) < 1e-9 and abs(vals[10] - 0.11) < 1e-9


async def test_leak_event_once_while_persisting(hass: HomeAssistant, freezer) -> None:
    events = []
    hass.bus.async_listen(EVENT_LEAK, callback(lambda e: events.append(e.data)))
    sub = meter_subentry("w1", "Wasser", "wasser", "m³", entity="sensor.wasser",
                         contract={"supplier": "WW", "start_date": "2026-01-01", "billing_rule": "calendar_year"})
    entry = make_entry(sub)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    for step in range(5):  # fünf Tage Dauertropfen
        today = rt.today()
        rt.put_daily([DailyConsumption("w1", today - timedelta(days=i), consumption=0.192, quality=Quality.REAL, hourly=[0.008] * 24)
                      for i in range(1, 5)])
        rt.coordinator.check_leaks()
        await hass.async_block_till_done()
        freezer.tick(timedelta(days=1))
    assert len(events) == 1


async def test_custom_service_windows_kept_by_dialog(hass: HomeAssistant) -> None:
    entry = make_entry(strom())
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "s1")
    await _call(hass, "set_preis", {"zaehler": dev, "ab": date(2026, 11, 1), "arbeitspreis": 0.30, "grundpreis": 10.0,
                                    "fenster": [{"name": "Mittag", "von": "11:00", "bis": "14:00", "monate": [1, 2], "aufschlag": -0.05}]})
    await hass.async_block_till_done()
    flow = hass.config_entries.subentries
    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "s1"})
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "preis_aendern"})
    r = await flow.async_configure(r["flow_id"], {"valid_from": "2026-11-10", "work_price": 31.0, "base_price": 10.0})
    assert r["reason"] == "price_saved"  # Schritt übersprungen, eigene Fenster unverändert
    seg = next(p for p in entry.runtime_data.data.prices if p.valid_from == date(2026, 11, 10))
    assert seg.work_price == 0.31 and seg.windows[0].name == "Mittag" and seg.windows[0].months == [1, 2]

