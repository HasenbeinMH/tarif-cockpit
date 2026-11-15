"""1.1: Jahresabrechnung und Kalibrieren, Staffel und Rundung, Prognosegüte, Heizlast."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.archive import forecast_accuracy, forecast_vs_actual
from engine.balance import _heat_samples
from engine.billing import calculate_costs, segment_on
from engine.heatload import HS_TO_HI, heat_load
from engine.invoice import calibrated_daily, calibrated_prices, compare_invoice
from engine.model import (
    BillingRule, Calibration, Contract, Conversion, DailyConsumption, GeneratorKind, HeatGenerator, Invoice, Medium, Meter,
    PowerBasis, PriceSegment, PriceTier, Reading, ReadingSource, Rounding,
)
from engine.quality import Quality
from engine.regression import HeatModel, ModelQuality

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 11, 15, 12, tzinfo=TZ)


def dt(y, m, d):
    return datetime(y, m, d, tzinfo=TZ)


def contract(start=date(2025, 1, 1)):
    return Contract("c1", "m1", "SW", start, BillingRule.CALENDAR_YEAR)


STROM = Meter("m1", Medium.STROM, "kWh", entity="sensor.x", data_level=2)
GAS = Meter("m1", Medium.GAS, "m³", entity="sensor.gas", data_level=2, conversion=Conversion(11.0, 0.95))


def days(first, n):
    return [first + timedelta(days=i) for i in range(n)]


# ---------------------------------------------------------------- Staffel und Rundung


def test_block_tiers_split_by_period_quantity():
    seg = PriceSegment("c1", date(2026, 1, 1), 0.0, 0.0, tiers=[PriceTier(1000, 0.30), PriceTier(None, 0.25)])
    q = {d: 10.0 for d in days(date(2026, 1, 1), 50)}  # 500 kWh
    cb = calculate_costs(contract(), [seg], STROM, q, dt(2026, 1, 1), dt(2026, 1, 1), TZ, tier_before=800.0)
    # 200 kWh bis zur Grenze 1000 zu 0,30, Rest 300 zu 0,25
    assert cb.energy == pytest.approx(200 * 0.30 + 300 * 0.25)
    half = calculate_costs(contract(), [seg], STROM, q, dt(2026, 1, 1), dt(2026, 1, 1), TZ, tier_scale=0.5)
    assert half.energy == pytest.approx(500 * 0.30)  # Halbjahr: Grenze 500
    over = calculate_costs(contract(), [seg], STROM, {date(2026, 1, 1): 600.0}, dt(2026, 1, 1), dt(2026, 1, 1), TZ, tier_scale=0.5)
    assert over.energy == pytest.approx(500 * 0.30 + 100 * 0.25)


def test_total_tiers_use_reached_tier_for_whole_quantity():
    seg = PriceSegment("c1", date(2026, 1, 1), 0.0, 0.0, tiers=[PriceTier(100, 3.0), PriceTier(None, 2.5)], tier_mode="total")
    water = Meter("m1", Medium.WASSER, "m³")
    q = {date(2026, 1, 1): 50.0}
    assert calculate_costs(contract(), [seg], water, q, dt(2026, 1, 1), dt(2026, 1, 1), TZ, tier_total=90.0).energy == pytest.approx(150.0)
    assert calculate_costs(contract(), [seg], water, q, dt(2026, 1, 1), dt(2026, 1, 1), TZ, tier_total=120.0).energy == pytest.approx(125.0)


def test_rounding_days_month_quantity_and_cents():
    base = PriceSegment("c1", date(2026, 1, 1), 0.3154, 13.09)
    q = {d: 3.333 for d in days(date(2026, 1, 1), 31)}
    plain = calculate_costs(contract(), [base], STROM, q, dt(2026, 1, 1), dt(2026, 2, 1), TZ)
    assert plain.base == pytest.approx(13.09 * 12 / 365.25 * 31, abs=1e-3)
    month = PriceSegment("c1", date(2026, 1, 1), 0.3154, 13.09, rounding=Rounding(base_by="month", quantity_decimals=0, money_decimals=2))
    cb = calculate_costs(contract(), [month], STROM, q, dt(2026, 1, 1), dt(2026, 2, 1), TZ)
    assert cb.base == pytest.approx(13.09)  # voller Monat
    assert cb.energy == pytest.approx(round(round(3.333 * 31) * 0.3154, 2))  # 103 kWh × 31,54 ct, auf Cent
    d365 = PriceSegment("c1", date(2026, 1, 1), 0.0, 10.0, rounding=Rounding(days_per_year="365"))
    assert calculate_costs(contract(), [d365], STROM, {}, dt(2026, 1, 1), dt(2027, 1, 1), TZ).base == pytest.approx(120.0)
    actual = PriceSegment("c1", date(2028, 1, 1), 0.0, 10.0, rounding=Rounding(days_per_year="actual"))
    assert calculate_costs(contract(), [actual], STROM, {}, dt(2028, 1, 1), dt(2029, 1, 1), TZ).base == pytest.approx(120.0)  # Schaltjahr


def test_invoice_example_adds_up_to_the_cent():
    """Rechnungsbeispiel: 3.342 kWh zu 31,54 ct und 12 Monate Grundpreis 13,09 € → 1.054,07 € + 157,08 € = 1.211,15 €."""
    seg = PriceSegment("c1", date(2025, 7, 1), 0.3154, 13.09, rounding=Rounding(base_by="month", quantity_decimals=0, money_decimals=2))
    c = Contract("c1", "m1", "SW", date(2025, 7, 1), BillingRule.FIXED_DAY, fixed_day="01.07")
    span = days(date(2025, 7, 1), 365)
    q = {d: 3342 / 365 for d in span}
    cb = calculate_costs(c, [seg], STROM, q, dt(2025, 7, 1), dt(2026, 7, 1), TZ)
    assert cb.energy == pytest.approx(1054.07)
    assert cb.base == pytest.approx(157.08)
    assert cb.total == pytest.approx(1211.15)


# ---------------------------------------------------------------- Rechnung gegen Integration


def _daily(meter_id, span, value, flags=(), source="statistics", quality=Quality.REAL):
    return {d: DailyConsumption(meter_id, d, consumption=value, quality=quality, quality_flags=list(flags), source=source) for d in span}


def test_compare_invoice_proposes_fallback_factor():
    span = days(date(2025, 7, 1), 365)
    daily = _daily("m1", span, 9.2, flags=["ersatzquelle"], quality=Quality.ESTIMATED)  # 3.358 kWh aus dem Wechselrichter
    inv = Invoice("i1", None, date(2026, 7, 20), date(2025, 7, 1), date(2026, 6, 30), 1200.0, meter_id="m1", quantity=3100.0)
    chk = compare_invoice(inv, STROM, None, [], daily, TZ, tolerance_pct=5.0)
    assert chk.coverage == 1.0 and chk.by_source == {"ersatzquelle": pytest.approx(3358.0)}
    assert chk.deviation_pct == pytest.approx((3358 / 3100 - 1) * 100)
    prop = chk.proposals[0]
    assert prop["art"] == "faktor_ersatzquelle" and prop["wert"] == pytest.approx(3100 / 3358, abs=1e-4)
    assert "ohne_vertrag" in chk.flags
    small = Invoice("i2", None, date(2026, 7, 20), date(2025, 7, 1), date(2026, 6, 30), 1200.0, meter_id="m1", quantity=3300.0)
    assert compare_invoice(small, STROM, None, [], daily, TZ, tolerance_pct=5.0).proposals == []  # 1,8 % < Toleranz
    far = Invoice("i3", None, date(2026, 7, 20), date(2025, 7, 1), date(2026, 6, 30), 1200.0, meter_id="m1", quantity=2000.0)
    chk3 = compare_invoice(far, STROM, None, [], daily, TZ)
    assert chk3.proposals == [] and "menge_weicht_stark_ab" in chk3.hints


def test_compare_invoice_calorific_and_price_positions():
    span = days(date(2025, 1, 1), 365)
    daily = _daily("m1", span, 4.0)
    seg = PriceSegment("c1", date(2025, 1, 1), 0.10, 15.0)
    inv = Invoice("i1", "c1", date(2026, 1, 15), date(2025, 1, 1), date(2025, 12, 31), 1800.0, meter_id="m1",
                  start_reading=1000.0, end_reading=2460.0, calorific=11.3, z_factor=0.95, work_cost=1567.0, base_cost=180.0)
    chk = compare_invoice(inv, GAS, contract(), [seg], daily, TZ)
    assert chk.quantity_invoice == 1460.0 and chk.quantity_own == pytest.approx(1460.0) and abs(chk.deviation_pct) < 1e-6
    assert [p["art"] for p in chk.proposals] == ["brennwert"] and chk.proposals[0]["wert"] == 11.3
    # Arbeitspreis mit dem Brennwert der Rechnung: 1460 × 11,3 × 0,95 × 0,10 = 1567,31 → passt; Grundpreis 180 passt
    assert chk.positions["arbeitspreis"]["eigen"] == pytest.approx(1567.31, abs=0.05)
    assert chk.hints == []
    wrong = Invoice("i2", "c1", date(2026, 1, 15), date(2025, 1, 1), date(2025, 12, 31), 1800.0, meter_id="m1",
                    start_reading=1000.0, end_reading=2460.0, work_cost=1567.0, base_cost=230.0)
    assert "grundpreis_pruefen" in compare_invoice(wrong, GAS, contract(), [seg], daily, TZ).hints


def test_compare_invoice_with_too_few_days():
    daily = _daily("m1", days(date(2025, 1, 1), 100), 4.0)
    inv = Invoice("i1", None, date(2026, 1, 15), date(2025, 1, 1), date(2025, 12, 31), 1800.0, meter_id="m1", quantity=1460.0)
    chk = compare_invoice(inv, STROM, None, [], daily, TZ)
    assert "zu_wenig_tageswerte" in chk.flags and chk.quantity_own is None and chk.proposals == []


def test_calibrations_apply_only_in_their_range():
    span = days(date(2025, 7, 1), 10)
    daily = {**_daily("m1", span[:5], 10.0, flags=["ersatzquelle"], quality=Quality.ESTIMATED), **_daily("m1", span[5:], 10.0)}
    cal = Calibration("k1", "m1", "faktor_ersatzquelle", 0.9, NOW, "i1")
    out = calibrated_daily(daily, [cal], "m1")
    assert out[span[0]].consumption == 9.0 and "kalibriert" in out[span[0]].quality_flags
    assert out[span[6]].consumption == 10.0  # eigener Zählerwert bleibt
    assert calibrated_daily(daily, [cal], "andere") is daily
    segs = [PriceSegment("c1", date(2025, 1, 1), 0.1, 10.0, calorific=11.0), PriceSegment("c1", date(2026, 1, 1), 0.12, 10.0)]
    bw = Calibration("k2", "m1", "brennwert", 11.4, NOW, "i1", date(2025, 3, 1), date(2025, 12, 31))
    cp = calibrated_prices(segs, [bw], "m1", {"c1"})
    assert segment_on(cp, date(2025, 2, 1)).calorific == 11.0
    assert segment_on(cp, date(2025, 6, 1)).calorific == 11.4 and segment_on(cp, date(2025, 6, 1)).work_price == 0.1
    assert segment_on(cp, date(2026, 2, 1)).calorific is None and segment_on(cp, date(2026, 2, 1)).work_price == 0.12


def test_invoice_without_readings_is_a_learning_sample():
    meter = Meter("m1", Medium.GAS, "m³", conversion=Conversion(11.0, 1.0))
    span = days(date(2024, 1, 1), 2 * 366 + 300)
    daily = {d: DailyConsumption("m1", d, degree_days=10.0, outdoor_temperature=5.0) for d in span}
    readings = [Reading("r1", "m1", dt(2026, 1, 1), 1000.0, source=ReadingSource.MANUAL),
                Reading("r2", "m1", dt(2026, 6, 1), 1500.0, source=ReadingSource.MANUAL)]
    inv = Invoice("i1", None, date(2025, 2, 1), date(2025, 1, 1), date(2025, 12, 31), 1500.0, meter_id="m1", quantity_kwh=20000.0)
    overlap = Invoice("i2", None, date(2026, 7, 1), date(2026, 1, 1), date(2026, 6, 30), 900.0, meter_id="m1", quantity_kwh=5000.0)
    samples, per_period = _heat_samples(meter, daily, readings, 11.0, date(2026, 11, 15), TZ, invoices=[inv, overlap])
    assert per_period and len(samples) == 2  # Ableseperiode + Rechnung 2025; die überlappende Rechnung zählt nicht doppelt
    year = next(s for s in samples if s.days == 365)
    assert year.consumption == 20000.0 and year.degree_days == pytest.approx(3650.0)


# ---------------------------------------------------------------- Prognosegüte


def _archive(end, actual, snaps, stand="abgeschlossen", menge=None):
    return {"stand": stand, "ende": end, "menge": menge, "kosten": {"gesamt": actual, "vollstaendig": True},
            "prognosen": [{"taken_at": t + "T00:05:00+01:00", "forecast_cost": c, "forecast_kwh": k, "quality": "gut"} for t, c, k in snaps]}


def test_forecast_accuracy_over_periods():
    assert forecast_accuracy([])["qualitaet"] == "unzureichend"
    a1 = _archive("2025-12-31", 1000.0, [("2025-10-01", 1100.0, 9000.0), ("2025-12-01", 1020.0, 10100.0)], menge=10000.0)
    one = forecast_accuracy([a1])
    assert one["perioden"] == 1 and one["qualitaet"] == "vorlaeufig"
    assert one["vorlauf"][0] == {"monate": 2, "kosten_pct": 10.0, "menge_pct": 10.0, "perioden": 1}
    a2 = _archive("2026-12-31", 2000.0, [("2026-10-01", 1800.0, None)])
    open_ = _archive("2027-12-31", 500.0, [("2027-10-01", 900.0, None)], stand="vorlaeufig")
    two = forecast_accuracy([a1, a2, open_])
    assert two["perioden"] == 2 and two["qualitaet"] == "gut"
    assert two["vorlauf"][0]["kosten_pct"] == pytest.approx(10.0) and two["vorlauf"][0]["perioden"] == 2
    assert forecast_vs_actual(a1)[0]["abweichung_menge_pct"] == -10.0


# ---------------------------------------------------------------- Heizlast


def _model(k, quality=ModelQuality.GOOD):
    return HeatModel(heat_coefficient=k, hot_water_baseload=8.0, confidence=quality, sample_count=60)


def test_heat_load_boiler_example():
    """Kessel 19,5 kW (kleinste Leistung 4,7 kW), k = 5 kWh Hs je Gradtag (≈ 15.000 kWh/Jahr), η 0,97, 20 °C, NAT −12 °C."""
    gen = HeatGenerator("g1", GeneratorKind.GAS_BOILER, nominal_kw=19.5, min_kw=4.7, efficiency=0.97)
    temps = {date(2026, 1, 1) + timedelta(days=i): (-8.0 if i < 100 else 12.0) for i in range(200)}
    hl = heat_load(_model(5.0), gen, 20.0, 16.0, -12.0, temps, date(2026, 11, 15))
    k_heat = 5.0 * HS_TO_HI * 0.97
    assert hl.heat_load_kw == pytest.approx(k_heat * 32 / 24)
    assert hl.ratio == pytest.approx(19.5 / hl.heat_load_kw) and hl.rating == "ueberdimensioniert"
    assert hl.cycling_limit_c == pytest.approx(20 - 4.7 * 24 / k_heat)
    assert hl.heat_load_kw == pytest.approx(5.83, abs=0.01) and hl.cycling_limit_c == pytest.approx(-5.8, abs=0.1)
    assert hl.heating_days == 200 and hl.cycling_days_share == pytest.approx(0.5)  # 12 °C über, −8 °C unter der Taktgrenze
    assert hl.quality == "gut"
    assert heat_load(_model(5.0, ModelQuality.INSUFFICIENT), gen, 20.0, 16.0, -12.0, temps, date(2026, 11, 15)) is None
    assert heat_load(None, gen, 20.0, 16.0, -12.0, temps, date(2026, 11, 15)) is None


def test_heat_load_input_basis_and_measured_peak():
    gen = HeatGenerator("g1", GeneratorKind.GAS_BOILER, nominal_kw=10.0, min_kw=None, power_basis=PowerBasis.INPUT, efficiency=0.9)
    temps = {date(2026, 2, 1): -3.0, date(2026, 3, 1): 4.0, date(2026, 7, 1): 22.0}
    power = {date(2026, 2, 1): 8.0, date(2026, 3, 1): 5.0, date(2026, 7, 1): 15.0}  # Juli: Warmwasser mit voller Leistung
    hl = heat_load(_model(8.0), gen, 20.0, 15.0, -12.0, temps, date(2026, 11, 15), power)
    assert hl.nominal_kw == pytest.approx(9.0)  # Belastung × η
    assert hl.measured_peak_kw == pytest.approx(8.0 * HS_TO_HI * 0.9)
    assert hl.cycling_limit_c is None and hl.rating == "passend"


# ---------------------------------------------------------------- Prüfbefunde 1.1


def test_fallback_factor_is_absolute_and_ranged():
    """Zwei Jahre nur Ersatzquelle: Rechnung 2024 = 1,10 ×, 2025 = 1,25 ×. Faktoren absolut, jeder ab seinem Rechnungsbeginn."""
    y24, y25 = days(date(2024, 1, 1), 366), days(date(2025, 1, 1), 365)
    raw = {**_daily("m1", y24, 10.0, flags=["ersatzquelle"], quality=Quality.ESTIMATED),
           **_daily("m1", y25, 10.0, flags=["ersatzquelle"], quality=Quality.ESTIMATED)}
    i24 = Invoice("i24", None, date(2025, 1, 20), date(2024, 1, 1), date(2024, 12, 31), 0.0, meter_id="m1", quantity=3660.0 * 1.10)
    i25 = Invoice("i25", None, date(2026, 1, 20), date(2025, 1, 1), date(2025, 12, 31), 0.0, meter_id="m1", quantity=3650.0 * 1.25)
    p24 = compare_invoice(i24, STROM, None, [], raw, TZ).proposals[0]
    p25 = compare_invoice(i25, STROM, None, [], raw, TZ).proposals[0]
    assert p24["wert"] == pytest.approx(1.10) and p25["wert"] == pytest.approx(1.25)
    cals = [Calibration("k1", "m1", "faktor_ersatzquelle", 1.10, NOW, "i24", date(2024, 1, 1)),
            Calibration("k2", "m1", "faktor_ersatzquelle", 1.25, NOW, "i25", date(2025, 1, 1))]
    out = calibrated_daily(raw, cals, "m1")
    assert out[date(2024, 6, 1)].consumption == pytest.approx(11.0) and out[date(2025, 6, 1)].consumption == pytest.approx(12.5)
    # mit geltendem Faktor: gleicher absoluter Vorschlag, „bisher“ = geltender Faktor, Abweichung danach ≈ 0
    again = compare_invoice(i25, STROM, None, [], raw, TZ, active_factor=1.25)
    assert again.proposals == [] and abs(again.deviation_pct) < 1e-6


def test_missing_days_are_extrapolated_not_zero():
    span = days(date(2025, 1, 1), 365)
    daily = _daily("m1", span[:334], 10.0, flags=["ersatzquelle"], quality=Quality.ESTIMATED)  # 91,5 %
    inv = Invoice("i1", None, date(2026, 1, 15), date(2025, 1, 1), date(2025, 12, 31), 0.0, meter_id="m1", quantity=3650.0)
    chk = compare_invoice(inv, STROM, None, [], daily, TZ)
    assert chk.quantity_own == pytest.approx(3650.0) and "hochgerechnet" in chk.flags and chk.proposals == []
    off = Invoice("i2", None, date(2026, 1, 15), date(2025, 1, 1), date(2025, 12, 31), 0.0, meter_id="m1", quantity=3300.0)
    chk2 = compare_invoice(off, STROM, None, [], daily, TZ)
    assert chk2.proposals == [] and "menge_weicht_ab_luecken" in chk2.hints  # unter 98 % kein Faktor, nur Hinweis


def test_two_calorific_calibrations_on_one_segment():
    segs = [PriceSegment("c1", date(2023, 1, 1), 0.1, 10.0, calorific=11.0)]
    cals = [Calibration("k1", "m1", "brennwert", 11.4, NOW, "i1", date(2024, 1, 1), date(2024, 12, 31)),
            Calibration("k2", "m1", "brennwert", 11.6, NOW, "i2", date(2025, 1, 1), date(2025, 12, 31)),
            Calibration("k3", "m1", "zustandszahl", 0.95, NOW, "i2", date(2025, 1, 1), date(2025, 12, 31))]
    cp = calibrated_prices(segs, cals, "m1", {"c1"})
    assert segment_on(cp, date(2023, 6, 1)).calorific == 11.0
    assert segment_on(cp, date(2024, 6, 1)).calorific == 11.4
    s25 = segment_on(cp, date(2025, 6, 1))
    assert (s25.calorific, s25.z_factor) == (11.6, 0.95)  # Brennwert und Zustandszahl derselben Rechnung zusammen
    assert segment_on(cp, date(2026, 6, 1)).calorific == 11.0


def test_total_tiers_without_total_are_incomplete_and_compare_uses_invoice_total():
    seg = PriceSegment("c1", date(2025, 1, 1), 0.0, 0.0, tiers=[PriceTier(2000, 0.30), PriceTier(None, 0.20)], tier_mode="total")
    cb = calculate_costs(contract(), [seg], STROM, {date(2025, 1, 1): 100.0}, dt(2025, 1, 1), dt(2025, 1, 1), TZ)
    assert "staffel_ohne_gesamtmenge" in cb.flags and not cb.complete
    span = days(date(2025, 1, 1), 365)
    daily = _daily("m1", span, 10.0)
    inv = Invoice("i1", "c1", date(2026, 1, 15), date(2025, 1, 1), date(2025, 12, 31), 730.0, meter_id="m1", quantity=3650.0, work_cost=730.0)
    chk = compare_invoice(inv, STROM, contract(), [seg], daily, TZ)
    assert chk.positions["arbeitspreis"]["eigen"] == pytest.approx(730.0) and "arbeitspreis_pruefen" not in chk.hints
    over = PriceSegment("c1", date(2025, 1, 1), 0.25, 0.0, tiers=[PriceTier(1000, 0.30)])
    assert calculate_costs(contract(), [over], STROM, {date(2025, 1, 1): 1500.0}, dt(2025, 1, 1), dt(2025, 1, 1), TZ).energy == pytest.approx(300 + 125)


def test_old_invoice_reading_does_not_bend_the_period_start():
    from engine.consumption import calculate_consumption  # noqa: PLC0415

    meter = Meter("m1", Medium.GAS, "m³", entity="sensor.gas", data_level=2)
    daily = {date(2025, 12, 31): DailyConsumption("m1", date(2025, 12, 31), consumption=5.0, end_value=1800.0, quality=Quality.REAL)}
    readings = [Reading("r1", "m1", dt(2025, 1, 1), 1000.0, source=ReadingSource.INVOICE),
                Reading("r2", "m1", dt(2026, 6, 1), 2400.0)]
    st = calculate_consumption(meter, readings, daily, date(2026, 1, 1), TZ, (dt(2026, 6, 1), 2400.0))
    assert st.start_source == "daily_end_value" and st.used == pytest.approx(600.0)
    near = readings + [Reading("r3", "m1", dt(2025, 12, 31), 1798.0)]  # Ablesung direkt am Periodenbeginn gilt weiter
    st2 = calculate_consumption(meter, near, daily, date(2026, 1, 1), TZ, (dt(2026, 6, 1), 2400.0))
    assert st2.start_source == "reading"

