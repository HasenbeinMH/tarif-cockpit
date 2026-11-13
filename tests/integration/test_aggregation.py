"""Tagesaggregation aus der Langzeitstatistik des Recorders (echter Recorder, importierte Stundenwerte)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.tarif_cockpit.const import DOMAIN, ISSUE_NO_STATISTICS
from custom_components.tarif_cockpit.engine.quality import Quality

from .conftest import HOUSEHOLD, TODAY, make_entry, meter_subentry, setup

TZ = ZoneInfo("Europe/Berlin")


@pytest.fixture(autouse=True)
async def berlin(recorder_mock, hass: HomeAssistant, freezer):
    """Wie in conftest, aber der Recorder muss vor hass aufgebaut werden."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(TODAY)


def _hours(first: datetime, last: datetime):
    t = first.astimezone(ZoneInfo("UTC"))
    while t <= last.astimezone(ZoneInfo("UTC")):
        yield t
        t += timedelta(hours=1)


async def test_daily_values_from_statistics(hass: HomeAssistant, recorder_mock) -> None:
    start = datetime(2026, 11, 9, 23, tzinfo=TZ)
    end = datetime(2026, 11, 12, 23, tzinfo=TZ)
    sums = [{"start": t, "sum": float(i), "state": float(i)} for i, t in enumerate(_hours(start, end))]
    async_import_statistics(hass, {
        "has_mean": False, "has_sum": True, "mean_type": StatisticMeanType.NONE, "name": "Zähler", "source": "recorder",
        "statistic_id": "sensor.zaehler", "unit_class": "energy", "unit_of_measurement": "kWh",
    }, sums)
    temps = [{"start": t, "mean": 5.0, "min": 4.0, "max": 6.0} for t in _hours(start, end)]
    async_import_statistics(hass, {
        "has_mean": True, "has_sum": False, "mean_type": StatisticMeanType.ARITHMETIC, "name": "Außen", "source": "recorder",
        "statistic_id": "sensor.aussen", "unit_class": "temperature", "unit_of_measurement": "°C",
    }, temps)
    await async_wait_recording_done(hass)

    contract = {"supplier": "SW", "start_date": "2026-11-10", "billing_rule": "calendar_year"}
    entry = make_entry(
        meter_subentry("m1", "Strom", "strom", "kWh", entity="sensor.zaehler", contract=contract),
        household={**HOUSEHOLD, "outdoor_temp_entity": "sensor.aussen"},
    )
    assert await setup(hass, entry)
    await entry.runtime_data.aggregator.async_run(overwrite=True)
    daily = entry.runtime_data.daily("m1")
    for d in (date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)):
        assert daily[d].quality == Quality.REAL, daily[d]
        assert daily[d].consumption == 24.0
        assert daily[d].outdoor_temperature == 5.0
        assert daily[d].degree_days == 15.0
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_NO_STATISTICS}_m1") is None


async def test_meter_without_statistics_raises_issue(hass: HomeAssistant, recorder_mock) -> None:
    contract = {"supplier": "SW", "start_date": "2026-11-10", "billing_rule": "calendar_year"}
    entry = make_entry(meter_subentry("m1", "Strom", "strom", "kWh", entity="sensor.ohne_statistik", contract=contract))
    assert await setup(hass, entry)
    await entry.runtime_data.aggregator.async_run(overwrite=True)
    assert all(d.consumption is None for d in entry.runtime_data.daily("m1").values())
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_NO_STATISTICS}_m1") is not None


async def test_statistics_in_wh_are_converted_to_meter_unit(hass: HomeAssistant, recorder_mock) -> None:
    start = datetime(2026, 11, 9, 23, tzinfo=TZ)
    end = datetime(2026, 11, 12, 23, tzinfo=TZ)
    sums = [{"start": t, "sum": 1000.0 * i, "state": 1000.0 * i} for i, t in enumerate(_hours(start, end))]
    async_import_statistics(hass, {
        "has_mean": False, "has_sum": True, "mean_type": StatisticMeanType.NONE, "name": "Zähler Wh", "source": "recorder",
        "statistic_id": "sensor.zaehler_wh", "unit_class": "energy", "unit_of_measurement": "Wh",
    }, sums)
    await async_wait_recording_done(hass)
    contract = {"supplier": "SW", "start_date": "2026-11-10", "billing_rule": "calendar_year"}
    entry = make_entry(meter_subentry("m1", "Strom", "strom", "kWh", entity="sensor.zaehler_wh", contract=contract))
    assert await setup(hass, entry)
    await entry.runtime_data.aggregator.async_run(overwrite=True)
    assert entry.runtime_data.daily("m1")[date(2026, 11, 11)].consumption == 24.0  # 24 000 Wh = 24 kWh
