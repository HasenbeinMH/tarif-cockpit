"""Eigene Tagesaggregation (Entscheidung E): Tageswerte je Zähler im Store, unabhängig vom Recorder.

Quelle für Zähler mit Sensor ist die Langzeitstatistik (Stundenwerte, laufende Summe), für Zähler nur mit
Ablesungen die Ablesungen selbst (linear verteilt). Temperaturen kommen als Stundenmittel aus der Statistik.
Läuft täglich um 00:05 und beim Start (holt fehlende Tage nach). Bestehende Tageswerte von Zählern mit Sensor
überschreibt nur ``recalculate``; fehlende Tage der letzten 7 Tage werden erneut versucht.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started

from .const import AGG_HOUR, AGG_MINUTE, BACKFILL_DAYS, DOMAIN, ISSUE_NO_STATISTICS, RETRY_MISSING_DAYS
from .engine.consumption import aggregate_day, day_bounds, daily_from_readings
from .engine.model import DailyConsumption, Meter
from .engine.quality import Quality
from .runtime import TarifRuntime

_LOGGER = logging.getLogger(__name__)

Series = dict[datetime, float]


class Aggregator:
    def __init__(self, hass: HomeAssistant, runtime: TarifRuntime) -> None:
        self.hass = hass
        self.rt = runtime

    # ------------------------------------------------------------ Statistik

    def _recorder_ready(self) -> bool:
        return "recorder" in self.hass.config.components

    async def _fetch(
        self, ids: set[str], start: datetime, end: datetime, kind: str, units: dict[str, str] | None = None
    ) -> dict[str, Series]:
        """Stundenwerte aus der Langzeitstatistik: kind 'sum' (Zähler) oder 'mean' (Temperatur).
        ``units`` rechnet in die gewünschte Einheit um (z. B. Wh-Sensor → kWh-Zähler)."""
        if not ids or not self._recorder_ready():
            return {}
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415 (Recorder ist optional)
        from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415

        try:
            rows = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, start, end, ids, "hour", units, {kind}
            )
        except Exception as err:  # noqa: BLE001 - Statistik darf die Integration nie stoppen
            _LOGGER.warning("Tarif-Cockpit: Langzeitstatistik nicht lesbar: %s", err)
            return {}
        out: dict[str, Series] = {}
        for sid, items in rows.items():
            series: Series = {}
            for row in items:
                val = row.get(kind)
                if val is None:
                    continue
                st = row["start"]
                ts = datetime.fromtimestamp(st, tz=self.rt.tz) if isinstance(st, (int, float)) else st
                series[ts] = float(val)
            out[sid] = series
        return out

    # ------------------------------------------------------------ Lauf

    def _range(self, meter: Meter, start: date | None, end: date | None) -> tuple[date, date] | None:
        yesterday = self.rt.today() - timedelta(days=1)
        chain = self.rt.contracts(meter.meter_id)
        if not chain:
            return None
        first = max(chain[0].start_date, self.rt.today() - timedelta(days=BACKFILL_DAYS))
        lo, hi = max(start or first, first), min(end or yesterday, yesterday)
        return (lo, hi) if lo <= hi else None

    def _targets(self, meter: Meter, lo: date, hi: date, overwrite: bool) -> list[date]:
        existing = self.rt.daily(meter.meter_id)
        retry_from = self.rt.today() - timedelta(days=RETRY_MISSING_DAYS)
        days: list[date] = []
        d = lo
        while d <= hi:
            cur = existing.get(d)
            if overwrite or cur is None or (cur.quality == Quality.MISSING and d >= retry_from):
                days.append(d)
            d += timedelta(days=1)
        return days

    async def async_run(
        self, meters: Iterable[str] | None = None, start: date | None = None, end: date | None = None, overwrite: bool = False
    ) -> int:
        """Tageswerte berechnen und speichern. Liefert die Anzahl geänderter Tage."""
        rt = self.rt
        hh = rt.household
        tz = rt.tz
        changed = 0
        for meter_id in meters or list(rt.meters):
            meter = rt.meters.get(meter_id)
            if meter is None:
                continue
            rng = self._range(meter, start, end)
            if rng is None:
                continue
            # Zähler ohne Sensor: Tageswerte hängen nur an den Ablesungen, also immer neu verteilen
            readings_based = meter.entity is None
            days = self._targets(meter, rng[0], rng[1], overwrite or readings_based)
            if not days:
                continue
            q_start = day_bounds(days[0], tz)[0] - timedelta(hours=1)
            q_end = day_bounds(days[-1], tz)[1]
            temp_ids = {i for i in [hh.outdoor_temp_entity, *[r.entity for r in hh.rooms]] if i}
            temps = await self._fetch(temp_ids, q_start, q_end, "mean", {"temperature": "°C"})
            sums: Series = {}
            if not readings_based:
                sums = (await self._fetch({meter.entity}, q_start, q_end, "sum", _unit_class(meter.unit))).get(meter.entity, {})
                self._check_statistics(meter, sums)
            outdoor = temps.get(hh.outdoor_temp_entity or "", {})
            indoor = [temps[r.entity] for r in hh.rooms if r.entity in temps]
            values = [
                aggregate_day(meter.meter_id, d, tz, sums, outdoor, indoor, hh.heating_limit, hh.indoor_ref) for d in days
            ]
            if readings_based:
                by_day = {v.date: v for v in daily_from_readings(meter, rt.readings(meter.meter_id), days[0], days[-1], tz)}
                values = [_merge_readings(v, by_day.get(v.date)) for v in values]
            changed += rt.put_daily(values)
        periods = rt.sync_periods()
        if changed:
            _LOGGER.debug("Tarif-Cockpit: %s Tageswerte aktualisiert", changed)
        rt.changed(save=changed > 0 or periods)
        return changed

    @callback
    def _check_statistics(self, meter: Meter, sums: Series) -> None:
        issue_id = f"{ISSUE_NO_STATISTICS}_{meter.meter_id}"
        if sums or not self._recorder_ready():
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NO_STATISTICS,
            translation_placeholders={"meter": meter.name or meter.meter_id, "entity": meter.entity or ""},
        )


def _unit_class(unit: str) -> dict[str, str] | None:
    """Einheitenklasse der Statistik für die Umrechnung in die Zählereinheit."""
    if unit in ("Wh", "kWh", "MWh"):
        return {"energy": unit}
    if unit in ("m³", "L"):
        return {"volume": unit}
    return None


def _merge_readings(stat_day: DailyConsumption, read_day: DailyConsumption | None) -> DailyConsumption:
    """Temperaturen aus der Statistik, Verbrauch aus den Ablesungen."""
    if read_day is None:
        return stat_day
    flags = [f for f in stat_day.quality_flags if f != "randwert_fehlt"] + read_day.quality_flags
    return DailyConsumption(
        meter_id=stat_day.meter_id, date=stat_day.date, consumption=read_day.consumption,
        degree_days=stat_day.degree_days, outdoor_temperature=stat_day.outdoor_temperature,
        indoor_temperature=stat_day.indoor_temperature, quality=read_day.quality, quality_flags=flags, source="readings",
    )


@callback
def async_setup_aggregation(hass: HomeAssistant, runtime: TarifRuntime) -> None:
    """Täglicher Lauf um 00:05 und Nachholen nach dem Start."""
    agg = Aggregator(hass, runtime)
    runtime.aggregator = agg

    async def _run(_: Any = None) -> None:
        await agg.async_run()

    @callback
    def _daily(_: Any = None) -> None:
        # als Aufgabe des Eintrags: wird beim Entladen abgebrochen
        runtime.entry.async_create_background_task(hass, _run(), "tarif_cockpit_daily")

    runtime.unsubs.append(async_track_time_change(hass, _daily, hour=AGG_HOUR, minute=AGG_MINUTE, second=0))
    if hass.state is CoreState.running:
        runtime.entry.async_create_background_task(hass, _run(), "tarif_cockpit_backfill")
    else:
        runtime.unsubs.append(async_at_started(hass, _daily))
