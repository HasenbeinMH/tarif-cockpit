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

from datetime import date, datetime, timedelta
import logging

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_NOTICE, EVENT_VERDICT, ISSUE_NOTICE, NOTICE_WARN_DAYS, signal_updated
from collections import deque

from .engine import billing
from .engine.balance import HEAT_MEDIA, MeterResult, PowerHeat, evaluate_meter
from .engine.burner import current_power, max_gap_for
from .engine.pulses import offset_at, unit_per_pulse
from .engine.archive import build_archive, close_criteria
from .engine.degree_days import degree_days
from .engine.reconcile import Reconciliation, reconcile
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
        self.reconciliations: dict[str, Reconciliation] = {}
        self.forecast_dd: dict = {}  # Gradtage aus der Wettervorhersage (Datum → Kd)
        self._forecast_at: datetime | None = None
        self._pulses: dict[str, deque] = {}  # letzte Zählerstand-Wechsel je Impulszähler (Momentanleistung)
        self._models: dict[str, HeatModel] = {}
        self._samples: dict[str, tuple[list, bool]] = {}  # Stichproben zum Modell (Streudiagramm ohne Neuberechnung)
        self._dirty: dict[str, set[str]] = {m: set(ALL) for m in rt.meters}
        self._debouncer = Debouncer(hass, _LOGGER, cooldown=STATE_DEBOUNCE_S, immediate=False, function=self._async_refresh_dirty)

    # ------------------------------------------------------------ Steuerung

    @callback
    def async_start(self) -> None:
        if self.rt.household.weather_entity:
            from homeassistant.helpers.event import async_track_time_interval  # noqa: PLC0415

            async def _weather(_=None) -> None:
                await self.async_update_weather()

            self.rt.unsubs.append(async_track_time_interval(self.hass, _weather, timedelta(hours=6)))
            from homeassistant.helpers.event import async_call_later  # noqa: PLC0415

            self.rt.unsubs.append(async_call_later(self.hass, 60, _weather))  # Wetter-Integration lädt ggf. später
        entities = {m.entity for m in self.rt.meters.values() if m.entity}
        # Impulszähler: aktuellen Stand als Ausgangspunkt für die Leistung (nach einem Neustart sonst leer)
        for m in self.rt.meters.values():
            if m.pulse_constant and m.entity:
                st = self.hass.states.get(m.entity)
                v = self._raw_value(m, st)
                if v is not None:
                    self._pulses.setdefault(m.meter_id, deque(maxlen=50)).append((st.last_changed, v))
        if entities:
            self.rt.unsubs.append(async_track_state_change_event(self.hass, sorted(entities), self._on_state))
        self.rt.unsubs.append(self._debouncer.async_shutdown)
        # nach einem Neustart: Perioden, die während der Pause geendet haben, und Kündigungsfristen gleich prüfen
        self.archive_ended()
        self.check_notice()

    @callback
    def _on_state(self, event: Event[EventStateChangedData]) -> None:
        for m in self.rt.meters.values():
            if m.entity == event.data["entity_id"]:
                if m.pulse_constant:
                    v = self._raw_value(m, event.data.get("new_state"))
                    if v is not None:
                        last = self.rt.data.sensor_last_raw.get(m.meter_id)
                        if last is not None and v < last - 1e-9:
                            self.rt.add_reset(m.meter_id, dt_util.now(), last)  # Zähler neu gestartet
                        if last is None or abs(v - last) > 1e-12:
                            self.rt.data.sensor_last_raw[m.meter_id] = v
                            # nur echte Wertänderungen sind Impulse (nicht unavailable → gleicher Wert, Attribute)
                            self._pulses.setdefault(m.meter_id, deque(maxlen=50)).append((dt_util.now(), v))
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

    @staticmethod
    def _raw_value(m: Meter, st) -> float | None:
        """Stand des Zähler-Sensors in der Zählereinheit (Impulszähler: Impulse × Menge je Impuls)."""
        if st is None or st.state in ("unavailable", "unknown", ""):
            return None
        try:
            if m.pulse_constant:
                k = unit_per_pulse(m.pulse_constant, m.pulse_mode)
                return float(st.state) * k if k else None
            return convert(float(st.state), st.attributes.get("unit_of_measurement"), m.unit)
        except (TypeError, ValueError):
            return None

    def sensor_raw(self, meter_id: str) -> float | None:
        """Sensorstand in der Zählereinheit; Impulszähler über Neustarts durchlaufend."""
        m = self.rt.meters[meter_id]
        v = self._raw_value(m, self.hass.states.get(m.entity)) if m.entity else None
        if v is not None and m.pulse_constant:
            v += offset_at(self.rt.resets(meter_id), dt_util.now())
        return v

    def kwh_per_unit(self, meter: Meter) -> float | None:
        contract = billing.contract_on(self.rt.contracts(meter.meter_id), self.rt.today())
        segs = [p for p in self.rt.data.prices if contract is not None and p.contract_id == contract.contract_id]
        return billing.energy_factor(meter, billing.segment_on(segs, self.rt.today()))

    def gas_power(self, meter_id: str) -> float | None:
        """Momentanleistung (kW) aus den letzten Impulsen."""
        m = self.rt.meters[meter_id]
        f = self.kwh_per_unit(m)
        pts = list(self._pulses.get(meter_id, ()))
        if not f or not pts:
            return None
        return current_power(pts, dt_util.now(), f, max_gap_for(unit_per_pulse(m.pulse_constant, m.pulse_mode), f, self.boiler_min_power(m)))

    def boiler_min_power(self, m: Meter) -> float | None:
        """Kleinste Leistung der Gastherme an diesem Zähler als Gaseinsatz nach Brennwert (kW)."""
        from .engine.generators import BOILER_EFFICIENCY, HS_HI  # noqa: PLC0415
        from .engine.model import PowerBasis  # noqa: PLC0415

        b = next((g for g in self.rt.generators.values() if g.kind == GeneratorKind.GAS_BOILER and g.meter_id == m.meter_id and g.min_kw), None)
        if b is None:
            return None
        return b.min_kw * HS_HI if b.power_basis == PowerBasis.INPUT else b.min_kw / (b.efficiency or BOILER_EFFICIENCY) * HS_HI

    def _current(self, meter_id: str) -> tuple[datetime, float] | None:
        m = self.rt.meters[meter_id]
        if not m.entity:
            return None
        value = self.sensor_raw(meter_id)
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

    async def async_update_weather(self) -> None:
        """Wettervorhersage (täglich) → Gradtage der nächsten Tage für die Rest-Prognose (Arbeitspaket 3.2)."""
        hh = self.rt.household
        entity = hh.weather_entity
        if not entity or self.hass.states.get(entity) is None:
            return
        try:
            resp = await self.hass.services.async_call("weather", "get_forecasts", {"type": "daily"}, target={"entity_id": entity},
                                                       blocking=True, return_response=True)
        except Exception as err:  # noqa: BLE001 - ohne Vorhersage rechnet die Prognose wie bisher
            _LOGGER.debug("Tarif-Cockpit: Wettervorhersage nicht verfügbar: %s", err)
            return
        out: dict = {}
        today = self.rt.today()
        for item in ((resp or {}).get(entity) or {}).get("forecast", []) or []:
            try:
                d = dt_util.parse_datetime(item["datetime"]).astimezone(self.rt.tz).date()
                hi = float(item["temperature"])
                lo = item.get("templow")
                t = (hi + float(lo)) / 2 if lo is not None else hi
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            if d >= today:
                out[d] = degree_days(t, hh.heating_limit, hh.indoor_ref)
        self._forecast_at = dt_util.utcnow()
        if out != self.forecast_dd:
            self.forecast_dd = out
            self.mark([m.meter_id for m in self.rt.meters.values()], {"forecast"})

    def _heat_inputs(self, meter: Meter) -> dict:
        """Zusätzliche Eingaben für ``evaluate_meter`` aus Situation und Wärmeerzeugern (Arbeitspaket 2.4/3.2)."""
        rt = self.rt
        gens = list(rt.generators.values())
        kw: dict = {}
        if self.forecast_dd and self._forecast_at and dt_util.utcnow() - self._forecast_at < timedelta(hours=24):
            today = rt.today()
            kw["forecast_dd"] = {d: v for d, v in self.forecast_dd.items() if d >= today}  # Vorhersage höchstens 24 h alt
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
            if meter.entity and rt.readings(meter_id) and meter.role != "main" and not rt.contracts(meter_id):
                self.reconciliations[meter_id] = reconcile(meter, rt.data.readings, rt.daily(meter_id), rt.tz)
            if meter.role != "main" and not rt.contracts(meter_id):
                continue  # Unterzähler ohne eigenen Vertrag: fließen in den Hauptzähler ein
            refit = bool(flags & {"consumption", "forecast"}) or meter_id not in self._models
            subs = [m for m in rt.meters.values() if m.parent_meter_id == meter_id]
            wallbox = next((rt.daily(m.meter_id) for m in subs if m.role == "wallbox"), None)
            garden = next((rt.daily(m.meter_id) for m in subs if m.role == "garden"), None)
            rec = None
            if meter.entity and rt.readings(meter_id):
                rec = reconcile(meter, rt.data.readings, rt.daily(meter_id), rt.tz)
                self.reconciliations[meter_id] = rec
            try:
                res = evaluate_meter(
                    meter, rt.contracts(meter_id), rt.data.prices, rt.data.advance_plans, rt.data.payments,
                    rt.readings(meter_id), rt.daily(meter_id), now, rt.tz, self._current(meter_id),
                    rt.household.tolerance_pct, rt.actual_ends(meter_id), sub_daily=wallbox, garden_daily=garden,
                    heat_model_override=None if refit else self._models.get(meter_id),
                    **self._heat_inputs(meter),
                    sensor_offset=rec.offset if rec is not None else None,
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
                rt.sync_periods()
                self._archive_period(meter_id, old.period.period_id, old)
            elif (old is not None and old.balance is not None and res.balance is not None and old.period is not None
                  and res.period is not None and old.period.period_id == res.period.period_id
                  and old.balance.verdict and res.balance.verdict and old.balance.verdict != res.balance.verdict):
                self._fire_verdict(meter, old, res)
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
            recommended_advance=res.balance.recommended_advance, saldo=res.balance.saldo, verdict=res.balance.verdict,
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
        self.archive_ended()
        self.check_notice()

    # ------------------------------------------------------------ Archiv (1.0)

    def _device_id(self, meter_id: str) -> str | None:
        from homeassistant.helpers import device_registry as dr  # noqa: PLC0415

        dev = next((d for d in dr.async_entries_for_config_entry(dr.async_get(self.hass), self.rt.entry.entry_id)
                    if (DOMAIN, meter_id) in d.identifiers), None)
        return dev.id if dev else None

    def _fire_verdict(self, meter: Meter, old: MeterResult, res: MeterResult) -> None:
        """Event bei Urteilswechsel innerhalb derselben Periode (für Benachrichtigungen per Automation)."""
        self.hass.bus.async_fire(EVENT_VERDICT, {
            "zaehler": meter.meter_id, "device_id": self._device_id(meter.meter_id), "name": meter.name,
            "alt": old.balance.verdict, "neu": res.balance.verdict, "saldo": res.balance.saldo,
            "prognose_kosten": res.balance.forecast_cost,
            "qualitaet": res.forecast.quality.value if res.forecast else None,
            "abschlag_empfohlen": res.balance.recommended_advance,
        })

    def _result_at_end(self, meter_id: str, period, allow_partial: bool = False) -> tuple[MeterResult | None, date | None]:
        """Ergebnis einer beendeten Periode, gerechnet zum Periodenende (Endablesung bzw. Stand am Ende des letzten Tages).

        Fehlt der Endstand des letzten Tages, mit ``allow_partial`` der letzte bekannte Stand der Periode (zweiter Wert:
        Tag, bis zu dem die Tageswerte reichen), sonst kein Ergebnis."""
        from .engine.consumption import day_bounds  # noqa: PLC0415

        rt = self.rt
        meter = rt.meters[meter_id]
        end_dt = day_bounds(period.end_date, rt.tz)[1]
        current = None
        until: date | None = None
        if meter.entity:
            daily = rt.daily(meter_id)
            d = daily.get(period.end_date)
            if d is None or d.end_value is None:
                last = max((k for k, v in daily.items() if period.start_date <= k < period.end_date and v.end_value is not None), default=None)
                if not allow_partial or last is None:
                    return None, None
                until, d = last, daily[last]
                current = (day_bounds(last, rt.tz)[1], d.end_value)
            else:
                current = (end_dt, d.end_value)  # end_value ist schon durchlaufend (Neustarts eingerechnet)
        rec = reconcile(meter, rt.data.readings, rt.daily(meter_id), rt.tz) if meter.entity and rt.readings(meter_id) else None
        subs = [m for m in rt.meters.values() if m.parent_meter_id == meter_id]
        return evaluate_meter(
            meter, rt.contracts(meter_id), rt.data.prices, rt.data.advance_plans, rt.data.payments, rt.readings(meter_id),
            rt.daily(meter_id), (current[0] if until else end_dt) - timedelta(seconds=1), rt.tz, current, rt.household.tolerance_pct,
            rt.actual_ends(meter_id),
            sub_daily=next((rt.daily(m.meter_id) for m in subs if m.role == "wallbox"), None),
            garden_daily=next((rt.daily(m.meter_id) for m in subs if m.role == "garden"), None),
            **{k: v for k, v in self._heat_inputs(meter).items() if k != "forecast_dd"},
            sensor_offset=rec.offset if rec is not None else None,
        ), until

    def _archive_period(self, meter_id: str, period_id: str, res: MeterResult | None = None) -> bool:
        rt = self.rt
        period = rt.stored_period(period_id)
        if period is None or period.status.value == "closed":
            return False
        final, reason, reading = close_criteria(period.end_date, rt.readings(meter_id), rt.data.invoices, period.contract_id, rt.today(), rt.tz)
        until = None
        try:
            # nach 60 Tagen wird auch ohne Endstand abgeschlossen (Kosten bis zum letzten bekannten Tag, gekennzeichnet)
            at_end, until = self._result_at_end(meter_id, period, allow_partial=reason == "frist_60_tage")
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Tarif-Cockpit: Archiv für Periode %s nicht berechenbar", period_id)
            return False
        if at_end is None:
            # Endstand fehlt (z. B. um Mitternacht vor dem Tageslauf): nie endgültig, höchstens vorläufig mit dem letzten Ergebnis
            final = False
            if res is None or res.period is None or res.period.period_id != period_id:
                return False
        else:
            res = at_end
        if res.period is None or res.period.period_id != period_id:
            return False
        archive = build_archive(res, rt.data.snapshots, rt.data.prices, final, dt_util.now(rt.tz), reason, until)
        return rt.store_archive(period_id, archive, final, reading.reading_id if reading else None)

    @callback
    def archive_ended(self) -> int:
        """Beendete Perioden archivieren: vorläufig, endgültig bei Endablesung, Rechnung oder nach 60 Tagen."""
        n = 0
        for meter_id in self.rt.meters:
            for p in self.rt.stored_periods(meter_id):
                if p.status.value != "closed" and self._archive_period(meter_id, p.period_id):
                    n += 1
        return n

    # ------------------------------------------------------------ Kündigungsfrist (1.0)

    @callback
    def check_notice(self) -> None:
        from homeassistant.helpers import issue_registry as ir  # noqa: PLC0415

        rt = self.rt
        today = rt.today()
        reg = ir.async_get(self.hass)
        for (domain, issue_id) in list(reg.issues):
            # Hinweise entfernter Zähler aufräumen
            if domain == DOMAIN and issue_id.startswith(f"{ISSUE_NOTICE}_") and issue_id[len(ISSUE_NOTICE) + 1:] not in rt.meters:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        for meter_id, meter in rt.meters.items():
            if meter.role != "main":
                continue
            contract = billing.contract_on(rt.contracts(meter_id), today)
            issue_id = f"{ISSUE_NOTICE}_{meter_id}"
            deadline, end, _kind = billing.notice_deadline(contract, today) if contract else (None, None, "")
            days = (deadline - today).days if deadline else None
            if days is not None and 0 <= days <= NOTICE_WARN_DAYS:
                ir.async_create_issue(self.hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING,
                                      translation_key=ISSUE_NOTICE, translation_placeholders={
                                          "meter": meter.name or meter_id, "lieferant": contract.supplier,
                                          "bis": deadline.isoformat(), "ende": end.isoformat() if end else "", "tage": str(days)})
                key = f"{meter_id}:{deadline.isoformat()}:{days}"
                if days in (NOTICE_WARN_DAYS, 0) and key not in rt.data.notices_sent:
                    # je Zähler, Frist und Stufe nur einmal (auch über Neustarts und „Vertrag ändern“)
                    rt.data.notices_sent.append(key)
                    rt.store.schedule_save(rt.data)
                    self.hass.bus.async_fire(EVENT_NOTICE, {"zaehler": meter_id, "device_id": self._device_id(meter_id), "name": meter.name,
                                                            "lieferant": contract.supplier, "kuendigen_bis": deadline.isoformat(),
                                                            "vertragsende": end.isoformat() if end else None, "tage": days})
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

