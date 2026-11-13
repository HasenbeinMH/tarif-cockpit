"""Befunde der P3-Prüfung: Zahltermine, fehlender Brennwert, kein Abschlagsplan, Sensorausfall, Wallbox-Lücken,
Gartenwasser im Rest, Grundpreis am Tag der Zeitumstellung."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.balance import evaluate_meter
from engine.billing import calculate_costs, plan_dates
from engine.model import (
    AdvancePlan, AdvanceStep, BillingRule, Contract, DailyConsumption, Medium, Meter, PriceSegment, Reading,
)
from engine.quality import Quality

TZ = ZoneInfo("Europe/Berlin")


def dt(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=TZ)


def test_plan_dates_anchor_on_first_pay_day_after_start():
    plan = AdvancePlan("c1", [AdvanceStep(date(2026, 6, 30), 100.0)], pay_day=15, rhythm=3)
    assert [d for d, _ in plan_dates(plan, date(2026, 6, 30), date(2027, 6, 29))] == [
        date(2026, 7, 15), date(2026, 10, 15), date(2027, 1, 15), date(2027, 4, 15)]


def test_plan_dates_step_change_does_not_move_past_dates_and_short_months():
    plan = AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 100.0), AdvanceStep(date(2026, 5, 1), 120.0, pay_day=31)], pay_day=1)
    dates = plan_dates(plan, date(2026, 1, 1), date(2026, 12, 31))
    assert dates[:4] == [(date(2026, 1, 1), 100.0), (date(2026, 2, 1), 100.0), (date(2026, 3, 1), 100.0), (date(2026, 4, 1), 100.0)]
    assert dates[4] == (date(2026, 5, 31), 120.0) and (date(2026, 6, 30), 120.0) in dates


def _gas(calorific=None):
    from engine.model import Conversion

    return Meter("m1", Medium.GAS, "m³", entity="sensor.gas", conversion=Conversion(calorific, 0.95 if calorific else None))


def _contract():
    return Contract("c1", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR)


def test_gas_without_calorific_gives_no_kwh_and_no_forecast():
    res = evaluate_meter(_gas(), [_contract()], [PriceSegment("c1", date(2026, 1, 1), 0.1, 10.0)], [], [],
                         [Reading("r0", "m1", dt(2026, 1, 1), 0.0)], {}, dt(2026, 3, 1), TZ, (dt(2026, 3, 1), 500.0))
    assert "brennwert_fehlt" in res.flags
    assert res.used_billing is None and res.forecast_total is None and res.balance.forecast_cost is None


def test_no_advance_plan_means_no_saldo():
    meter = Meter("m1", Medium.STROM, "kWh", data_level=1)
    readings = [Reading("r0", "m1", dt(2026, 1, 1), 0.0), Reading("r1", "m1", dt(2026, 3, 2), 600.0)]
    res = evaluate_meter(meter, [_contract()], [PriceSegment("c1", date(2026, 1, 1), 0.3, 10.0)], [], [], readings, {},
                         dt(2026, 4, 1), TZ, None)
    assert res.balance.forecast_cost is not None
    assert res.balance.saldo is None and res.balance.verdict is None and res.balance.paid_to_date is None


def test_unavailable_meter_sensor_does_not_fall_back_to_start_reading():
    meter = Meter("m1", Medium.STROM, "kWh", entity="sensor.x")
    res = evaluate_meter(meter, [_contract()], [PriceSegment("c1", date(2026, 1, 1), 0.3, 10.0)], [], [],
                         [Reading("r0", "m1", dt(2026, 1, 1), 0.0)], {}, dt(2026, 4, 1), TZ, None)
    assert res.consumption.used is None and "sensor_nicht_verfuegbar" in res.consumption.flags
    assert res.balance.actual_cost is None


def test_wallbox_without_previous_year_keeps_previous_year_forecast():
    meter = Meter("m1", Medium.STROM, "kWh", entity="sensor.x")
    main, wb = {}, {}
    for i in range(365 + 181):
        d = date(2025, 1, 1) + timedelta(days=i)
        main[d] = DailyConsumption("m1", d, 10.0, quality=Quality.REAL)
        if d >= date(2026, 6, 1):  # Wallbox erst seit Juni 2026 erfasst
            wb[d] = DailyConsumption("wb", d, 2.0, quality=Quality.REAL)
    used = sum(v.consumption for k, v in main.items() if k >= date(2026, 1, 1))
    res = evaluate_meter(meter, [_contract()], [PriceSegment("c1", date(2026, 1, 1), 0.3, 10.0)], [], [],
                         [Reading("r0", "m1", dt(2026, 1, 1), 0.0)], main, dt(2026, 7, 1), TZ, (dt(2026, 7, 1), used), sub_daily=wb)
    assert res.forecast.method == "vorjahr" and "wallbox_luecken" in res.flags


def test_garden_water_is_excluded_from_wastewater_in_rest_too():
    meter = Meter("m1", Medium.WASSER, "m³", entity="sensor.w")
    prices = [PriceSegment("c1", date(2026, 1, 1), 2.0, 0.0, wastewater_price=3.0)]
    main = {date(2026, 1, 1) + timedelta(days=i): DailyConsumption("m1", date(2026, 1, 1) + timedelta(days=i), 1.0, quality=Quality.REAL) for i in range(60)}
    garden = {k: DailyConsumption("g", k, 0.4, quality=Quality.REAL) for k in main}
    res = evaluate_meter(meter, [_contract()], prices, [], [], [Reading("r0", "m1", dt(2026, 1, 1), 0.0)], main,
                         dt(2026, 3, 2), TZ, (dt(2026, 3, 2), 60.0), garden_daily=garden)
    rest_days = (date(2026, 12, 31) - date(2026, 3, 2)).days + 1
    assert res.rest.wastewater == pytest.approx(rest_days * 0.6 * 3.0, rel=0.01)


def test_base_price_on_dst_day_counts_one_day():
    c = _contract()
    seg = [PriceSegment("c1", date(2026, 1, 1), 0.0, 365.25 / 12)]  # 1 € je Tag
    m = Meter("m1", Medium.STROM, "kWh")
    cb = calculate_costs(c, seg, m, {}, dt(2026, 10, 25), dt(2026, 10, 26), TZ)
    assert cb.base == pytest.approx(1.0, abs=1e-4)
