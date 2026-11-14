"""0.9: Impulszähler, Abgleich mit Ablesungen (Abnahme: verlorene Impulse), Gasleistung, Brennerlaufzeit, Takten."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.burner import burner_day, current_power
from engine.consumption import calculate_consumption
from engine.model import DailyConsumption, Medium, Meter, Reading
from engine.pulses import bridge_resets, unit_per_pulse
from engine.quality import Quality
from engine.reconcile import apply_reconciliation, reconcile

TZ = ZoneInfo("Europe/Berlin")
GAS = Meter("g", Medium.GAS, "m³", entity="sensor.gas_impulse", data_level=2, pulse_constant=100.0)
D0 = date(2026, 9, 1)


def midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=TZ)


def sensor_days(n: int, true_per_day: float, ratio: float, start_sensor: float = 500.0, missing=()) -> dict[date, DailyConsumption]:
    """Tageswerte eines Sensors, der nur ``ratio`` der echten Menge zählt (verlorene Impulse)."""
    out = {}
    s = start_sensor
    out[D0 - timedelta(days=1)] = DailyConsumption("g", D0 - timedelta(days=1), true_per_day * ratio, end_value=s, quality=Quality.REAL)
    for i in range(n):
        d = D0 + timedelta(days=i)
        s += true_per_day * ratio
        if d in missing:
            out[d] = DailyConsumption("g", d, None, end_value=s, quality=Quality.MISSING, quality_flags=["randwert_fehlt"])
        else:
            out[d] = DailyConsumption("g", d, true_per_day * ratio, end_value=s, quality=Quality.REAL)
    return out


def readings(*pairs):
    return [Reading(f"r{i}", "g", midnight(D0 + timedelta(days=day)), value) for i, (day, value) in enumerate(pairs)]


def test_pulse_constant_and_reset_bridge():
    assert unit_per_pulse(100, "per_unit") == 0.01 and unit_per_pulse(0.01, "per_pulse") == 0.01
    assert unit_per_pulse(None) is None and unit_per_pulse(0) is None
    t = [midnight(D0) + timedelta(hours=i) for i in range(5)]
    bridged, resets = bridge_resets({t[0]: 100, t[1]: 110, t[2]: 3, t[3]: 8, t[4]: 20})
    assert [bridged[x] for x in t] == [100, 110, 113, 118, 130] and resets == [t[2]]


def test_reconcile_with_lost_pulses_acceptance():
    """Abnahme P6: 5 % der Impulse gehen verloren. Die Ablesung gilt, Tageswerte werden angeglichen, fehlende Tage
    bleiben fehlend, ab 2 % gibt es einen Hinweis."""
    missing = {D0 + timedelta(days=40)}
    daily = sensor_days(60, 10.0, 0.95, missing=missing)
    rs = readings((0, 1000.0), (30, 1300.0), (60, 1600.0))
    rec = reconcile(GAS, rs, daily, TZ)
    first, second = rec.intervals
    assert first.read == 300.0 and first.measured == pytest.approx(285.0)
    assert first.factor == pytest.approx(300 / 285) and first.deviation_pct == pytest.approx(-5.0) and first.missing == pytest.approx(15.0)
    assert rec.notice and "abweichung" in rec.flags
    changed = {v.date: v for v in apply_reconciliation(daily, rec, TZ)}
    merged = {**daily, **changed}
    # erstes Intervall vollständig: angeglichene Tage summieren sich exakt auf die Ablesung
    s1 = sum(merged[D0 + timedelta(days=i)].consumption for i in range(30))
    assert s1 == pytest.approx(300.0)
    day = merged[D0 + timedelta(days=5)]
    assert day.quality == Quality.ESTIMATED and "abgeglichen" in day.quality_flags and day.raw_consumption == pytest.approx(9.5)
    # zweites Intervall: ein fehlender Tag bleibt fehlend (nicht 0), die übrigen sind angeglichen
    gap = merged[D0 + timedelta(days=40)]
    assert gap.consumption is None and gap.quality == Quality.MISSING
    s2 = sum(merged[D0 + timedelta(days=i)].consumption for i in range(30, 60) if i != 40)
    assert s2 == pytest.approx(290.0)  # 29 Tage × 10
    # neu rechnen ist stabil (vom Rohwert aus, nicht doppelt angeglichen)
    again = apply_reconciliation(merged, reconcile(GAS, rs, merged, TZ), TZ)
    assert again == []


def test_reconcile_outlier_and_gaps_not_applied():
    daily = sensor_days(30, 10.0, 0.6)
    rec = reconcile(GAS, readings((0, 1000.0), (30, 1300.0)), daily, TZ)
    assert "ausreisser" in rec.intervals[0].flags and rec.notice
    assert apply_reconciliation(daily, rec, TZ) == []
    holes = {D0 + timedelta(days=i) for i in range(0, 30, 3)}  # zu viele Lücken
    daily2 = sensor_days(30, 10.0, 0.95, missing=holes)
    rec2 = reconcile(GAS, readings((0, 1000.0), (30, 1300.0)), daily2, TZ)
    assert apply_reconciliation(daily2, rec2, TZ) == [] and "abgleich_luecken" in rec2.intervals[0].flags


def test_reconcile_small_deviation_no_notice_and_offset():
    daily = sensor_days(30, 10.0, 0.99)
    rs = readings((0, 1000.0), (30, 1300.0))
    rec = reconcile(GAS, rs, daily, TZ)
    assert not rec.notice and rec.intervals[0].deviation_pct == pytest.approx(-1.0)
    # Offset = Ablesung − Sensorstand: 1300 − (500 + 30 × 9,9)
    assert rec.offset == pytest.approx(1300 - (500 + 30 * 9.9))
    # aktueller Stand = Sensor + Offset, wenn der Startwert aus einer Ablesung kommt
    now = midnight(D0 + timedelta(days=30)) + timedelta(hours=12)
    st = calculate_consumption(GAS, rs, daily, D0, TZ, (now, 500 + 30 * 9.9 + 5.0), sensor_offset=rec.offset)
    assert st.used == pytest.approx(305.0) and "abgleich_offset" in st.flags


def test_reading_sensor_value_is_preferred():
    daily = sensor_days(30, 10.0, 0.95)
    rs = readings((0, 1000.0), (30, 1300.0))
    rs[1].sensor_value = 500 + 280.0  # zum Ablesezeitpunkt notierter Sensorstand
    rec = reconcile(GAS, rs, daily, TZ)
    assert rec.intervals[0].measured == pytest.approx(280.0)


def _pulses(start: datetime, minutes: float, kw: float, kwh_per_m3: float = 10.0, step_m3: float = 0.01, v0: float = 0.0):
    """Impulse eines Brennerlaufs mit konstanter Leistung (Gaszähler 0,01 m³ je Impuls)."""
    per_h = kw / kwh_per_m3  # m³/h
    dt = timedelta(hours=step_m3 / per_h)
    out, t, v = [], start, v0
    while t <= start + timedelta(minutes=minutes):
        out.append((t, round(v, 4)))
        t += dt
        v += step_m3
    return out, v


def test_burner_runtime_starts_and_power():
    day = midnight(date(2026, 11, 10))
    run, v = _pulses(day + timedelta(hours=18), 60, 10.0)
    res = burner_day(run, day, day + timedelta(days=1), kwh_per_unit=10.0)
    assert res.starts == 1 and res.hours == pytest.approx(1.0, abs=0.02)
    assert res.mean_power_kw == pytest.approx(10.0, rel=0.02) and res.cycling is None
    assert current_power(run, run[-1][0] + timedelta(seconds=10), 10.0) == pytest.approx(10.0, rel=0.02)
    assert current_power(run, run[-1][0] + timedelta(minutes=10), 10.0) == 0.0


def test_burner_cycling_at_minimum_modulation():
    """Viele kurze Läufe mit kleiner Leistung: Heizlast unter der kleinsten Modulationsstufe."""
    day = midnight(date(2026, 11, 10))
    changes, v = [], 0.0
    for k in range(12):  # 12 Läufe à 5 min mit 4 kW, je 15 min Pause
        run, v = _pulses(day + timedelta(minutes=20 * k), 5, 4.0, v0=v)
        changes += run
    res = burner_day(changes, day, day + timedelta(days=1), kwh_per_unit=10.0, min_power_kw=3.5)
    assert res.starts == 12 and res.cycling is True
    calm = burner_day(changes, day, day + timedelta(days=1), kwh_per_unit=10.0, min_power_kw=1.0)
    assert calm.cycling is False  # Leistung weit über der kleinsten Stufe: kein Takten
    quiet = burner_day([], day, day + timedelta(days=1), kwh_per_unit=10.0)
    assert quiet.hours == 0.0 and quiet.starts == 0


# ---------------------------------------------------------------- Befunde der Prüfung (0.9)


def test_persistent_resets_detect_and_apply():
    from engine.pulses import apply_resets, detect_resets

    t = [midnight(D0) + timedelta(hours=i) for i in range(4)]
    resets = detect_resets({t[1]: 3.0, t[2]: 5.0}, last_raw=53.0)  # vor der Reihe stand der Zähler bei 53
    assert resets == [(t[1], 53.0)]
    assert apply_resets({t[0]: 50.0, t[2]: 5.0, t[3]: 9.0}, resets) == {t[0]: 50.0, t[2]: 58.0, t[3]: 62.0}


def test_meter_replacement_keeps_reconciliation_and_offset():
    from engine.model import Replacement

    meter = Meter("g", Medium.GAS, "m³", entity="sensor.gas", data_level=2,
                  replacements=[Replacement(D0 + timedelta(days=40), old_end=1400.0, new_start=0.0)])
    daily = sensor_days(60, 10.0, 1.0, start_sensor=1000.0)
    # neuer Zähler: Sensor und Ablesung starten nach dem Tausch bei 0
    for d, v in daily.items():
        if d >= D0 + timedelta(days=40):
            daily[d] = DailyConsumption("g", d, v.consumption, end_value=v.end_value - 1400.0, quality=Quality.REAL)
    rs = readings((0, 1000.0), (30, 1300.0), (50, 100.0))  # nach dem Tausch: 100 auf dem neuen Zähler
    rec = reconcile(meter, rs, daily, TZ)
    assert all(i.deviation_pct == pytest.approx(0.0, abs=1e-6) for i in rec.intervals)
    now = midnight(D0 + timedelta(days=55))
    st = calculate_consumption(meter, rs, daily, D0, TZ, (now, daily[D0 + timedelta(days=54)].end_value), sensor_offset=rec.offset)
    assert st.used == pytest.approx(550.0)


def test_outlier_reading_does_not_set_offset_and_estimates_ignored():
    daily = sensor_days(60, 10.0, 1.0)
    rs = readings((0, 1000.0), (30, 1300.0), (60, 16000.0))  # Tippfehler: 16000 statt 1600
    rec = reconcile(GAS, rs, daily, TZ)
    assert "ausreisser" in rec.intervals[-1].flags and "offset_aus_frueherer_ablesung" in rec.flags
    assert rec.offset == pytest.approx(1300 - (500 + 30 * 10.0))
    est = readings((0, 1000.0), (30, 1400.0))
    est[1].quality = Quality.ESTIMATED  # Schätzung des Versorgers: gleicht nichts an
    assert reconcile(GAS, est, daily, TZ).intervals == []


def test_reset_after_invalid_reading_restores_original_quality():
    daily = sensor_days(30, 10.0, 0.95)
    d5 = D0 + timedelta(days=5)
    daily[d5] = DailyConsumption("g", d5, 9.5, end_value=daily[d5].end_value, quality=Quality.ESTIMATED, quality_flags=["ersatzquelle"])
    rs = readings((0, 1000.0), (30, 1300.0))
    merged = {**daily, **{v.date: v for v in apply_reconciliation(daily, reconcile(GAS, rs, daily, TZ), TZ)}}
    assert "abgeglichen" in merged[d5].quality_flags
    rs[1].quality = Quality.INVALID  # Ablesung ungültig: zurück auf den Rohwert
    back = {v.date: v for v in apply_reconciliation(merged, reconcile(GAS, rs, merged, TZ), TZ)}
    assert back[d5].consumption == 9.5 and back[d5].quality == Quality.ESTIMATED and "ersatzquelle" in back[d5].quality_flags
    assert back[D0 + timedelta(days=6)].quality == Quality.REAL


def test_burner_midnight_single_pulse_runs_and_gap():
    from engine.burner import max_gap_for

    # 0,1 m³ je Impuls, 10 kWh/m³, kleinste Leistung 5 kW: Impulsabstand 12 min → max_gap 18 min
    gap = max_gap_for(0.1, 10.0, 5.0)
    assert gap == timedelta(minutes=18)
    day = midnight(date(2026, 11, 10))
    run, _ = _pulses(day - timedelta(minutes=30), 60, 10.0)  # Lauf 23:30–00:30
    res = burner_day(run, day, day + timedelta(days=1), kwh_per_unit=10.0)
    prev = burner_day(run, day - timedelta(days=1), day, kwh_per_unit=10.0)
    assert res.hours == pytest.approx(0.5, abs=0.02) and prev.hours == pytest.approx(0.5, abs=0.02)
    assert res.starts == 0 and prev.starts == 1  # der Start zählt am Vortag
    single = [(day + timedelta(hours=h), 0.01 * k) for k, h in enumerate((2, 5, 9))]  # drei Läufe aus je einem Impuls
    res1 = burner_day(single, day, day + timedelta(days=1), kwh_per_unit=10.0, unit_per_pulse=0.01, min_power_kw=4.0)
    assert res1.starts == 2 and res1.hours > 0  # erster Wert ohne Vorgänger ist nur der Ausgangsstand
