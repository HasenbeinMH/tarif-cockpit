"""Szenario-Fixtures (Arbeitspaket 1a): Haushalte im Umfang von 0.5 (Perioden, Ablesungen, Tageswerte)."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from engine.billing import current_period, periods_for_chain, validate_chain
from engine.consumption import daily_from_readings
from engine.model import Dataset, Meter, from_dict
from engine.quality import Quality

TZ = ZoneInfo("Europe/Berlin")
SCENARIOS = ["szenario_haus.json", "szenario_miete.json", "szenario_nur_ablesungen.json", "szenario_wechsel.json"]


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_periods(fixture_data, name):
    sc = fixture_data(name)
    ds, errors = Dataset.from_dict(sc["dataset"])
    assert errors == []
    today = date.fromisoformat(sc["heute"])
    for raw in sc["zaehler"]:
        meter, errs = from_dict(Meter, raw)
        assert errs == []
        chain = [c for c in ds.contracts if c.meter_id == meter.meter_id]
        assert validate_chain(chain) == []
        got = [[p.start_date.isoformat(), p.end_date.isoformat(), p.is_partial, p.is_final] for p in periods_for_chain(chain, today)]
        assert got == sc["erwartet"][meter.meter_id]
        cur = current_period(chain, today)
        assert cur is not None and cur.contains(today)


def test_scenario_readings_only_daily_values(fixture_data):
    sc = fixture_data("szenario_nur_ablesungen.json")
    ds, _ = Dataset.from_dict(sc["dataset"])
    meter, _ = from_dict(Meter, sc["zaehler"][0])
    tw = sc["tageswerte"]
    days = daily_from_readings(meter, ds.readings, date.fromisoformat(tw["von"]), date.fromisoformat(tw["bis"]), TZ)
    by = {d.date: d for d in days}
    assert by[date(2026, 1, 15)].consumption == pytest.approx(tw["januar_tag"])
    assert by[date(2026, 2, 15)].consumption == pytest.approx(tw["februar_tag"])
    assert by[date(2026, 2, 15)].quality == Quality.INTERPOLATED
    missing_from = date.fromisoformat(tw["fehlend_ab"])
    assert all(d.consumption is None and d.quality == Quality.MISSING for d in days if d.date >= missing_from)
