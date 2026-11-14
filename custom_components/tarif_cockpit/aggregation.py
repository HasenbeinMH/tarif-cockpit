"""Eigene Tagesaggregation (Entscheidung E): Tageswerte je Zähler im Store, unabhängig vom Recorder.

Quelle für Zähler mit Sensor ist die Langzeitstatistik (Stundenwerte, laufende Summe), für Zähler nur mit
Ablesungen die Ablesungen selbst (linear verteilt). Temperaturen kommen als Stundenmittel aus der Statistik.
Läuft täglich um 00:05 und beim Start (holt fehlende Tage nach). Bestehende Tageswerte von Zählern mit Sensor
überschreibt nur ``recalculate``; fehlende Tage der letzten 7 Tage werden erneut versucht.

Wärmeerzeuger (0.8): Energie und Wärme aus der Statistik (Summe), Leistung als Stundenmittel, Betriebsstunden aus dem
Verlauf der Betriebszustand-Entität; Kaminofen ohne Entität aus der Raumtemperatur (5-Minuten-Statistik). Verlauf und
5-Minuten-Werte hält der Recorder nur einige Tage: Betriebsstunden gibt es ab der Einrichtung (plus diese Tage).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started

from .const import AGG_HOUR, AGG_MINUTE, BACKFILL_DAYS, DOMAIN, ISSUE_NO_STATISTICS, RETRY_MISSING_DAYS
from .engine import billing
from .engine.consumption import aggregate_day, day_bounds, daily_from_readings
from .engine.generators import build_generator_day, is_on, on_hours, stove_hours_from_room
from .engine.model import DailyConsumption, GeneratorDaily, GeneratorKind, HeatGenerator, Medium, Meter
from .engine.quality import Quality, usable
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
        self, ids: set[str], start: datetime, end: datetime, kind: str, units: dict[str, str] | None = None,
        period: str = "hour",
    ) -> dict[str, Series]:
        """Stundenwerte aus der Langzeitstatistik: kind 'sum'/'state' (Zähler) oder 'mean' (Temperatur).
        ``units`` rechnet in die gewünschte Einheit um (z. B. Wh-Sensor → kWh-Zähler)."""
        ids = {i for i in ids if i}
        if not ids or not self._recorder_ready():
            return {}
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415 (Recorder ist optional)
        from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415

        try:
            rows = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, start, end, ids, period, units, {kind}
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
        horizon = self.rt.today() - timedelta(days=BACKFILL_DAYS)
        chain = self.rt.contracts(meter.meter_id)
        if meter.entity:
            # Zähler mit Sensor: auch vor Vertragsbeginn, denn die Prognose braucht das Vorjahr
            first = horizon
        elif chain:
            first = max(chain[0].start_date, horizon)
        else:
            return None
        lo, hi = max(start or first, first), min(end or yesterday, yesterday)
        return (lo, hi) if lo <= hi else None

    def _targets(self, meter: Meter, lo: date, hi: date, overwrite: bool) -> list[date]:
        existing = self.rt.daily(meter.meter_id)
        retry_from = self.rt.today() - timedelta(days=RETRY_MISSING_DAYS)
        days: list[date] = []
        d = lo
        while d <= hi:
            cur = existing.get(d)
            # Mit Ersatzquelle werden fehlende Tage jeden Alters erneut versucht (Ersatzquelle kann nachträglich gesetzt werden)
            retry = cur is not None and cur.quality == Quality.MISSING and (d >= retry_from or meter.history_entity)
            if overwrite or cur is None or retry:
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
            values = await self.async_compute(meter, days, rt.readings(meter.meter_id), check=True)
            changed += rt.put_daily(values)
        if meters is None:
            changed += await self.async_run_generators(start, end, overwrite)
        periods = rt.sync_periods()
        if changed:
            _LOGGER.debug("Tarif-Cockpit: %s Tageswerte aktualisiert", changed)
        rt.changed(save=changed > 0 or periods)
        return changed

    async def async_compute(self, meter: Meter, days: list[date], readings: list, check: bool = False) -> list[DailyConsumption]:
        """Tageswerte für ``days`` berechnen, ohne zu speichern (auch für die Probe-Prognose in der Einrichtung)."""
        if not days:
            return []
        hh = self.rt.household
        tz = self.rt.tz
        readings_based = meter.entity is None
        q_start = day_bounds(days[0], tz)[0] - timedelta(hours=1)
        q_end = day_bounds(days[-1], tz)[1]
        temp_ids = {i for i in [hh.outdoor_temp_entity, *[r.entity for r in hh.rooms]] if i}
        temps = await self._fetch(temp_ids, q_start, q_end, "mean", {"temperature": "°C"})
        sums: Series = {}
        states: Series = {}
        hist: Series = {}
        if not readings_based:
            units = _unit_class(meter.unit)
            sums = (await self._fetch({meter.entity}, q_start, q_end, "sum", units)).get(meter.entity, {})
            states = (await self._fetch({meter.entity}, q_start, q_end, "state", units)).get(meter.entity, {})
            if meter.history_entity:
                hist = (await self._fetch({meter.history_entity}, q_start, q_end, "sum", units)).get(meter.history_entity, {})
            if check:
                self._check_statistics(meter, sums)
        outdoor = temps.get(hh.outdoor_temp_entity or "", {})
        indoor = [temps[r.entity] for r in hh.rooms if r.entity in temps]
        values = []
        for d in days:
            v = aggregate_day(meter.meter_id, d, tz, sums, outdoor, indoor, hh.heating_limit, hh.indoor_ref, states)
            if hist and v.consumption is None and v.quality == Quality.MISSING:
                h = aggregate_day(meter.meter_id, d, tz, hist)
                if h.consumption is not None:
                    # Ersatzquelle: anderer Zähler (z. B. Wechselrichter), daher nur "geschätzt"
                    v = replace(v, consumption=h.consumption, quality=Quality.ESTIMATED,
                                quality_flags=[f for f in v.quality_flags if f != "randwert_fehlt"] + ["ersatzquelle"])
            values.append(v)
        if readings_based:
            by_day = {v.date: v for v in daily_from_readings(meter, readings, days[0], days[-1], tz)}
            values = [_merge_readings(v, by_day.get(v.date)) for v in values]
        return values

    # ------------------------------------------------------------ Wärmeerzeuger

    async def async_run_generators(self, start: date | None = None, end: date | None = None, overwrite: bool = False) -> int:
        rt = self.rt
        if not rt.generators:
            return 0
        today = rt.today()
        yesterday = today - timedelta(days=1)
        horizon = today - timedelta(days=BACKFILL_DAYS)
        retry_from = today - timedelta(days=RETRY_MISSING_DAYS)
        changed = 0
        for gid, gen in rt.generators.items():
            existing = rt.generator_daily(gid)
            lo, hi = max(start or horizon, horizon), min(end or yesterday, yesterday)
            days = []
            d = lo
            while d <= hi:
                cur = existing.get(d)
                if overwrite or cur is None or (d >= retry_from and _gen_empty(cur)):
                    days.append(d)
                d += timedelta(days=1)
            if not days:
                continue
            values = await self.async_compute_generator(gen, days)
            # leere alte Tage nicht speichern (der Recorder hat sie nicht mehr); fehlend bleibt fehlend
            values = [v for v in values if not (_gen_empty(v) and v.date < retry_from)]
            changed += rt.put_generator_daily(values)
        return changed

    async def async_compute_generator(self, gen: HeatGenerator, days: list[date]) -> list[GeneratorDaily]:
        if not days:
            return []
        rt = self.rt
        tz = rt.tz
        q_start = day_bounds(days[0], tz)[0] - timedelta(hours=1)
        q_end = day_bounds(days[-1], tz)[1]
        ent = gen.entities
        energy = (await self._fetch({ent.get("energy", "")}, q_start, q_end, "sum", {"energy": "kWh"})).get(ent.get("energy", ""), {})
        heat = (await self._fetch({ent.get("heat", "")}, q_start, q_end, "sum", {"energy": "kWh"})).get(ent.get("heat", ""), {})
        power = (await self._fetch({ent.get("power", "")}, q_start, q_end, "mean", {"power": "kW"})).get(ent.get("power", ""), {})
        state_changes: list = []
        state_entity = ent.get("state")
        use_state = state_entity and not (gen.kind == GeneratorKind.FIREPLACE and gen.stove_detection == "room")
        if use_state:
            state_changes = await self._state_changes(state_entity, q_start, q_end)
        room_series: Series = {}
        room = gen.room_entity or ent.get("room")
        if gen.kind == GeneratorKind.FIREPLACE and not use_state and room:
            five_start = max(q_start, day_bounds(rt.today() - timedelta(days=12), tz)[0])
            if five_start < q_end:
                room_series = (await self._fetch({room}, five_start, q_end, "mean", {"temperature": "°C"}, "5minute")).get(room, {})
        meter = rt.meters.get(gen.meter_id or "")
        meter_daily = rt.daily(meter.meter_id) if meter is not None and not gen.on_household_power else {}
        any_daily = self._degree_days()
        out = []
        for d in days:
            a, b = day_bounds(d, tz)
            e = aggregate_day(gen.generator_id, d, tz, energy).consumption if energy else None
            h = aggregate_day(gen.generator_id, d, tz, heat).consumption if heat else None
            p_vals = [v for ts, v in power.items() if a <= ts < b]
            p_mean = sum(p_vals) / len(p_vals) if p_vals else None
            hours = None
            if use_state:
                hours = on_hours(state_changes, a, b)
            elif room_series:
                dd = any_daily.get(d)
                if dd is not None and dd > 0:
                    hours = stove_hours_from_room([(ts, v) for ts, v in room_series.items() if a <= ts < b], gen.stove_threshold_k)
                elif dd == 0:
                    hours = 0.0  # außerhalb der Heizperiode zählt kein Ofenbetrieb
            mk = None
            if meter_daily:
                mv = meter_daily.get(d)
                if mv is not None and mv.consumption is not None and usable(mv.quality):
                    mk = self._to_kwh(meter, d, mv.consumption)
            out.append(build_generator_day(gen, d, energy=e, power_mean_kw=p_mean, heat=h, hours=hours, meter_kwh=mk,
                                           power_coverage=len(p_vals) / 24))
        return out

    def _to_kwh(self, meter: Meter, day: date, value: float) -> float | None:
        """Zählereinheit → kWh wie in der Abrechnung (Gas m³: Brennwert/Zustandszahl des Preisabschnitts, sonst des Zählers)."""
        contract = billing.contract_on(self.rt.contracts(meter.meter_id), day)
        segs = [p for p in self.rt.data.prices if contract is not None and p.contract_id == contract.contract_id]
        f = billing.energy_factor(meter, billing.segment_on(segs, day))
        return value * f if f else None

    def _degree_days(self) -> dict[date, float | None]:
        """Gradtage je Tag aus den Tageswerten irgendeines Zählers (alle haben dieselbe Außentemperatur)."""
        out: dict[date, float | None] = {}
        for d in self.rt.data.daily:
            if d.degree_days is not None and d.date not in out:
                out[d.date] = d.degree_days
        return out

    async def _state_changes(self, entity_id: str, start: datetime, end: datetime) -> list:
        """Zustandswechsel aus dem Recorder-Verlauf (inklusive Zustand zu Beginn)."""
        if not self._recorder_ready():
            return []
        from homeassistant.components.recorder import get_instance, history  # noqa: PLC0415

        try:
            states = await get_instance(self.hass).async_add_executor_job(
                lambda: history.get_significant_states(
                    self.hass, start, end, [entity_id], include_start_time_state=True, significant_changes_only=False,
                    minimal_response=False, no_attributes=True,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Tarif-Cockpit: Verlauf von %s nicht lesbar: %s", entity_id, err)
            return []
        return [(s.last_changed.astimezone(self.rt.tz), is_on(s.state)) for s in states.get(entity_id, [])]

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


def _gen_empty(g: GeneratorDaily) -> bool:
    return g.energy_input is None and g.thermal_output is None and g.hours is None


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
        # einmalig nach dem Update auf 0.6: Tageswerte mit Zählerstand am Tagesende neu aus der Statistik holen
        todo = [m.meter_id for m in runtime.meters.values() if m.entity and m.meter_id not in runtime.data.reaggregated_meters]
        if todo:
            await agg.async_run(meters=todo, overwrite=True)
            runtime.data.reaggregated_meters.extend(todo)
        await agg.async_run()
        if runtime.coordinator is not None:
            runtime.coordinator.daily()

    @callback
    def _daily(_: Any = None) -> None:
        # als Aufgabe des Eintrags: wird beim Entladen abgebrochen
        runtime.entry.async_create_background_task(hass, _run(), "tarif_cockpit_daily")

    runtime.unsubs.append(async_track_time_change(hass, _daily, hour=AGG_HOUR, minute=AGG_MINUTE, second=0))
    if hass.state is CoreState.running:
        runtime.entry.async_create_background_task(hass, _run(), "tarif_cockpit_backfill")
    else:
        runtime.unsubs.append(async_at_started(hass, _daily))
