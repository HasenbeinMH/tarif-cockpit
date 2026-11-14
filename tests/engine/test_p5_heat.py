"""0.8: Wärmeerzeuger, Warmwasser-Flag, Kaminofen und Split-Klima mit Vergleichstagen, Heizen am Hausstrom,
Innentemperatur, Fernwärme, Reihen für die Diagramme. Szenario-Tests Heizung (Abnahme P5)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.balance import PowerHeat, evaluate_meter
from engine.generators import (
    HS_HI, build_generator_day, evaluate_generator, gas_per_hour, stove_relief_per_hour, suggested_kinds,
)
from engine.model import (
    AdvancePlan, AdvanceStep, BillingRule, Contract, GeneratorKind, HeatGenerator, Medium, Meter, PowerBasis, PriceSegment,
    Reading,
)
from engine.quality import Quality
from engine.regression import (
    MIN_COMPARISON_DAYS, HeatModel, ModelQuality, Sample, comparison_days, fit_heat_model, solve_least_squares,
)
from engine.series import cost_curve, scatter

from .synth import heat_year

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 11, 13, 12, tzinfo=TZ)
START = date(2025, 10, 1)  # gut ein Jahr Tageswerte vor "heute"
N = (NOW.date() - START).days


def samples_of(s, stove_relief=0.0):
    return [
        Sample(d.consumption, 1.0, d.degree_days, d.outdoor_temperature, stove_hours=s.stove_hours.get(k, 0.0),
               stove_assumed=s.stove_hours.get(k, 0.0) * stove_relief, hp_energy=s.hp_energy.get(k, 0.0))
        for k, d in s.daily.items() if NOW.date() - timedelta(days=365) <= k < NOW.date()
    ]


# ---------------------------------------------------------------- Regression


def test_least_squares_three_regressors_exact():
    rows = [[1, x, x * x] for x in range(10)]
    y = [2 + 3 * x - 0.5 * x * x for x in range(10)]
    a, b, c = solve_least_squares(rows, y)
    assert (a, b, c) == pytest.approx((2, 3, -0.5))
    assert solve_least_squares([[1, 2], [2, 4]], [1, 2]) is None  # singulär


def test_hot_water_flag_off_forces_zero():
    s = heat_year("g", START, N, k=6.0, ww=8.0)
    with_ww = fit_heat_model(samples_of(s))
    without = fit_heat_model(samples_of(s), hot_water=False)
    assert with_ww.hot_water_baseload == pytest.approx(8.0, abs=0.01)
    assert without.hot_water_baseload == 0.0 and "ww_aus" in without.flags


def test_stove_few_days_uses_assumption_and_keeps_coefficient():
    # Ofen nur an wenigen Tagen: Annahme (7 kWh je Stunde) gleicht den Ofen aus, der Kennwert bleibt richtig
    s = heat_year("g", START, N, k=6.0, ww=8.0, stove_every=40, stove_effect=7.0)
    with_, _ = comparison_days(samples_of(s), lambda x: x.stove_hours)
    assert 0 < with_ < MIN_COMPARISON_DAYS
    m = fit_heat_model(samples_of(s, stove_relief=7.0))
    assert m.stove_quality == ModelQuality.ASSUMPTION and "ofen_annahme" in m.flags
    assert m.heat_coefficient == pytest.approx(6.0, abs=0.01) and m.stove_coefficient == pytest.approx(7.0)


def test_stove_enough_comparison_days_is_learned():
    # genug Vergleichstage: der Ofen-Effekt wird gelernt (6 kWh/h), auch wenn die Annahme (9) daneben liegt
    s = heat_year("g", START, N, k=6.0, ww=8.0, stove_every=3, stove_effect=6.0)
    m = fit_heat_model(samples_of(s, stove_relief=9.0))
    assert m.stove_quality in (ModelQuality.GOOD, ModelQuality.VERY_GOOD)
    assert m.stove_coefficient == pytest.approx(6.0, abs=0.05)
    assert m.heat_coefficient == pytest.approx(6.0, abs=0.05)  # Kennwert unverfälscht


def test_split_climate_needs_comparison_days():
    few = heat_year("g", START, N, k=6.0, ww=8.0, hp_every=40)
    m = fit_heat_model(samples_of(few))
    assert m.hp_avoided_per_kwh is None and "klimatage_ausgeschlossen" in m.flags
    assert m.heat_coefficient == pytest.approx(6.0, abs=0.01)
    many = heat_year("g", START, N, k=6.0, ww=8.0, hp_every=3, hp_avoided=2.5)
    m2 = fit_heat_model(samples_of(many))
    assert m2.hp_avoided_per_kwh == pytest.approx(2.5, abs=0.05) and m2.hp_quality in (ModelQuality.GOOD, ModelQuality.VERY_GOOD)


def test_indoor_temperature_coefficient_and_pct():
    s = heat_year("g", START, N, k=6.0, ww=8.0, indoor=21.0, indoor_swing=1.0)
    samples = []
    for k_, d in s.daily.items():
        if k_ >= NOW.date():
            continue
        dd_in = max(d.indoor_temperature - d.outdoor_temperature, 0.0) if d.degree_days > 0 else 0.0
        samples.append(Sample(d.consumption, 1.0, d.degree_days, d.outdoor_temperature, degree_days_indoor=dd_in,
                              t_indoor=d.indoor_temperature))
    m = fit_heat_model(samples)
    assert m.heat_coefficient_indoor == pytest.approx(6.0, abs=0.01)
    heating = [x for x in samples if (x.degree_days_indoor or 0) > 0]
    expected = 100.0 / (sum(x.degree_days_indoor for x in heating) / len(heating))
    assert m.indoor_pct_per_k == pytest.approx(expected) and m.indoor_pct_quality != ModelQuality.ASSUMPTION
    # ohne Innenwerte: 6 %/K als Annahme
    plain = fit_heat_model(samples_of(heat_year("g", START, N)))
    assert plain.indoor_pct_per_k == 6.0 and plain.indoor_pct_quality == ModelQuality.ASSUMPTION


# ---------------------------------------------------------------- Erzeuger


def test_gas_power_basis_and_stove_relief():
    load = HeatGenerator("t", GeneratorKind.GAS_BOILER, nominal_kw=20.0, power_basis=PowerBasis.INPUT)
    output = HeatGenerator("t", GeneratorKind.GAS_BOILER, nominal_kw=18.0, power_basis=PowerBasis.OUTPUT, efficiency=0.9)
    assert gas_per_hour(load) == pytest.approx(20.0 * HS_HI)
    assert gas_per_hour(output) == pytest.approx(18.0 / 0.9 * HS_HI)
    stove = HeatGenerator("o", GeneratorKind.FIREPLACE, nominal_kw=6.0, effective_share=0.5)
    assert stove_relief_per_hour(stove, Medium.GAS) == pytest.approx(3.0 / 0.9 * HS_HI)
    assert stove_relief_per_hour(stove, Medium.FERNWAERME) == pytest.approx(3.0)
    assert suggested_kinds({"heating": ["gas", "kaminofen", "keine"]}) == [GeneratorKind.GAS_BOILER, GeneratorKind.FIREPLACE]


def test_generator_day_quantities_are_separate():
    d = date(2026, 1, 10)
    hp = HeatGenerator("k", GeneratorKind.AIR_AIR_HP, on_household_power=True, cop=4.0)
    g = build_generator_day(hp, d, energy=5.0)
    assert (g.energy_input, g.estimated_thermal_output, g.thermal_output, g.avoided_energy) == (5.0, 20.0, None, None)
    assert g.measurement_quality == Quality.REAL
    g2 = build_generator_day(hp, d, power_mean_kw=0.5)
    assert g2.energy_input == 12.0 and g2.measurement_quality == Quality.ESTIMATED
    assert build_generator_day(hp, d).energy_input is None  # fehlend bleibt fehlend
    stove = HeatGenerator("o", GeneratorKind.FIREPLACE, nominal_kw=6.0, efficiency=0.75)
    g3 = build_generator_day(stove, d, hours=3.0)
    # Wärme = Stunden × Nennleistung × wirksamer Anteil (Vorschlag 0,6)
    assert g3.energy_input == pytest.approx(24.0) and g3.estimated_thermal_output == pytest.approx(3.0 * 6.0 * 0.6)
    assert g3.measurement_quality == Quality.ASSUMPTION


def test_evaluate_generator_wood_and_avoided():
    stove = HeatGenerator("o", GeneratorKind.FIREPLACE, nominal_kw=6.0, efficiency=0.75, wood_price=120.0, wood_price_unit="rm")
    days = {date(2026, 1, 1) + timedelta(days=i): build_generator_day(stove, date(2026, 1, 1) + timedelta(days=i), hours=2.0)
            for i in range(10)}
    m = fit_heat_model([])  # kein Modell: keine Entlastung
    r = evaluate_generator(stove, days, date(2026, 1, 1), date(2026, 1, 11), m)
    assert r.hours == 20.0 and r.days_on == 10 and r.energy_input == pytest.approx(160.0)
    assert r.wood_kg == pytest.approx(160.0 / 4.2, abs=0.1) and r.wood_cost == pytest.approx(r.wood_kg * 120.0 / 400.0, abs=0.01)
    assert r.avoided_energy is None and "entlastung_noch_nicht_gelernt" in r.flags
    # unbrauchbares Modell (unzureichend): auch eine Annahme wird nicht angezeigt (Regel 10)
    m.stove_coefficient, m.stove_quality = 7.0, ModelQuality.ASSUMPTION
    assert evaluate_generator(stove, days, date(2026, 1, 1), date(2026, 1, 11), m).avoided_energy is None
    good = HeatModel(heat_coefficient=6.0, confidence=ModelQuality.GOOD, stove_coefficient=7.0, stove_quality=ModelQuality.ASSUMPTION)
    r2 = evaluate_generator(stove, days, date(2026, 1, 1), date(2026, 1, 11), good)
    assert r2.avoided_energy == pytest.approx(140.0) and r2.avoided_quality == "annahme"


# ---------------------------------------------------------------- Szenarien Heizung (evaluate_meter)


def _setup(meter: Meter, daily, unit_price=0.10, base=10.0, advance=150.0, demand=None):
    c = Contract("c1", meter.meter_id, "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR)
    seg = PriceSegment("c1", date(2026, 1, 1), unit_price, base)
    if demand:
        seg.demand_price, seg.demand_kw = demand
    plan = AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), advance)], 1, 1)
    used = sum(v.consumption for k, v in daily.items() if date(2026, 1, 1) <= k < NOW.date())
    readings = [Reading("r0", meter.meter_id, datetime(2026, 1, 1, tzinfo=TZ), 0.0)]
    return c, [seg], [plan], readings, (NOW, used)


def test_scenario_daniels_house_gas_with_stove():
    """Daniels Haus: Gas mit WW über die Therme und Kaminofen (Betriebszustand-Entität)."""
    gas = Meter("g", Medium.GAS, "kWh", entity="sensor.gas", data_level=2)
    s = heat_year("g", START, N, k=6.0, ww=8.0, stove_every=3, stove_effect=6.0, noise=1.0)
    c, segs, plans, rd, cur = _setup(gas, s.daily)
    res = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, stove_hours=s.stove_hours, stove_relief=9.0)
    m = res.heat_model
    assert m.usable and m.heat_coefficient == pytest.approx(6.0, abs=0.1) and m.stove_coefficient == pytest.approx(6.0, abs=0.2)
    assert res.forecast.details["entlastung_rest"] > 0
    without = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur)
    assert res.forecast.rest < without.forecast.rest  # Ofen entlastet auch im Rest der Periode
    sc = scatter(res)
    assert sc["qualitaet"] == m.confidence.value and any("ofen" in p for p in sc["punkte"])
    assert sc["gerade"]["y0"] == pytest.approx(m.hot_water_baseload, abs=0.01)
    curve = cost_curve(res, gas, segs, TZ, NOW.date())
    assert curve["ist"][-1][1] == pytest.approx(res.balance.actual_cost, abs=0.02)
    assert curve["prognose"][-1][1] == pytest.approx(res.balance.forecast_cost, abs=0.02)
    assert curve["abschlaege"][-1][1] == pytest.approx(12 * 150.0)


def test_scenario_heat_pump_on_own_meter():
    """Wärmepumpe am eigenen Zähler (WP-Tarif), ohne PV: der ganze Zähler läuft über die Gradtag-Regression."""
    wp = Meter("w", Medium.STROM, "kWh", entity="sensor.wp", data_level=2)
    s = heat_year("w", START, N, k=1.8, baseload_only=1.0)
    c, segs, plans, rd, cur = _setup(wp, s.daily, unit_price=0.25)
    meas = {k: v.consumption for k, v in s.daily.items()}
    res = evaluate_meter(wp, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, power_heat=PowerHeat(measured=meas))
    assert "heizstrom_gemessen" in res.flags and res.power_heat_model.heat_coefficient == pytest.approx(1.8, abs=0.01)
    rest_days = (date(2026, 12, 31) - NOW.date()).days + 1
    dd_prev = sum(s.daily[d - timedelta(days=365)].degree_days for d in (NOW.date() + timedelta(days=i) for i in range(rest_days)))
    assert res.forecast.rest == pytest.approx(1.8 * dd_prev + 1.0 * rest_days, rel=0.02)


def test_scenario_split_climate_on_household_power():
    """Split-Klima am Hausstrom ohne eigene Messung: witterungsabhängiger Anteil vor der Grundlast abgezogen."""
    strom = Meter("s", Medium.STROM, "kWh", entity="sensor.strom", data_level=2)
    s = heat_year("s", START, N, k=0.8, baseload_only=8.0, noise=0.3)
    c, segs, plans, rd, cur = _setup(strom, s.daily, unit_price=0.30)
    res = evaluate_meter(strom, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, power_heat=PowerHeat())
    assert "heizstrom_geschaetzt" in res.flags
    assert res.power_heat_model.heat_coefficient == pytest.approx(0.8, abs=0.02)
    plain = evaluate_meter(strom, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur)
    # ohne Vorjahresfenster fällt die Grundlast auf das Mittel seit Januar zurück (mit Sommer): unterschätzt den Winter.
    # Getrennt: Grundlast 8/Tag + 0,8 × Gradtage des Vorjahresfensters
    rest_days = (date(2026, 12, 31) - NOW.date()).days + 1
    dd_prev = sum(s.daily[d - timedelta(days=365)].degree_days for d in (NOW.date() + timedelta(days=i) for i in range(rest_days)))
    expected = 8.0 * rest_days + 0.8 * dd_prev
    assert res.forecast.details["heizstrom_rest"] == pytest.approx(0.8 * dd_prev, rel=0.03)
    assert res.forecast.rest == pytest.approx(expected, rel=0.03)
    assert abs(plain.forecast.rest - expected) > abs(res.forecast.rest - expected)


def test_scenario_district_heating_mwh_with_demand_price():
    """Fernwärme in MWh mit Leistungspreis: Prognose wie Gas, Kosten mit Leistungspreis."""
    fw = Meter("f", Medium.FERNWAERME, "MWh", entity="sensor.fw", data_level=2)
    s = heat_year("f", START, N, k=0.006, ww=0.008)  # MWh je Gradtag bzw. Tag
    c, segs, plans, rd, cur = _setup(fw, s.daily, unit_price=0.12, base=20.0, demand=(30.0, 10.0))
    res = evaluate_meter(fw, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, hot_water=True)
    assert res.heat_model.usable and res.heat_model.heat_coefficient == pytest.approx(6.0, abs=0.01)  # in kWh je Gradtag
    assert res.actual.demand > 0 and res.rest.demand > 0
    total_demand = res.actual.demand + res.rest.demand
    assert total_demand == pytest.approx(30.0 * 10.0, rel=0.01)


def test_scenario_hot_water_electric_no_ww_term():
    """Warmwasser per Durchlauferhitzer: im Gas gibt es keinen WW-Term."""
    gas = Meter("g", Medium.GAS, "kWh", entity="sensor.gas", data_level=2)
    s = heat_year("g", START, N, k=6.0, ww=0.0)
    c, segs, plans, rd, cur = _setup(gas, s.daily)
    res = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, hot_water=False)
    assert res.heat_model.hot_water_baseload == 0.0 and "ww_aus" in res.heat_model.flags


def test_indoor_split_against_previous_year():
    """Innen 1 K wärmer als im Vorjahr: der Mehrverbrauch geht auf die Raumtemperatur, nicht aufs Verhalten."""
    from engine.balance import indoor_split

    s = heat_year("g", date(2024, 10, 1), (NOW.date() - date(2024, 10, 1)).days, k=6.0, ww=0.0, indoor=20.0)
    for k_, d in s.daily.items():  # ab 2026 wird 1 K wärmer geheizt: Verbrauch folgt den Gradtagen innen
        if k_ >= date(2026, 1, 1) and d.degree_days > 0:
            d.indoor_temperature = 21.0
            d.consumption = 6.0 * (21.0 - d.outdoor_temperature)
    samples = [Sample(d.consumption, 1.0, d.degree_days, d.outdoor_temperature,
                      degree_days_indoor=max(d.indoor_temperature - d.outdoor_temperature, 0.0) if d.degree_days > 0 else 0.0,
                      t_indoor=d.indoor_temperature)
               for k_, d in s.daily.items() if NOW.date() - timedelta(days=365) <= k_ < NOW.date()]
    m = fit_heat_model(samples, hot_water=False)
    split = indoor_split(s.daily, m, date(2026, 1, 1), NOW.date())
    assert split is not None and split["innen_aenderung_k"] == pytest.approx(1.0, abs=0.01)
    assert split["gesamt_pct"] > 0 and abs(split["verhalten_pct"]) < abs(split["raumtemperatur_pct"])


def test_on_hours_from_state_changes():
    from engine.generators import is_on, on_hours

    d0 = datetime(2026, 1, 10, tzinfo=TZ)
    ch = [(d0 - timedelta(hours=2), False), (d0 + timedelta(hours=18), True), (d0 + timedelta(hours=21, minutes=30), False)]
    assert on_hours(ch, d0, d0 + timedelta(days=1)) == pytest.approx(3.5)
    # überwiegend unbekannt: fehlend, nicht 0
    assert on_hours([(d0, None), (d0 + timedelta(hours=20), True)], d0, d0 + timedelta(days=1)) is None
    assert is_on("on") and is_on("850.0") and not is_on("off") and is_on("unavailable") is None


def test_stove_detection_from_room_temperature():
    from engine.generators import stove_hours_from_room

    d0 = datetime(2026, 1, 10, 0, tzinfo=TZ)
    series = []
    for i in range(24 * 12):  # 5-Minuten-Werte
        ts = d0 + timedelta(minutes=5 * i)
        h = i / 12
        if 18 <= h < 19:
            t = 20.0 + (h - 18) * 3.0  # +3 K in einer Stunde: Ofen an
        elif 19 <= h < 22:
            t = 23.0
        elif h >= 22:
            t = 23.0 - (h - 22) * 1.0  # fällt nach dem Ausgehen
        else:
            t = 20.0
        series.append((ts, t))
    hours = stove_hours_from_room(series)
    assert 3.5 <= hours <= 5.0
    flat = [(d0 + timedelta(minutes=5 * i), 20.0 + 0.01 * (i % 3)) for i in range(288)]
    assert stove_hours_from_room(flat) == 0.0


# ---------------------------------------------------------------- Befunde der Prüfung (0.8)


def test_heat_pump_own_meter_short_contract_with_annual_value():
    """WP am eigenen Zähler, Vertrag erst 10 Tage alt, Jahresverbrauch eingetragen: nur die Wärmeprognose zählt."""
    wp = Meter("w", Medium.STROM, "kWh", entity="sensor.wp", data_level=2, annual_consumption=4000.0)
    s = heat_year("w", START, N, k=1.8, baseload_only=1.0)
    c = Contract("c1", "w", "SW", NOW.date() - timedelta(days=10), BillingRule.CONTRACT_YEAR)
    segs = [PriceSegment("c1", c.start_date, 0.25, 10.0)]
    used = sum(v.consumption for k, v in s.daily.items() if c.start_date <= k < NOW.date())
    rd = [Reading("r0", "w", datetime.combine(c.start_date, datetime.min.time(), tzinfo=TZ), 0.0)]
    meas = {k: v.consumption for k, v in s.daily.items()}
    res = evaluate_meter(wp, [c], segs, [], [], rd, s.daily, NOW, TZ, (NOW, used), power_heat=PowerHeat(measured=meas, whole_meter=True))
    assert res.forecast.available and res.forecast.method.startswith("waermepumpe")
    assert res.forecast.quality in (ModelQuality.GOOD, ModelQuality.VERY_GOOD)
    assert res.forecast.rest < 4000.0 * 2  # nicht Jahresverbrauch + Wärmeprognose
    assert res.forecast.rest == pytest.approx(res.forecast.details["heizstrom_rest"])


def test_unknown_stove_days_are_not_zero():
    """Ofenstunden erst seit 60 Tagen bekannt: das Vorjahr (unbekannt) verfälscht den Kennwert nicht."""
    s = heat_year("g", START, N, k=6.0, ww=8.0, stove_every=3, stove_effect=6.0)
    known_from = NOW.date() - timedelta(days=60)
    partial = {d: h for d, h in s.stove_hours.items() if d >= known_from}
    samples = [Sample(d.consumption, 1.0, d.degree_days, d.outdoor_temperature,
                      stove_hours=partial.get(k_) if k_ >= known_from else None,
                      stove_assumed=(partial.get(k_) or 0.0) * 6.0) for k_, d in s.daily.items()
               if NOW.date() - timedelta(days=365) <= k_ < NOW.date()]
    m = fit_heat_model(samples)
    assert "ofen_unbekannte_tage_ausgeschlossen" in m.flags
    assert m.heat_coefficient == pytest.approx(6.0, abs=0.05)


def test_cooling_in_summer_does_not_count_as_climate_day():
    """Split-Klima kühlt im Sommer: Sommertage bleiben für die Warmwasser-Trennung erhalten."""
    s = heat_year("g", START, N, k=6.0, ww=8.0)
    samples = [Sample(d.consumption, 1.0, d.degree_days, d.outdoor_temperature, hp_energy=3.0 if d.degree_days == 0 else 0.0)
               for k_, d in s.daily.items() if NOW.date() - timedelta(days=365) <= k_ < NOW.date()]
    m = fit_heat_model(samples)
    assert m.heat_coefficient == pytest.approx(6.0, abs=0.01) and m.hot_water_baseload == pytest.approx(8.0, abs=0.01)


def test_stove_without_measurable_effect_uses_no_assumption():
    """Genug Vergleichstage, aber der Ofen wirkt nicht: keine Annahme, Kennwert unverfälscht."""
    s = heat_year("g", START, N, k=6.0, ww=8.0, stove_every=3, stove_effect=0.0)
    m = fit_heat_model(samples_of(s, stove_relief=7.4))
    assert m.heat_coefficient == pytest.approx(6.0, abs=0.05)
    assert m.stove_coefficient == 0.0 and m.stove_quality != ModelQuality.ASSUMPTION and "ofen_annahme" not in m.flags
