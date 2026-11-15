"""1.2: Zeitfenster (HT/NT, § 14a), dynamischer Tarif, Vergleich, Kühlgradtage, Leckage, Stundenwerte."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.balance import cooling_forecast
from engine.billing import calculate_costs
from engine.compare import compare_dynamic
from engine.consumption import aggregate_day
from engine.degree_days import cooling_degree_days
from engine.leak import detect_leak
from engine.model import (
    BillingRule, Contract, DailyConsumption, DynamicPrice, Medium, Meter, PriceSegment, PriceWindow, Rounding, VatMode,
)
from engine.quality import Quality
from engine.windows import day_slots, price_at, slot_starts, typical_profile, window_usage

TZ = ZoneInfo("Europe/Berlin")
STROM = Meter("m1", Medium.STROM, "kWh", entity="sensor.x", data_level=2)
WASSER = Meter("w1", Medium.WASSER, "m³", entity="sensor.w", data_level=2)
C = Contract("c1", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR)


def dt(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=TZ)


HTNT = PriceSegment("c1", date(2026, 1, 1), 0.25, 0.0,  # NT = Arbeitspreis
                    windows=[PriceWindow("HT", "06:00", "22:00", [0, 1, 2, 3, 4], work_price=0.35)])


# ---------------------------------------------------------------- Fenster


def test_price_at_weekdays_midnight_months_delta():
    assert price_at(HTNT, dt(2026, 11, 16, 7)) == (0.35, "HT")  # Montag
    assert price_at(HTNT, dt(2026, 11, 16, 23)) == (0.25, "standard")
    assert price_at(HTNT, dt(2026, 11, 15, 12)) == (0.25, "standard")  # Sonntag
    m3 = PriceSegment("c1", date(2026, 1, 1), 0.30, 0.0, windows=[
        PriceWindow("NT", "22:00", "06:00", months=[1, 2, 3], delta=-0.08),  # über Mitternacht, nur Q1
        PriceWindow("HT", "17:00", "20:00", months=[1, 2, 3], delta=0.05),
    ])
    assert price_at(m3, dt(2026, 2, 3, 23))[0] == pytest.approx(0.22)
    assert price_at(m3, dt(2026, 2, 4, 3))[0] == pytest.approx(0.22)
    assert price_at(m3, dt(2026, 2, 4, 18))[0] == pytest.approx(0.35)
    assert price_at(m3, dt(2026, 7, 4, 23))[0] == pytest.approx(0.30)  # Q3: kein Fenster


def test_day_slots_sources_and_dst():
    assert len(slot_starts(date(2026, 3, 29), TZ, 15)) == 92 and len(slot_starts(date(2026, 10, 25), TZ, 60)) == 25
    hourly = [1.0] * 24
    sl = day_slots(date(2026, 11, 16), 48.0, TZ, hourly=hourly)
    assert sl.source == "hour" and sum(sl.qty) == pytest.approx(48.0)  # auf den Tageswert skaliert
    q = [0.25] * 96
    assert day_slots(date(2026, 11, 16), 24.0, TZ, hourly=hourly, intervals=q).source == "interval"
    prof = [0.0] * 24
    prof[12] = 1.0
    sl = day_slots(date(2026, 11, 16), 10.0, TZ, profile=prof)
    assert sl.source == "profil" and sl.qty[12] == pytest.approx(10.0)
    assert day_slots(date(2026, 11, 16), 24.0, TZ).source == "gleich"


def test_costs_with_htnt_match_hourly_sum_and_fallback():
    day = date(2026, 11, 16)  # Montag
    hourly = {day: [1.0] * 24}
    cb = calculate_costs(C, [HTNT], STROM, {day: 24.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, hourly=hourly)
    assert cb.energy == pytest.approx(16 * 0.35 + 8 * 0.25)
    usage, src = window_usage({day: 24.0}, lambda d: HTNT, TZ, hourly)
    assert usage == {"HT": pytest.approx(16.0), "standard": pytest.approx(8.0)} and src == {"hour"}
    gu = calculate_costs(C, [HTNT], STROM, {day: 24.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ)
    assert "fenster_geschaetzt" in gu.flags and gu.energy == pytest.approx(16 * 0.35 + 8 * 0.25)  # gleichmäßig
    profile = typical_profile([(day - timedelta(days=i), [0.0] * 6 + [2.0] * 16 + [0.0] * 2) for i in range(1, 8)], TZ)
    pc = calculate_costs(C, [HTNT], STROM, {day: 24.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, profile=profile)
    assert pc.energy == pytest.approx(24 * 0.35)  # alles im HT laut Profil


def test_rebate_14a_module1():
    seg = PriceSegment("c1", date(2026, 1, 1), 0.30, 10.0, rebate_yearly=110.0, rounding=Rounding(days_per_year="365"))
    cb = calculate_costs(C, [seg], STROM, {}, dt(2026, 1, 1), dt(2027, 1, 1), TZ)
    assert cb.rebate == pytest.approx(110.0) and cb.total == pytest.approx(120.0 - 110.0)


# ---------------------------------------------------------------- dynamisch und Vergleich


def _prices(day, value_of):
    return [value_of(i) for i in range(len(slot_starts(day, TZ, 15)))]


def test_dynamic_quarter_hours_and_fallbacks():
    day = date(2026, 11, 16)
    seg = PriceSegment("c1", date(2026, 1, 1), 0.0, 0.0, dynamic=DynamicPrice("sensor.epex", markup=0.15))
    intervals = {day: [0.0] * 40 + [1.0] * 8 + [0.0] * 48}  # 8 kWh 10:00–12:00
    prices = {day: _prices(day, lambda i: 0.10 if i < 44 else 0.20)}
    cb = calculate_costs(C, [seg], STROM, {day: 8.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, intervals=intervals, prices=prices)
    assert cb.energy == pytest.approx(4 * (0.10 + 0.15) + 4 * (0.20 + 0.15))
    holes = {day: [None if 40 <= i < 44 else p for i, p in enumerate(prices[day])]}
    cb2 = calculate_costs(C, [seg], STROM, {day: 8.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, intervals=intervals, prices=holes)
    assert "preis_geschaetzt" in cb2.flags and cb2.complete
    rest = calculate_costs(C, [seg], STROM, {day + timedelta(days=5): 10.0}, dt(2026, 11, 21), dt(2026, 11, 21), TZ, dynamic_mean=0.12)
    assert "dynamisch_mittel" in rest.flags and rest.energy == pytest.approx(10 * 0.27)
    none = calculate_costs(C, [seg], STROM, {day + timedelta(days=5): 10.0}, dt(2026, 11, 21), dt(2026, 11, 21), TZ)
    assert "preis_fehlt" in none.flags and not none.complete


def test_compare_dynamic_only_days_with_prices():
    d1, d2 = date(2026, 11, 16), date(2026, 11, 17)
    seg = PriceSegment("c1", date(2026, 1, 1), 0.3154, 13.09)
    prices = {d1: _prices(d1, lambda i: 0.10)}
    cmp_ = compare_dynamic(STROM, DynamicPrice("sensor.epex", markup=0.15), 12.0, C, [seg], {d1: 10.0, d2: 10.0}, TZ,
                           {d1: [10 / 24] * 24}, None, prices, None, forecast_total=3650.0)
    assert cmp_.days == 1 and cmp_.days_total == 2 and cmp_.interval_days == 0 and "teils_stuendlich" in cmp_.flags
    own = 10 * 0.3154 + 13.09 * 12 / 365.25
    dyn = 10 * 0.25 + 12.0 * 12 / 365.25
    assert cmp_.cost_actual == pytest.approx(own, abs=1e-3) and cmp_.cost_dynamic == pytest.approx(dyn, abs=1e-3)
    assert cmp_.diff == pytest.approx(own - dyn, abs=1e-3) and cmp_.projected_diff == pytest.approx((own - dyn) / 10 * 3650, rel=1e-3)
    assert compare_dynamic(STROM, DynamicPrice("x"), None, C, [seg], {d2: 5.0}, TZ, None, None, {}, None).flags == ["keine_preise"]


# ---------------------------------------------------------------- Kühlgradtage


def test_cooling_degree_days_and_forecast():
    assert cooling_degree_days(25.0) == 3.0 and cooling_degree_days(20.0) == 0.0 and cooling_degree_days(None) is None
    today = date(2026, 6, 15)
    daily, meas = {}, {}
    for i in range(400):
        d = today - timedelta(days=400 - i)
        t = 27.0 if d.month in (6, 7, 8) else 15.0
        daily[d] = DailyConsumption("m1", d, degree_days=0.0, outdoor_temperature=t, cooling_degree_days=cooling_degree_days(t, 22.0))
        meas[d] = 0.2 + (1.5 * 5.0 if d.month in (6, 7, 8) else 0.0)  # 1,5 kWh je Kühlgradtag + 0,2 Standby
    fc = cooling_forecast(meas, daily, today, date(2026, 8, 31), today)
    assert fc is not None and fc.details["kuehlkennwert"] == pytest.approx(1.5)
    assert fc.rest == pytest.approx(1.5 * 5.0 * 78, rel=0.05)  # 15.06.–31.08. wie im Vorjahr


# ---------------------------------------------------------------- Leckage


def _wday(day, per_hour):
    return DailyConsumption("w1", day, consumption=sum(per_hour) / 1000, quality=Quality.REAL, hourly=[v / 1000 for v in per_hour])


def test_leak_night_minimum_continuous_and_garden():
    today = date(2026, 11, 16)
    normal = [0, 0, 0, 0, 0, 0, 30, 40, 10, 0, 0, 5, 20, 0, 0, 0, 0, 10, 30, 20, 10, 5, 0, 0]
    ok = {today - timedelta(days=i): _wday(today - timedelta(days=i), normal) for i in range(1, 5)}
    assert not detect_leak(ok, "m³", today, TZ).suspect
    drip = [8.0 + v for v in normal]  # 8 L/h auch nachts
    leak = {today - timedelta(days=i): _wday(today - timedelta(days=i), drip) for i in range(1, 5)}
    r = detect_leak(leak, "m³", today, TZ)
    assert r.suspect and r.kind == "nachtminimum" and r.night_min_lph == pytest.approx(8.0) and len(r.days) == 3
    high = detect_leak(leak, "m³", today, TZ, threshold_lph=10.0)
    assert high.suspect and high.kind == "dauerfluss"  # 8 L/h liegt unter 10, fließt aber ohne Pause
    garden = {d: _wday(d, [8.0] * 24) for d in leak}
    assert not detect_leak(leak, "m³", today, TZ, garden=garden).suspect  # Gartenwasser erklärt den Fluss
    gap = dict(leak)
    gap[today - timedelta(days=2)] = DailyConsumption("w1", today - timedelta(days=2))  # Lücke unterbricht
    assert detect_leak(gap, "m³", today, TZ).kind != "nachtminimum"


# ---------------------------------------------------------------- Stundenwerte aus der Statistik


def test_aggregate_day_hourly_with_jump_and_dst():
    utc = ZoneInfo("UTC")
    day = date(2026, 11, 16)
    start = datetime(2026, 11, 16, tzinfo=TZ)
    hours = [(start - timedelta(hours=1) + timedelta(hours=i)).astimezone(utc) for i in range(25)]
    sums = {h: float(i) + (50.0 if i >= 10 else 0.0) for i, h in enumerate(hours)}
    states = {h: 50.0 + i for i, h in enumerate(hours)}
    v = aggregate_day("m1", day, TZ, sums, states=states, cooling_limit=22.0)
    assert v.consumption == pytest.approx(24.0) and v.hourly == [1.0] * 24 and "statistik_sprung" in v.quality_flags
    dst = date(2026, 3, 29)
    s0 = datetime(2026, 3, 29, tzinfo=TZ).astimezone(UTC)
    hrs = [s0 - timedelta(hours=1) + timedelta(hours=i) for i in range(24)]
    v2 = aggregate_day("m1", dst, TZ, {h: float(i) for i, h in enumerate(hrs)})
    assert len(v2.hourly) == 23 and v2.consumption == 23.0


# ---------------------------------------------------------------- Prüfbefunde 1.2


def test_rounding_with_dynamic_price_is_per_segment():
    day = date(2026, 11, 16)
    seg = PriceSegment("c1", date(2026, 1, 1), 0.0, 0.0, dynamic=DynamicPrice("e", markup=0.0),
                       rounding=Rounding(quantity_decimals=0, money_decimals=2))
    intervals = {day: [0.03] * 96}
    prices = {day: _prices(day, lambda i: 0.10 + (i % 7) / 100)}
    cb = calculate_costs(C, [seg], STROM, {day: 2.88}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, intervals=intervals, prices=prices)
    raw = sum(0.03 * p for p in prices[day])
    assert cb.energy == pytest.approx(round(raw * 3 / 2.88, 2))  # Menge 2,88 → 3 kWh, Betrag einmal auf Cent


def test_dynamic_net_price_gets_vat_in_gross_contract_and_comparison():
    day = date(2026, 11, 16)
    net = PriceSegment("c1", date(2026, 1, 1), 0.0, 0.0, dynamic=DynamicPrice("e", markup=0.15, net=True))
    prices = {day: _prices(day, lambda i: 0.10)}
    cb = calculate_costs(C, [net], STROM, {day: 10.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, hourly={day: [1.0] * 24}, prices=prices)
    assert cb.energy == pytest.approx(10 * (0.10 * 1.19 + 0.15))
    c_net = Contract("c1", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR, vat_mode=VatMode.NET)
    gross_entity = PriceSegment("c1", date(2026, 1, 1), 0.0, 0.0, dynamic=DynamicPrice("e", markup=0.10))
    cb2 = calculate_costs(c_net, [gross_entity], STROM, {day: 10.0}, dt(2026, 11, 16), dt(2026, 11, 16), TZ, hourly={day: [1.0] * 24}, prices=prices)
    assert cb2.gross == pytest.approx(10 * (0.10 / 1.19 + 0.10) * 1.19)  # Brutto-Preis der Entität nicht doppelt besteuert


def test_compare_with_own_dynamic_tariff_and_rebate():
    d1 = date(2026, 11, 16)
    own_seg = PriceSegment("c1", date(2026, 1, 1), 0.0, 10.0, dynamic=DynamicPrice("own"), rebate_yearly=365.25)
    own_prices = {d1: _prices(d1, lambda i: 0.30)}
    cmp_prices = {d1: _prices(d1, lambda i: 0.10)}
    cmp_ = compare_dynamic(STROM, DynamicPrice("cmp"), 10.0, C, [own_seg], {d1: 300.0}, TZ, {d1: [12.5] * 24}, None, cmp_prices, None,
                           own_prices=own_prices)
    assert cmp_.diff == pytest.approx(300 * 0.20, abs=1e-3)  # Grundpreis und Pauschale auf beiden Seiten gleich


def test_intervals_inconsistent_with_hourly_fall_back_to_hours():
    day = date(2026, 11, 16)
    hourly = [1.0] * 24
    jump = [0.25] * 96
    jump[40] = 50.0  # Sprung in einer Viertelstunde, in den Stundenwerten schon abgezogen
    assert day_slots(day, 24.0, TZ, hourly=hourly, intervals=jump).source == "hour"


def test_leak_needs_complete_garden_and_minimum_flow():
    today = date(2026, 11, 16)
    drip = [8.0] * 24
    leak = {today - timedelta(days=i): _wday(today - timedelta(days=i), drip) for i in range(1, 5)}
    no_hourly_garden = {d: DailyConsumption("g1", d, consumption=0.19, quality=Quality.REAL) for d in leak}
    assert not detect_leak(leak, "m³", today, TZ, garden=no_hourly_garden).suspect  # Garten ohne Stundenwerte: nicht prüfbar
    noise = {today - timedelta(days=i): _wday(today - timedelta(days=i), [0.2] * 24) for i in range(1, 5)}
    assert not detect_leak(noise, "m³", today, TZ).suspect  # Rauschen unter 1 L/h ist kein Dauerfluss

