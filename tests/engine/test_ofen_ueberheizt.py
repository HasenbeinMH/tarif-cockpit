"""1.2.8: Kaminofen, der bewusst zusätzlich heizt (überheizt) – seine Wärme wird nie dem Gas zugerechnet,
und Ofentage bleiben aus dem temperaturbereinigten Kennwert heraus."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from engine.balance import evaluate_meter
from engine.generators import build_generator_day, evaluate_generator
from engine.model import GeneratorKind, HeatGenerator, Medium, Meter
from engine.regression import HeatModel, ModelQuality

from .synth import heat_year
from .test_p5_heat import NOW, START, N, TZ, _setup


def _overheated(stove_every: int = 5, extra_k: float = 4.0):
    """Gas folgt der Innentemperatur 21 °C; an Ofentagen ist es durch den Ofen 4 K wärmer, das Gas bleibt gleich."""
    s = heat_year("g", START, N, k=6.0, ww=8.0, stove_every=stove_every, stove_effect=0.0, indoor=21.0)
    for d, h in s.stove_hours.items():
        if h > 0:
            s.daily[d] = replace(s.daily[d], indoor_temperature=s.daily[d].indoor_temperature + extra_k)
    return s, {d for d, h in s.stove_hours.items() if h > 0}


def test_overheating_stove_is_not_added_to_gas():
    gas = Meter("g", Medium.GAS, "kWh", entity="sensor.gas", data_level=2)
    s, stove_days = _overheated(stove_every=40)
    c, segs, plans, rd, cur = _setup(gas, s.daily)
    # bisher (Ofen entlastet): Annahme 9 kWh je Ofenstunde wird zum Gas addiert – der Kennwert wird zu hoch
    old = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, stove_hours=s.stove_hours, stove_relief=9.0)
    assert "ofen_annahme" in old.heat_model.flags
    # neu (Ofen entlastet nicht): nur die Ofentage kommen an, keine Annahme, kein Term, keine Entlastung im Rest
    new = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, stove_days=stove_days)
    plain = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur)
    m = new.heat_model
    assert m.stove_coefficient is None and m.stove_quality is None and "ofen_annahme" not in m.flags
    assert m.heat_coefficient == pytest.approx(plain.heat_model.heat_coefficient)
    assert old.heat_model.heat_coefficient > m.heat_coefficient
    assert "entlastung_rest" not in new.forecast.details
    assert new.forecast.rest == pytest.approx(plain.forecast.rest)


def test_stove_days_left_out_of_indoor_coefficient():
    gas = Meter("g", Medium.GAS, "kWh", entity="sensor.gas", data_level=2)
    s, stove_days = _overheated(stove_every=5)
    c, segs, plans, rd, cur = _setup(gas, s.daily)
    with_days = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur, stove_days=stove_days).heat_model
    without = evaluate_meter(gas, [c], segs, plans, [], rd, s.daily, NOW, TZ, cur).heat_model
    # ohne Ofentage stimmt der temperaturbereinigte Kennwert (6), mit ihnen zieht die überhöhte Raumtemperatur ihn herunter
    assert with_days.heat_coefficient_indoor == pytest.approx(6.0, abs=0.01)
    assert without.heat_coefficient_indoor is None or without.heat_coefficient_indoor < 5.9


def test_generator_without_relief_shows_no_avoided_energy():
    stove = HeatGenerator("o", GeneratorKind.FIREPLACE, nominal_kw=6.0, efficiency=0.75, relieves_heating=False)
    days = {date(2026, 1, 1) + timedelta(days=i): build_generator_day(stove, date(2026, 1, 1) + timedelta(days=i), hours=2.0)
            for i in range(10)}
    good = HeatModel(heat_coefficient=6.0, confidence=ModelQuality.GOOD, stove_coefficient=7.0, stove_quality=ModelQuality.ASSUMPTION)
    r = evaluate_generator(stove, days, date(2026, 1, 1), date(2026, 1, 11), good)
    assert r.avoided_energy is None and "entlastet_heizung_nicht" in r.flags
    assert r.hours == 20.0 and r.wood_kg is not None  # Stunden und Holz bleiben
