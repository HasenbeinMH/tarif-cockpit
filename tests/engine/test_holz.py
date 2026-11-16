"""1.2.2: gewogenes Holz am Kaminofen – Menge und Wärme je Brennstunde lernen, Tageswerte, Entlastungs-Annahme."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from engine.generators import (
    HS_HI, WOOD_KWH_PER_KG, apply_wood, build_generator_day, evaluate_generator, stove_relief_per_hour, wood_by_day, wood_rate,
)
from engine.model import Dataset, GeneratorDaily, GeneratorKind, HeatGenerator, Medium, WoodEntry, to_dict
from engine.quality import Quality

STOVE = HeatGenerator("o1", GeneratorKind.FIREPLACE, nominal_kw=8.0, efficiency=0.75, effective_share=0.6,
                      wood_price=260.0, wood_price_unit="rm", kg_per_rm=480.0)
D0 = date(2026, 11, 1)


def days(hours: list[float | None]) -> dict[date, GeneratorDaily]:
    return {D0 + timedelta(days=i): build_generator_day(STOVE, D0 + timedelta(days=i), hours=h) for i, h in enumerate(hours)}


def test_wood_by_day_sums_entries_per_stove() -> None:
    entries = [WoodEntry("a", "o1", D0, 10.0), WoodEntry("b", "o1", D0, 5.5), WoodEntry("c", "o2", D0, 3.0),
               WoodEntry("d", "o1", D0 + timedelta(days=1), 12.0)]
    assert wood_by_day(entries, "o1") == {D0: 15.5, D0 + timedelta(days=1): 12.0}


def test_rate_needs_three_days_with_hours() -> None:
    d = days([5.0, 4.0, 0.5, None, 6.0])
    wood = {D0: 15.0, D0 + timedelta(days=1): 12.0, D0 + timedelta(days=2): 3.0, D0 + timedelta(days=3): 9.0}
    # Tag 3 (0,5 h) und Tag 4 (keine Stunden) zählen nicht → nur 2 Tage → noch nicht gelernt
    assert wood_rate(STOVE, d, wood) is None
    wood[D0 + timedelta(days=4)] = 18.0
    r = wood_rate(STOVE, d, wood)
    assert r is not None and r.days == 3 and r.quality == "vorlaeufig"
    assert r.kg_per_hour == pytest.approx(45.0 / 15.0)  # Summe kg ÷ Summe Stunden
    assert r.heat_kw == pytest.approx(3.0 * WOOD_KWH_PER_KG * 0.75, abs=0.01)


def test_rate_good_after_seven_days_and_zero_kg_ignored() -> None:
    d = days([4.0] * 8)
    wood = {D0 + timedelta(days=i): 10.0 for i in range(7)}
    wood[D0 + timedelta(days=7)] = 0.0  # kein Holz: zählt nicht zur Rate
    r = wood_rate(STOVE, d, wood)
    assert r.days == 7 and r.quality == "gut" and r.kg_per_hour == pytest.approx(2.5)


def test_rate_only_for_fireplace() -> None:
    hp = HeatGenerator("w1", GeneratorKind.WATER_HP)
    assert wood_rate(hp, days([5, 5, 5]), {D0: 1, D0 + timedelta(days=1): 1, D0 + timedelta(days=2): 1}) is None


def test_apply_wood_replaces_assumption_and_keeps_measurements() -> None:
    d = days([5.0, 4.0, 6.0, 3.0])
    d[D0 + timedelta(days=3)] = GeneratorDaily("o1", D0 + timedelta(days=3), energy_input=20.0, measurement_quality=Quality.REAL, hours=3.0)
    wood = {D0: 15.0, D0 + timedelta(days=1): 12.0, D0 + timedelta(days=2): 18.0, D0 + timedelta(days=3): 99.0,
            D0 + timedelta(days=5): 7.0}  # Tag 5 ohne Tageswert (z. B. Erkennung ausgefallen)
    rate = wood_rate(STOVE, d, wood)
    out = apply_wood(STOVE, d, wood, rate)
    g0 = out[D0]
    assert g0.energy_input == pytest.approx(15.0 * WOOD_KWH_PER_KG) and g0.measurement_quality == Quality.ESTIMATED
    assert g0.estimated_thermal_output == pytest.approx(15.0 * WOOD_KWH_PER_KG * 0.75 * 0.6)  # wirksame Wärme
    assert out[D0 + timedelta(days=3)].energy_input == 20.0  # eigene Messung bleibt
    assert out[D0 + timedelta(days=5)].energy_input == pytest.approx(7.0 * WOOD_KWH_PER_KG)
    # Tag ohne Holz, aber mit Stunden: gelernte Menge je Brennstunde statt Nennleistung
    d2 = {**d, D0 + timedelta(days=6): build_generator_day(STOVE, D0 + timedelta(days=6), hours=2.0)}
    out = apply_wood(STOVE, d2, wood, rate)
    g6 = out[D0 + timedelta(days=6)]
    assert g6.energy_input == pytest.approx(2.0 * rate.kg_per_hour * WOOD_KWH_PER_KG, abs=1e-3)
    assert g6.estimated_thermal_output == pytest.approx(2.0 * rate.kg_per_hour * WOOD_KWH_PER_KG * 0.75 * 0.6, abs=1e-3)
    assert g6.measurement_quality == Quality.ASSUMPTION  # Rate erst vorläufig
    # die Eingabe bleibt unverändert
    assert d2[D0].measurement_quality == Quality.ASSUMPTION


def test_evaluate_with_wood_counts_weighed_kg_and_costs() -> None:
    d = days([5.0, 4.0, 6.0, 2.0])
    wood = {D0: 15.0, D0 + timedelta(days=1): 12.0, D0 + timedelta(days=2): 18.0}
    res = evaluate_generator(STOVE, d, D0, D0 + timedelta(days=4), wood=wood)
    assert res.wood_days == 3 and res.wood_weighed_kg == 45.0
    assert res.wood_rate is not None and "holz_leistung_gelernt" in res.flags
    # 45 kg gewogen + 2 h × 3 kg/h
    assert res.wood_kg == pytest.approx(51.0, abs=0.1)
    assert res.wood_cost == pytest.approx(51.0 * 260 / 480, abs=0.05)
    assert res.measurement_quality == Quality.ASSUMPTION  # ein Tag hochgerechnet mit vorläufiger Rate


def test_evaluate_without_enough_days_flags_weighed_only() -> None:
    d = days([5.0, 4.0])
    res = evaluate_generator(STOVE, d, D0, D0 + timedelta(days=2), wood={D0: 15.0})
    assert res.wood_rate is None and "holz_gewogen" in res.flags
    # Tag 0 gewogen, Tag 1 weiter Nennleistung ÷ Wirkungsgrad
    assert res.wood_kg == pytest.approx(15.0 + 4.0 * 8.0 / 0.75 / WOOD_KWH_PER_KG, abs=0.1)


def test_rate_learned_from_whole_history_not_only_period() -> None:
    d = days([5.0, 4.0, 6.0, 3.0])
    wood = {D0: 15.0, D0 + timedelta(days=1): 12.0, D0 + timedelta(days=2): 18.0}
    res = evaluate_generator(STOVE, d, D0 + timedelta(days=3), D0 + timedelta(days=4), wood=wood)
    assert res.wood_rate is not None and res.wood_days == 0 and res.wood_weighed_kg is None
    assert res.wood_kg == pytest.approx(3.0 * 3.0, abs=0.1)


def test_relief_assumption_uses_learned_heat() -> None:
    assert stove_relief_per_hour(STOVE, Medium.GAS) == pytest.approx(8.0 * 0.6 / 0.9 * HS_HI)
    # gelernte Ofenwärme ersetzt die Nennleistung, der wirksame Anteil bleibt
    assert stove_relief_per_hour(STOVE, Medium.GAS, 9.45) == pytest.approx(9.45 * 0.6 / 0.9 * HS_HI)
    assert stove_relief_per_hour(STOVE, Medium.FERNWAERME, 9.45) == pytest.approx(9.45 * 0.6)


def test_dataset_round_trip_and_consistency() -> None:
    ds = Dataset(wood_log=[WoodEntry("a", "o1", D0, 12.5, logs=8, kg_per_log=1.5625, note="Buche")])
    back, errors = Dataset.from_dict(to_dict(ds))
    assert not errors and back.wood_log == ds.wood_log
    raw = to_dict(ds)
    raw["wood_log"].append(dict(raw["wood_log"][0]))
    assert Dataset.from_dict(raw)[0] is None
    old = to_dict(Dataset())
    del old["wood_log"]
    back, errors = Dataset.from_dict(old)
    assert not errors and back.wood_log == []


def test_good_rate_marks_extrapolated_days_estimated_and_heat_meter_kept() -> None:
    d = days([4.0] * 9)
    wood = {D0 + timedelta(days=i): 10.0 for i in range(7)}
    rate = wood_rate(STOVE, d, wood)
    assert rate.quality == "gut"
    out = apply_wood(STOVE, d, wood, rate)
    assert out[D0 + timedelta(days=8)].measurement_quality == Quality.ESTIMATED
    # Wärmemengenzähler am Ofen: gemessene Wärme und Qualität bleiben
    d[D0] = GeneratorDaily("o1", D0, thermal_output=30.0, measurement_quality=Quality.REAL, hours=4.0)
    out = apply_wood(STOVE, d, wood, rate)
    assert out[D0].thermal_output == 30.0 and out[D0].measurement_quality == Quality.REAL
    assert out[D0].energy_input == pytest.approx(10.0 * WOOD_KWH_PER_KG)
