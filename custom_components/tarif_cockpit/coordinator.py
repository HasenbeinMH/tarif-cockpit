"""Ereignisgesteuerter Coordinator (Entscheidung H): Neuberechnung je Zähler mit Dirty-Flags.

| Auslöser | Flags |
|---|---|
| Zählerstand (entprellt 30 s), Tageswechsel | consumption, forecast, costs, payments |
| Ablesung | consumption, forecast, costs, payments |
| Preis | costs (Prognose-Mengen bleiben, die Regression wird nicht neu gerechnet) |
| Abschlagsplan, Zahlung | payments |
| täglich 00:05 | alles (Konsistenzprüfung) |

Das Wärmemodell (Regression) wird nur bei ``consumption``/``forecast`` neu geschätzt; sonst bleibt das letzte Modell.
Prognose-Schnappschüsse (Entscheidung L): am 1. jedes Monats und am Ende jeder Periode eingefroren.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import signal_updated
from .engine.balance import HEAT_MEDIA, MeterResult, PowerHeat, evaluate_meter
from .engine.generators import ON_POWER_KINDS, GeneratorResult, evaluate_generator, stove_relief_per_hour
from .engine.model import ForecastSnapshot, GeneratorKind, HeatGenerator, Medium, Meter
from .engine.regression import HeatModel
from .engine.units import convert
from .runtime import TarifRuntime

_LOGGER = logging.getLogger(__name__)

ALL = frozenset({"consumption", "forecast", "costs", "payments"})
STATE_DEBOUNCE_S = 30


class TarifCoordinator:
    def __init__(self, hass: HomeAssistant, rt: TarifRuntime) -> None:
        self.hass = hass
        self.rt = rt
        self.results: dict[str, MeterResult] = {}
        self.gen_results: dict[str, GeneratorResult] = {}
        self._models: dict[str, HeatModel] = {}
        self._samples: dict[str, tuple[list, bool]] = {}  # Stichproben zum Modell (Streudiagramm ohne Neuberechnung)
        self._dirty: dict[str, set[str]] = {m: set(ALL) for m in rt.meters}
        self._debouncer = Debouncer(hass, _LOGGER, cooldown=STATE_DEBOUNCE_S, immediate=False, function=self._async_refresh_dirty)

    # ------------------------------------------------------------ Steuerung

    @callback
    def async_start(self) -> None:
        entities = {m.entity for m in self.rt.meters.values() if m.entity}
        if entities:
            self.rt.unsubs.append(async_track_state_change_event(self.hass, sorted(entities), self._on_state))
        self.rt.unsubs.append(self._debouncer.async_shutdown)

    @callback
    def _on_state(self, event: Event[EventStateChangedData]) -> None:
        for m in self.rt.meters.values():
            if m.entity == event.data["entity_id"]:
                self.mark(m.meter_id, ALL, debounce=True)

    @callback
    def mark(self, meter_ids: str | list[str] | None, flags: set[str] | frozenset[str], debounce: bool = False) -> None:
        """Zähler als veraltet markieren. Ohne debounce sofort neu rechnen (Aktionen), sonst entprellt (Sensoren)."""
        ids = list(self.rt.meters) if meter_ids is None else ([meter_ids] if isinstance(meter_ids, str) else meter_ids)
        for mid in ids:
            # Haupt- und Unterzähler hängen zusammen (Wallbox, Gartenwasser)
            self._dirty.setdefault(mid, set()).update(flags)
            parent = self.rt.meters[mid].parent_meter_id if mid in self.rt.meters else None
            if parent in self.rt.meters:
                self._dirty.setdefault(parent, set()).update(flags)
        if debounce:
            self.hass.async_create_task(self._debouncer.async_call())
        else:
            self.async_refresh_now()

    @callback
    def async_refresh_now(self) -> None:
        self._refresh()

    async def _async_refresh_dirty(self) -> None:
        self._refresh()

    # ------------------------------------------------------------ Rechnen

    def _current(self, meter_id: str) -> tuple[datetime, float] | None:
        m = self.rt.meters[meter_id]
        if not m.entity:
            return None
        st = self.hass.states.get(m.entity)
        value: float | None = None
        if st is not None and st.state not in ("unavailable", "unknown", ""):
            try:
                value = convert(float(st.state), st.attributes.get("unit_of_measurement"), m.unit)
            except (TypeError, ValueError):
                value = None
        if value is not None:
            return dt_util.now(), value
        # Sensor gerade nicht verfügbar: letzter bekannter Stand = Ende von gestern aus der Statistik (nie die Startablesung)
        today = dt_util.now(self.rt.tz).date()
        y = self.rt.daily(meter_id).get(today - timedelta(days=1))
        if y is not None and y.end_value is not None:
            return datetime.combine(today, datetime.min.time(), tzinfo=self.rt.tz), y.end_value
        return None

    # ------------------------------------------------------------ Wärmeerzeuger

    def heat_meter_id(self) -> str | None:
        """Der Wärmezähler (Gas/Fernwärme), den Ofen und Klimageräte entlasten: der erste Hauptzähler dieser Medien."""
        for m in self.rt.meters.values():
            if m.role == "main" and m.medium in HEAT_MEDIA:
                return m.meter_id
        return None

    def _gen_series(self, gens: list[HeatGenerator], attr: str) -> dict:
        out: dict = {}
        for g in gens:
            for day, v in self.rt.generator_daily(g.generator_id).items():
                val = getattr(v, attr)
                if val is not None:
                    out[day] = (out.get(day) or 0.0) + val
        return out

    def _heat_inputs(self, meter: Meter) -> dict:
        """Zusätzliche Eingaben für ``evaluate_meter`` aus Situation und Wärmeerzeugern (Arbeitspaket 2.4/3.2)."""
        rt = self.rt
        gens = list(rt.generators.values())
        kw: dict = {}
        if meter.role != "main":
            return kw
        if meter.medium in HEAT_MEDIA:
            kw["hot_water"] = self.hot_water_on(meter)
            if meter.meter_id == self.heat_meter_id():
                stoves = [g for g in gens if g.kind == GeneratorKind.FIREPLACE]
                if stoves:
                    kw["stove_hours"] = self._gen_series(stoves, "hours")
                    kw["stove_relief"] = stove_relief_per_hour(stoves[0], meter.medium)
                hps = [g for g in gens if g.kind in ON_POWER_KINDS and g.meter_id != meter.meter_id]
                if hps:
                    kw["hp_energy"] = self._gen_series(hps, "energy_input")
        elif meter.medium == Medium.STROM:
            own = [g for g in gens if g.meter_id == meter.meter_id and g.kind in ON_POWER_KINDS]
            on_power = [g for g in gens if g.on_household_power and g.kind in ON_POWER_KINDS]
            if own:
                # eigener Zähler der Wärmepumpe (WP-Tarif): der ganze Zähler ist Heizstrom
                kw["power_heat"] = PowerHeat(measured={d: v.consumption for d, v in rt.daily(meter.meter_id).items()}, whole_meter=True)
            elif on_power and meter.meter_id == self.main_power_id():
                measured = all(g.entities.get("energy") or g.entities.get("power") for g in on_power)
                kw["power_heat"] = PowerHeat(measured=self._gen_series(on_power, "energy_input") if measured else None)
        return kw

    def hot_water_on(self, meter: Meter) -> bool:
        """Läuft Warmwasser über die Heizung dieses Zählers? Ohne Antwort (Haushalt aus 0.6) wie bisher: ja.
        Solarthermie unterstützt nur, das Warmwasser kommt dann weiterhin auch über die Heizung."""
        hw = self.rt.household.situation.get("hot_water")
        own_dhw = any(g.central_dhw and g.meter_id == meter.meter_id for g in self.rt.generators.values())
        return hw is None or hw in ("heizung", "solarthermie") or own_dhw

    def main_power_id(self) -> str | None:
        own = {g.meter_id for g in self.rt.generators.values() if g.meter_id}
        for m in self.rt.meters.values():
            if m.role == "main" and m.medium == Medium.STROM and m.meter_id not in own:
                return m.meter_id
        return None

    def _refresh_generators(self) -> None:
        rt = self.rt
        today = dt_util.now(rt.tz).date()
        heat_id = self.heat_meter_id()
        for gid, gen in rt.generators.items():
            ref = gen.meter_id if gen.meter_id in self.results else (heat_id if heat_id in self.results else self.main_power_id())
            res = self.results.get(ref) if ref else None
            start = res.period.start_date if res is not None and res.period is not None else today.replace(month=1, day=1)
            model = self._models.get(heat_id) if heat_id else None
            try:
                self.gen_results[gid] = evaluate_generator(gen, rt.generator_daily(gid), start, today, model)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Tarif-Cockpit: Auswertung des Wärmeerzeugers %s fehlgeschlagen", gen.name or gid)

    @callback
    def _refresh(self) -> None:
        rt = self.rt
        now = dt_util.now(rt.tz)
        changed = False
        for meter_id, meter in rt.meters.items():
            flags = self._dirty.pop(meter_id, set())
            if not flags and meter_id in self.results:
                continue
            if meter.role != "main" and not rt.contracts(meter_id):
                continue  # Unterzähler ohne eigenen Vertrag: fließen in den Hauptzähler ein
            refit = bool(flags & {"consumption", "forecast"}) or meter_id not in self._models
            subs = [m for m in rt.meters.values() if m.parent_meter_id == meter_id]
            wallbox = next((rt.daily(m.meter_id) for m in subs if m.role == "wallbox"), None)
            garden = next((rt.daily(m.meter_id) for m in subs if m.role == "garden"), None)
            try:
                res = evaluate_meter(
                    meter, rt.contracts(meter_id), rt.data.prices, rt.data.advance_plans, rt.data.payments,
                    rt.readings(meter_id), rt.daily(meter_id), now, rt.tz, self._current(meter_id),
                    rt.household.tolerance_pct, rt.actual_ends(meter_id), sub_daily=wallbox, garden_daily=garden,
                    heat_model_override=None if refit else self._models.get(meter_id),
                    **self._heat_inputs(meter),
                )
            except Exception:  # noqa: BLE001 - ein Fehler in einem Zähler darf die anderen nicht stoppen
                _LOGGER.exception("Tarif-Cockpit: Auswertung von Zähler %s fehlgeschlagen", meter.name or meter_id)
                continue
            if res.heat_model is not None:
                self._models[meter_id] = res.heat_model
                if res.samples:
                    self._samples[meter_id] = (res.samples, res.samples_per_period)
                elif not refit and meter_id in self._samples:
                    # Modell aus dem Speicher (nur Kosten/Zahlungen geändert): Stichproben fürs Streudiagramm übernehmen
                    res.samples, res.samples_per_period = self._samples[meter_id]
            old = self.results.get(meter_id)
            if old is not None and old.period is not None and res.period is not None and old.period.period_id != res.period.period_id:
                # Periodenwechsel: letzte Prognose der beendeten Periode einfrieren (Entscheidung L, Regel 4)
                if self._snapshot(old, now):
                    rt.store.schedule_save(rt.data)
            self.results[meter_id] = res
            changed = True
        if rt.generators:
            self._refresh_generators()
            changed = True
        if changed:
            async_dispatcher_send(self.hass, signal_updated(rt.entry.entry_id))

    # ------------------------------------------------------------ Schnappschüsse

    def _snapshot(self, res: MeterResult, now: datetime) -> bool:
        """Ein Ergebnis einfrieren (höchstens ein Schnappschuss je Periode und Tag)."""
        rt = self.rt
        if res.period is None or res.balance is None or res.forecast is None:
            return False
        pid = res.period.period_id
        if any(s.period_id == pid and s.taken_at.astimezone(rt.tz).date() == now.date() for s in rt.data.snapshots):
            return False
        rt.data.snapshots.append(ForecastSnapshot(
            period_id=pid, taken_at=dt_util.as_utc(now), quality=res.forecast.quality.value,
            forecast_kwh=res.forecast_total, forecast_cost=res.balance.forecast_cost,
            recommended_advance=res.balance.recommended_advance,
        ))
        return True

    @callback
    def take_snapshots(self, reason: str = "monat") -> int:
        """Prognose je laufender Periode einfrieren."""
        now = dt_util.now(self.rt.tz)
        taken = sum(1 for res in self.results.values() if self._snapshot(res, now))
        if taken:
            _LOGGER.debug("Tarif-Cockpit: %s Prognose-Schnappschüsse (%s)", taken, reason)
        return taken

    @callback
    def daily(self) -> None:
        """Täglich nach der Tagesaggregation: am Monatsersten einfrieren, dann alles neu rechnen.
        Das Periodenende friert ``_refresh`` beim Wechsel der Periode ein."""
        rt = self.rt
        if dt_util.now(rt.tz).date().day == 1 and self.take_snapshots("monat"):
            rt.store.schedule_save(rt.data)
        self.mark(None, ALL)

