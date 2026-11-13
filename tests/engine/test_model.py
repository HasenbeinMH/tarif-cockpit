"""Datenmodell: Hin- und Rückumwandlung, Fehlerlisten, Konsistenz, keine HA-Imports im Rechenkern."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import re

import pytest

from engine.model import (
    AdvancePlan, AdvanceStep, BillingPeriod, BillingRule, Contract, DailyConsumption, Dataset, ForecastSnapshot,
    IntervalConsumption, Invoice, Meter, Payment, PriceSegment, Reading, from_dict, to_dict,
)
from engine.quality import Quality

UTC = timezone.utc


def full_dataset() -> Dataset:
    c = Contract("c1", "m1", "Stadtwerke", date(2026, 1, 1), BillingRule.CALENDAR_YEAR, tariff="Basis")
    r1 = Reading("r1", "m1", datetime(2026, 1, 1, tzinfo=UTC), 100.0)
    return Dataset(
        readings=[r1],
        daily=[DailyConsumption("m1", date(2026, 1, 1), 3.5, quality=Quality.REAL)],
        contracts=[c],
        periods=[BillingPeriod("c1-2026-01-01", "c1", date(2026, 1, 1), date(2026, 12, 31), start_reading="r1")],
        prices=[PriceSegment("c1", date(2026, 1, 1), 0.31, 12.5, components={"energy": 0.15})],
        advance_plans=[AdvancePlan("c1", [AdvanceStep(date(2026, 1, 1), 165.0)], pay_day=15)],
        payments=[Payment("p1", "c1", date(2026, 1, 15), 165.0)],
        invoices=[Invoice("i1", "c1", date(2027, 1, 20), date(2026, 1, 1), date(2026, 12, 31), 1980.0, period_id="c1-2026-01-01")],
        snapshots=[ForecastSnapshot("c1-2026-01-01", datetime(2026, 3, 1, tzinfo=UTC), Quality.ASSUMPTION, forecast_cost=2300.0)],
        intervals=[IntervalConsumption("m1", datetime(2026, 1, 1, tzinfo=UTC), 15, 0.2, Quality.REAL)],
    )


def test_roundtrip_full_dataset():
    ds = full_dataset()
    back, errors = Dataset.from_dict(ds.to_dict())
    assert errors == []
    assert back == ds


def test_unknown_and_missing_fields_are_reported_not_dropped():
    data = full_dataset().to_dict()
    data["readings"][0]["surprise"] = 1
    del data["contracts"][0]["supplier"]
    ds, errors = Dataset.from_dict(data)
    assert ds is None
    assert any("surprise: unbekanntes Feld" in e for e in errors)
    assert any("supplier: Pflichtfeld fehlt" in e for e in errors)


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: d["readings"][0].update(timestamp="2026-01-01T00:00:00"), "ohne Zeitzone"),
        (lambda d: d["readings"][0].update(value="12"), "Zahl erwartet"),
        (lambda d: d["readings"][0].update(quality="gut"), "unbekannter Wert"),
        (lambda d: d["daily"][0].update(quality="missing"), "missing und hat trotzdem"),
        (lambda d: d["periods"][0].update(contract_id="xx"), "Vertrag xx fehlt"),
        (lambda d: d["readings"].append(dict(d["readings"][0])), "doppelt"),
        (lambda d: d["periods"][0].update(start_reading="nope"), "Ablesung nope fehlt"),
    ],
)
def test_invalid_data_is_detected(mutate, needle):
    data = full_dataset().to_dict()
    mutate(data)
    ds, errors = Dataset.from_dict(data)
    assert ds is None
    assert any(needle in e for e in errors), errors


def test_missing_consumption_stays_none():
    d = DailyConsumption("m1", date(2026, 1, 2))
    assert d.consumption is None and d.quality == Quality.MISSING
    assert to_dict(d)["consumption"] is None


def test_meter_from_subentry_style_dict():
    m, errors = from_dict(Meter, {"meter_id": "m1", "medium": "gas", "unit": "m³", "conversion": {"calorific": 11.2, "z_factor": 0.95}})
    assert errors == [] and m.conversion.z_factor == 0.95


def test_engine_has_no_homeassistant_imports():
    engine = Path(__file__).resolve().parents[2] / "custom_components" / "tarif_cockpit" / "engine"
    pattern = re.compile(r"^\s*(from|import)\s+homeassistant", re.M)
    offenders = [p.name for p in engine.glob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
