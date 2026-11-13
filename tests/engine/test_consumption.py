"""Tageswerte aus Ablesungen und Stundenwerten, Gradtage, Qualität."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from engine.consumption import aggregate_day, daily_from_readings, hours_of_day, latest_reading
from engine.degree_days import degree_days
from engine.model import Medium, Meter, Reading, Replacement
from engine.quality import Quality, worst

TZ = ZoneInfo("Europe/Berlin")
METER = Meter(meter_id="m1", medium=Medium.GAS, unit="m³")


def rd(rid, y, m, d, h, value, quality=Quality.REAL, superseded=None):
    return Reading(rid, "m1", datetime(y, m, d, h, tzinfo=TZ), value, quality, superseded_by=superseded)


def test_degree_days():
    assert degree_days(5.0) == 15.0
    assert degree_days(15.0) == 0.0
    assert degree_days(14.9, 15, 20) == 5.1
    assert degree_days(None) is None


def test_worst_quality():
    assert worst(Quality.REAL, Quality.INTERPOLATED) == Quality.INTERPOLATED
    assert worst() == Quality.MISSING


def test_dst_day_lengths():
    assert hours_of_day(date(2026, 3, 29), TZ) == 23
    assert hours_of_day(date(2026, 10, 25), TZ) == 25
    assert hours_of_day(date(2026, 11, 13), TZ) == 24


def test_readings_interpolated_and_missing_outside():
    rs = [rd("a", 2026, 1, 1, 0, 100.0), rd("b", 2026, 1, 11, 0, 200.0)]
    days = daily_from_readings(METER, rs, date(2025, 12, 31), date(2026, 1, 12), TZ)
    by = {d.date: d for d in days}
    assert by[date(2025, 12, 31)].quality == Quality.MISSING and by[date(2025, 12, 31)].consumption is None
    assert by[date(2026, 1, 5)].quality == Quality.INTERPOLATED and by[date(2026, 1, 5)].consumption == 10.0
    assert sum(by[date(2026, 1, d)].consumption for d in range(1, 11)) == 100.0
    assert by[date(2026, 1, 11)].consumption is None  # nach der letzten Ablesung: fehlend, nie 0


def test_reading_midday_leaves_partial_days_missing():
    rs = [rd("a", 2026, 1, 1, 9, 0.0), rd("b", 2026, 1, 3, 9, 48.0)]
    by = {d.date: d for d in daily_from_readings(METER, rs, date(2026, 1, 1), date(2026, 1, 3), TZ)}
    assert by[date(2026, 1, 1)].consumption is None
    assert by[date(2026, 1, 2)].consumption == 24.0
    assert by[date(2026, 1, 3)].consumption is None


def test_invalid_and_superseded_readings_are_ignored():
    rs = [rd("a", 2026, 1, 1, 0, 100.0), rd("x", 2026, 1, 6, 0, 999.0, Quality.INVALID),
          rd("y", 2026, 1, 6, 0, 500.0, superseded="z"), rd("z", 2026, 1, 6, 0, 150.0), rd("b", 2026, 1, 11, 0, 200.0)]
    by = {d.date: d for d in daily_from_readings(METER, rs, date(2026, 1, 1), date(2026, 1, 10), TZ)}
    assert by[date(2026, 1, 2)].consumption == 10.0
    assert by[date(2026, 1, 8)].consumption == 10.0
    assert latest_reading(rs, "m1").reading_id == "b"


def test_meter_replacement_bridges_consumption():
    meter = Meter("m1", Medium.GAS, "m³", replacements=[Replacement(date(2026, 1, 6), old_end=150.0, new_start=0.0)])
    rs = [rd("a", 2026, 1, 1, 0, 100.0), rd("b", 2026, 1, 11, 0, 50.0)]  # neuer Zähler zeigt 50
    by = {d.date: d for d in daily_from_readings(meter, rs, date(2026, 1, 1), date(2026, 1, 10), TZ)}
    assert by[date(2026, 1, 3)].consumption == 10.0
    assert by[date(2026, 1, 3)].quality == Quality.INTERPOLATED


def test_backwards_readings_are_invalid():
    rs = [rd("a", 2026, 1, 1, 0, 100.0), rd("b", 2026, 1, 3, 0, 90.0)]
    d = daily_from_readings(METER, rs, date(2026, 1, 1), date(2026, 1, 1), TZ)[0]
    assert d.quality == Quality.INVALID and d.consumption is None


def _sums(day, n_hours, start_sum=1000.0, per_hour=1.0, skip=()):
    start = datetime(day.year, day.month, day.day, tzinfo=TZ)
    out = {start - timedelta(hours=1): start_sum}
    t = start
    s = start_sum
    for i in range(n_hours):
        s += per_hour
        if i not in skip:
            out[t] = s
        t = (t.astimezone(ZoneInfo("UTC")) + timedelta(hours=1)).astimezone(TZ)
    return out


def test_aggregate_full_day():
    day = date(2026, 1, 15)
    temps = {k: 2.0 for k in _sums(day, 24) if k.date() == day}
    d = aggregate_day("m1", day, TZ, _sums(day, 24), temps)
    assert d.quality == Quality.REAL and d.consumption == 24.0
    assert d.outdoor_temperature == 2.0 and d.degree_days == 18.0


def test_aggregate_dst_days():
    spring, autumn = date(2026, 3, 29), date(2026, 10, 25)
    assert aggregate_day("m1", spring, TZ, _sums(spring, 23)).consumption == 23.0
    assert aggregate_day("m1", autumn, TZ, _sums(autumn, 25)).consumption == 25.0


def test_aggregate_gap_inside_day_is_fine_but_missing_edge_is_missing():
    day = date(2026, 1, 15)
    assert aggregate_day("m1", day, TZ, _sums(day, 24, skip={5, 6, 7})).consumption == 24.0
    d = aggregate_day("m1", day, TZ, _sums(day, 24, skip={23}))
    assert d.quality == Quality.MISSING and d.consumption is None


def test_aggregate_temperature_incomplete():
    day = date(2026, 1, 15)
    start = datetime(2026, 1, 15, tzinfo=TZ)
    temps = {start + timedelta(hours=h): 4.0 for h in range(10)}
    d = aggregate_day("m1", day, TZ, _sums(day, 24), temps)
    assert d.outdoor_temperature is None and d.degree_days is None
    assert "aussen_unvollstaendig" in d.quality_flags


def test_half_hour_timezone_uses_hour_grid():
    """Indien (UTC+5:30): Mitternacht liegt nicht auf dem Stundenraster der Statistik."""
    tz = ZoneInfo("Asia/Kolkata")
    day = date(2026, 1, 15)
    utc = ZoneInfo("UTC")
    start = datetime(2026, 1, 14, 12, tzinfo=utc)
    sums = {start + timedelta(hours=h): 100.0 + h for h in range(48)}
    d = aggregate_day("m1", day, tz, sums)
    assert d.consumption == 24.0
    assert d.quality == Quality.ESTIMATED and "tagesgrenze_verschoben" in d.quality_flags


def test_day_with_inner_reading_gets_value():
    rs = [rd("a", 2026, 1, 5, 10, 0.0), rd("b", 2026, 2, 5, 10, 31.0), rd("c", 2026, 3, 5, 10, 59.0)]
    days = daily_from_readings(METER, rs, date(2026, 1, 6), date(2026, 3, 4), TZ)
    by = {d.date: d for d in days}
    assert by[date(2026, 2, 5)].consumption is not None
    assert "ablesung_im_tag" in by[date(2026, 2, 5)].quality_flags
    total = sum(d.consumption for d in days)
    # 06.01. 00:00 bis 05.03. 00:00: Ablesungsdifferenz abzüglich der Randstücke an den Ablesetagen
    assert abs(total - (59.0 - 14 / 24 * 1.0 - 10 / 24 * 1.0)) < 1e-6
