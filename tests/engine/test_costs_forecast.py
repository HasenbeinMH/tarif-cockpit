"""Kosten, Zahlungen, Regression, Prognose (0.6)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from zoneinfo import ZoneInfo

import pytest

from engine.balance import calculate_balance, evaluate_meter
from engine.billing import calculate_costs, calculate_payments
from engine.forecast import baseload_forecast, heat_forecast, submeter_forecast
from engine.model import (
    AdvancePlan, AdvanceStep, BillingRule, Contract, Conversion, DailyConsumption, Medium, Meter, Payment, PaymentStatus,
    PaymentType, PriceSegment, Reading, VatMode,
)
from engine.quality import Quality
from engine.regression import HeatModel, ModelQuality, Sample, fit_heat_model
from engine.units import convert

TZ = ZoneInfo("Europe/Berlin")


def dt(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=TZ)


def contract(rule=BillingRule.CALENDAR_YEAR, start=date(2026, 1, 1), vat=VatMode.GROSS):
    return Contract("c1", "m1", "SW", start, rule, vat_mode=vat)


STROM = Meter("m1", Medium.STROM, "kWh", entity="sensor.x", data_level=2)


# ---------------------------------------------------------------- Einheiten


def test_units():
    assert convert(1500, "Wh", "kWh") == 1.5
    assert convert(2, "MWh", "kWh") == 2000
    assert convert(500, "L", "m³") == 0.5
    with pytest.raises(ValueError):
        convert(1, "kWh", "m³")


# ---------------------------------------------------------------- Kosten


def test_price_change_mid_period_and_base_price_per_day():
    c = contract()
    segs = [PriceSegment("c1", date(2026, 1, 1), 0.30, 10.0), PriceSegment("c1", date(2026, 1, 11), 0.40, 20.0)]
    q = {date(2026, 1, 1) + timedelta(days=i): 10.0 for i in range(20)}
    cb = calculate_costs(c, segs, STROM, q, dt(2026, 1, 1), dt(2026, 1, 21), TZ)
    assert cb.energy == pytest.approx(10 * 10 * 0.30 + 10 * 10 * 0.40)
    assert cb.base == pytest.approx(10 * 10 * 12 / 365.25 + 10 * 20 * 12 / 365.25, abs=1e-3)
    assert cb.complete


def test_net_prices_add_vat_and_missing_price_is_flagged():
    c = contract(vat=VatMode.NET)
    segs = [PriceSegment("c1", date(2026, 1, 5), 0.25, 0.0)]
    cb = calculate_costs(c, segs, STROM, {date(2026, 1, 5): 100.0, date(2026, 1, 2): 5.0}, dt(2026, 1, 5), dt(2026, 1, 6), TZ)
    assert cb.total == pytest.approx(25.0) and cb.gross == pytest.approx(25.0 * 1.19)
    assert "kein_preis" in cb.flags and not cb.complete


def test_gas_calorific_from_segment():
    gas = Meter("m1", Medium.GAS, "m³", conversion=Conversion(11.0, 0.95))
    segs = [PriceSegment("c1", date(2026, 1, 1), 0.10, 0.0), PriceSegment("c1", date(2026, 1, 2), 0.10, 0.0, calorific=12.0, z_factor=1.0)]
    cb = calculate_costs(contract(), segs, gas, {date(2026, 1, 1): 1.0, date(2026, 1, 2): 1.0}, dt(2026, 1, 1), dt(2026, 1, 1), TZ)
    assert cb.quantity == pytest.approx(11.0 * 0.95 + 12.0)
    no_conv = Meter("m1", Medium.GAS, "m³")
    assert "brennwert_fehlt" in calculate_costs(contract(), segs[:1], no_conv, {date(2026, 1, 1): 1.0}, dt(2026, 1, 1), dt(2026, 1, 1), TZ).flags


def test_water_with_wastewater_and_fixed_yearly():
    water = Meter("m1", Medium.WASSER, "m³")
    segs = [PriceSegment("c1", date(2026, 1, 1), 2.0, 0.0, wastewater_price=3.0, fixed_yearly=36.525)]
    cb = calculate_costs(contract(), segs, water, {date(2026, 1, 1): 1.0}, dt(2026, 1, 1), dt(2026, 1, 2), TZ,
                         wastewater={date(2026, 1, 1): 0.6})
    assert cb.energy == 2.0 and cb.wastewater == pytest.approx(1.8) and cb.fixed == pytest.approx(0.1)


# ---------------------------------------------------------------- Zahlungen


def test_payments_steps_rhythm_max_and_partial_year():
    plan = AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 100.0), AdvanceStep(date(2026, 5, 1), 120.0)], pay_day=15, max_per_period=11)
    ps = calculate_payments(plan, [], date(2026, 1, 1), date(2026, 12, 31), date(2026, 6, 20))
    assert ps.per_period == 11
    assert ps.paid_to_date == 4 * 100 + 2 * 120
    assert ps.period_total == 4 * 100 + 7 * 120
    assert ps.next_date == date(2026, 7, 15) and ps.remaining == 5
    q = calculate_payments(AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 300.0)], pay_day=1, rhythm=3), [], date(2026, 1, 1), date(2026, 12, 31), date(2026, 12, 31))
    assert [i.date.month for i in q.installments] == [1, 4, 7, 10]
    rumpf = calculate_payments(AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 50.0)], pay_day=1), [], date(2026, 9, 15), date(2026, 12, 31), date(2026, 9, 15))
    assert rumpf.per_period == 3  # 01.10., 01.11., 01.12.


def test_payments_own_records_credit_and_cancel():
    plan = AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 100.0)], pay_day=1)
    pays = [
        Payment("p1", "c1", date(2026, 2, 3), 95.0, PaymentType.ADVANCE),  # tatsächlich gezahlt, ersetzt Februar
        Payment("p2", "c1", date(2026, 3, 1), 100.0, PaymentType.ADVANCE, PaymentStatus.CANCELLED),  # März storniert
        Payment("p3", "c1", date(2026, 3, 10), 40.0, PaymentType.CREDIT),  # Gutschrift
    ]
    ps = calculate_payments(plan, pays, date(2026, 1, 1), date(2026, 12, 31), date(2026, 3, 31))
    assert ps.paid_to_date == 100 + 95 - 40
    assert ps.period_total == 100 + 95 + 9 * 100 - 40


def test_balance_verdict_and_recommended_advance():
    plan = AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 100.0)], pay_day=1)
    ps = calculate_payments(plan, [], date(2026, 1, 1), date(2026, 12, 31), date(2026, 6, 15))
    b = calculate_balance(1500.0, ps, 5.0)
    assert b.saldo == -300.0 and b.verdict == "nachzahlung"
    assert b.recommended_advance == math.ceil((1500 - 600) / 6) and b.fitting_advance == 125
    assert calculate_balance(1210.0, ps, 5.0).verdict == "passt"


# ---------------------------------------------------------------- Regression


def _days(k=6.0, ww=10.0, n=120, noise=0.0, summer=True):
    out = []
    for i in range(n):
        t = 18.0 - 20.0 * i / n if summer else 10.0 - 10.0 * i / n
        dd = max(20.0 - t, 0.0) if t < 15 else 0.0
        out.append(Sample(ww + k * dd + (noise if i % 2 else -noise), 1.0, dd, t))
    return out


def test_regression_separates_hot_water_with_summer_days():
    m = fit_heat_model(_days())
    assert m.heat_coefficient == pytest.approx(6.0) and m.hot_water_baseload == pytest.approx(10.0)
    assert m.confidence == ModelQuality.VERY_GOOD and m.usable


def test_regression_without_summer_days_folds_hot_water():
    m = fit_heat_model(_days(summer=False))
    assert "ww_nicht_getrennt" in m.flags and m.hot_water_baseload == 0.0


@pytest.mark.parametrize(("samples", "quality"), [
    (_days(n=10), ModelQuality.INSUFFICIENT),  # zu wenige Tage
    ([Sample(50, 1, 10, 10.0 + i * 0.1) for i in range(30)], ModelQuality.INSUFFICIENT),  # Spanne < 5 K
    (_days(n=30, noise=25.0), ModelQuality.INSUFFICIENT),  # schwache Erklärung
])
def test_regression_quality_levels(samples, quality):
    assert fit_heat_model(samples).confidence == quality


def test_regression_preliminary_and_good():
    assert fit_heat_model(_days(n=25, noise=8.0)).confidence in (ModelQuality.PRELIMINARY, ModelQuality.GOOD)
    assert fit_heat_model(_days(n=50, noise=2.0)).confidence in (ModelQuality.GOOD, ModelQuality.VERY_GOOD)


# ---------------------------------------------------------------- Prognose


def test_baseload_fallbacks():
    start, known, end = date(2026, 1, 1), date(2026, 3, 2), date(2026, 12, 31)
    f1 = baseload_forecast(600.0, start, known, end, {}, elapsed_days=60)
    assert f1.method == "mittel_seit_beginn" and f1.quality == ModelQuality.PRELIMINARY
    assert f1.rest == pytest.approx(10.0 * ((end - known).days + 1))
    f2 = baseload_forecast(100.0, start, date(2026, 1, 11), end, {}, elapsed_days=10, annual=3650.0)
    assert f2.method == "jahresrechnung" and f2.quality == ModelQuality.ASSUMPTION
    f3 = baseload_forecast(100.0, start, date(2026, 1, 11), end, {}, elapsed_days=10)
    assert not f3.available


def test_baseload_missing_previous_year_days_are_not_zero():
    start, known, end = date(2026, 1, 1), date(2026, 2, 1), date(2026, 12, 31)
    prev = {date(2025, 1, 1) + timedelta(days=i): 10.0 for i in range(365) if i % 2}  # nur jeder zweite Tag
    f = baseload_forecast(310.0, start, known, end, prev, 31)
    assert f.method != "vorjahr"  # 50 % Abdeckung reicht nicht, keine Nullen eingerechnet


def test_submeter_and_heat_forecast():
    known, end = date(2026, 11, 13), date(2026, 11, 22)
    wb = {known - timedelta(days=i): 7.0 for i in range(1, 31)}
    f = submeter_forecast(wb, known, end)
    assert f.rest == pytest.approx(70.0)
    model = HeatModel(heat_coefficient=5.0, hot_water_baseload=2.0, confidence=ModelQuality.GOOD)
    dd = {date(2025, 11, 13) + timedelta(days=i): 12.0 for i in range(10)}
    h = heat_forecast(model, dd, known, end)
    assert h.rest == pytest.approx(5.0 * 120 + 2.0 * 10)
    assert not heat_forecast(HeatModel(confidence=ModelQuality.INSUFFICIENT), dd, known, end).available


def test_evaluate_with_wallbox_separated():
    now = dt(2026, 7, 1, 0)
    c = Contract("c1", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR)
    prices = [PriceSegment("c1", date(2026, 1, 1), 0.30, 10.0)]
    main, wb = {}, {}
    for i in range(365 + 181):
        d = date(2025, 1, 1) + timedelta(days=i)
        main[d] = DailyConsumption("m1", d, 10.0 + (5.0 if d >= date(2026, 6, 1) else 0.0), quality=Quality.REAL)
        wb[d] = DailyConsumption("wb", d, 5.0 if d >= date(2026, 6, 1) else 0.0, quality=Quality.REAL)
    readings = [Reading("r0", "m1", dt(2026, 1, 1), 0.0)]
    used = sum(v.consumption for k, v in main.items() if k >= date(2026, 1, 1))
    res = evaluate_meter(STROM, [c], prices, [], [], readings, main, now, TZ, (now, used), sub_daily=wb)
    assert "wallbox_getrennt" in res.flags
    # Grundlast wie im Vorjahr (10/Tag) + Wallbox 5/Tag fortgeschrieben
    assert res.forecast.rest == pytest.approx(184 * 10.0 + 184 * 5.0, rel=0.01)


def test_readings_only_meter_known_until_last_reading():
    meter = Meter("m1", Medium.STROM, "kWh", data_level=1)
    c = Contract("c1", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR)
    prices = [PriceSegment("c1", date(2026, 1, 1), 0.30, 0.0)]
    readings = [Reading("r0", "m1", dt(2026, 1, 1), 0.0), Reading("r1", "m1", dt(2026, 3, 2), 600.0)]
    res = evaluate_meter(meter, [c], prices, [], [], readings, {}, dt(2026, 4, 1, 12), TZ, None)
    assert res.consumption.used == 600.0 and res.consumption.known_until == readings[1].timestamp
    assert res.forecast.method == "mittel_seit_beginn"
    assert res.forecast_total == pytest.approx(600 + 10.0 * 305, rel=0.01)
