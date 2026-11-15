"""Laufzeitdaten eines Haushalts (Config Entry): Store, Datenbestand, Haushalt, Zähler.

Alle Änderungen am Datenbestand laufen über diese Klasse: Ablesungen werden nur angehängt, Verträge nur
über den Folgevertrag geändert, abgeschlossene Perioden nie überschrieben (Regel 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ISSUE_RECONCILE, signal_updated
from .engine import billing
from .engine.model import (
    AdvancePlan, AdvanceStep, BillingPeriod, Calibration, Contract, DayIntervals, DailyConsumption, Dataset, GeneratorDaily, HeatGenerator, Household,
    Invoice, Meter, Payment, PaymentStatus, PaymentType, PeriodStatus, PriceSegment, Reading, ReadingSource, SensorReset, new_id,
)
from .engine.quality import Quality, usable
from .engine.reconcile import Reconciliation, apply_reconciliation, reconcile
from .store import TarifStore

_LOGGER = logging.getLogger(__name__)


class ContractLocked(billing.BillingError):
    """Abrechnungsregel nicht mehr änderbar: eine Periode des Vertrags ist schon gespeichert (beendet)."""


@dataclass
class TarifRuntime:
    hass: HomeAssistant
    entry: ConfigEntry
    store: TarifStore
    data: Dataset
    household: Household
    meters: dict[str, Meter]  # meter_id (= subentry_id) → Zähler
    generators: dict[str, HeatGenerator] = field(default_factory=dict)  # generator_id (= subentry_id) → Wärmeerzeuger
    subentry_ids: frozenset[str] = frozenset()
    unsubs: list[Any] = field(default_factory=list)
    aggregator: Any = None  # aggregation.Aggregator, gesetzt beim Setup
    coordinator: Any = None  # coordinator.TarifCoordinator, gesetzt beim Setup
    subentry_signature: str = ""

    # ------------------------------------------------------------ Hilfen

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.hass.config.time_zone)

    def today(self) -> date:
        return dt_util.now(self.tz).date()

    def contracts(self, meter_id: str) -> list[Contract]:
        return billing.sort_chain([c for c in self.data.contracts if c.meter_id == meter_id])

    def readings(self, meter_id: str) -> list[Reading]:
        return sorted((r for r in self.data.readings if r.meter_id == meter_id), key=lambda r: r.timestamp)

    def daily(self, meter_id: str) -> dict[date, DailyConsumption]:
        return {d.date: d for d in self.data.daily if d.meter_id == meter_id}

    def generator_daily(self, generator_id: str) -> dict[date, GeneratorDaily]:
        return {g.date: g for g in self.data.generator_daily if g.generator_id == generator_id}

    def put_generator_daily(self, values: list[GeneratorDaily]) -> int:
        """Erzeuger-Tageswerte einsetzen bzw. ersetzen; ein Wert wird nie durch einen leeren ersetzt."""
        index = {(g.generator_id, g.date): i for i, g in enumerate(self.data.generator_daily)}
        changed = 0
        for v in values:
            key = (v.generator_id, v.date)
            empty = v.energy_input is None and v.thermal_output is None and v.hours is None
            if key in index:
                cur = self.data.generator_daily[index[key]]
                if empty and not (cur.energy_input is None and cur.thermal_output is None and cur.hours is None):
                    continue
                # feldweise: ein fehlender neuer Wert (z. B. Stunden außerhalb der Recorder-Haltezeit) behält den alten
                merged = replace(v, **{f: getattr(cur, f) for f in ("energy_input", "thermal_output", "estimated_thermal_output", "hours")
                                       if getattr(v, f) is None and getattr(cur, f) is not None})
                if merged.energy_input is not None and v.energy_input is None:
                    merged = replace(merged, measurement_quality=cur.measurement_quality)
                if cur != merged:
                    self.data.generator_daily[index[key]] = merged
                    changed += 1
            else:
                index[key] = len(self.data.generator_daily)
                self.data.generator_daily.append(v)
                changed += 1
        return changed

    def actual_ends(self, meter_id: str) -> dict[str, dict[date, date]]:
        """Abweichende tatsächliche Periodenenden (Ablesetermin) aus den gespeicherten Perioden des Zählers."""
        ids = {c.contract_id for c in self.contracts(meter_id)}
        out: dict[str, dict[date, date]] = {}
        for p in self.data.periods:
            if p.contract_id in ids and p.regular_end and p.regular_end != p.end_date:
                out.setdefault(p.contract_id, {})[p.regular_end] = p.end_date
        return out

    def stored_periods(self, meter_id: str, ended_only: bool = True) -> list[BillingPeriod]:
        """Gespeicherte Perioden des Zählers. ended_only: nur beendete (nicht die Vorgabe der laufenden)."""
        ids = {c.contract_id for c in self.contracts(meter_id)}
        today = self.today()
        out = [p for p in self.data.periods if p.contract_id in ids and (not ended_only or p.end_date < today)]
        return sorted(out, key=lambda p: p.start_date)

    def sync_periods(self) -> bool:
        """Beendete Perioden einfrieren (Regel 3/4): Sie werden gespeichert und danach nicht mehr verändert."""
        today = self.today()
        added = False
        for meter_id in self.meters:
            stored = {p.period_id for p in self.stored_periods(meter_id, ended_only=False)}
            try:
                specs = billing.periods_for_chain(self.contracts(meter_id), today, self.actual_ends(meter_id))
            except billing.BillingError as err:
                _LOGGER.warning("Tarif-Cockpit: Perioden für Zähler %s nicht berechenbar: %s", meter_id, err)
                continue
            for spec in specs:
                if spec.end_date < today and spec.period_id not in stored:
                    bp = billing.to_billing_period(spec, PeriodStatus.CLOSING)
                    if spec.end_date != spec.regular_end and not spec.is_final:
                        bp = replace(bp, regular_end=spec.regular_end)
                    self.data.periods.append(bp)
                    added = True
            # gespeicherte Vorgabe einer inzwischen beendeten Periode: Status nachziehen
            for i, p in enumerate(self.data.periods):
                if p.period_id in stored and p.status == PeriodStatus.OPEN and p.end_date < today:
                    self.data.periods[i] = replace(p, status=PeriodStatus.CLOSING)
                    added = True
        return added

    def current_period(self, meter_id: str, day: date | None = None) -> billing.PeriodSpec | None:
        try:
            return billing.current_period(self.contracts(meter_id), day or self.today(), self.actual_ends(meter_id))
        except billing.BillingError as err:
            _LOGGER.warning("Tarif-Cockpit: Perioden für Zähler %s nicht berechenbar: %s", meter_id, err)
            return None

    def stored_period(self, period_id: str) -> BillingPeriod | None:
        return next((p for p in self.data.periods if p.period_id == period_id), None)

    # ------------------------------------------------------------ Änderungen

    @callback
    def changed(self, save: bool = True, meter_id: str | None = None, flags: frozenset[str] | set[str] | None = None) -> None:
        """Daten geändert: speichern und die betroffenen Zähler neu rechnen (Coordinator), dann Sensoren melden."""
        if save:
            self.store.schedule_save(self.data)
        if self.coordinator is not None:
            # flags=None: alles neu; leere Menge: nichts zu rechnen (z. B. Rechnung erfasst), nur speichern
            self.coordinator.mark(meter_id, frozenset({"consumption", "forecast", "costs", "payments"}) if flags is None else flags)
        else:
            async_dispatcher_send(self.hass, signal_updated(self.entry.entry_id))

    def add_reading(
        self,
        meter_id: str,
        timestamp: datetime,
        value: float,
        quality: Quality = Quality.REAL,
        source: ReadingSource = ReadingSource.MANUAL,
        note: str | None = None,
        replaces: str | None = None,
        sensor_value: float | None = None,
    ) -> Reading:
        """Neue Ablesung anhängen. Mit ``replaces`` wird eine frühere Ablesung als ersetzt markiert (nicht gelöscht).
        ``sensor_value``: Stand des Zähler-Sensors zum Ablesezeitpunkt (für den Abgleich)."""
        reading = Reading(new_id(), meter_id, dt_util.as_utc(timestamp), float(value), quality, source, note,
                          sensor_value=sensor_value)
        if replaces:
            idx = self._reading_index(meter_id, replaces)
            target = self.data.readings[idx]
            if target.superseded_by or target.quality == Quality.INVALID:
                # nur die jeweils gültige Ablesung lässt sich ersetzen, sonst gäbe es zwei gültige Stände
                raise ValueError(target.superseded_by or target.reading_id)
            self.data.readings[idx] = replace(target, superseded_by=reading.reading_id)
        self.data.readings.append(reading)
        return reading

    async def after_readings_changed(self, meter_id: str) -> None:
        """Nach neuen/korrigierten Ablesungen: Tageswerte von Zählern ohne Sensor neu verteilen, speichern, melden."""
        if self.aggregator is not None and self.meters[meter_id].entity is None:
            await self.aggregator.async_run(meters=[meter_id], overwrite=True)
        else:
            self.reconcile_meter(meter_id)
            self.changed(meter_id=meter_id)

    def store_archive(self, period_id: str, archive: dict, final: bool, end_reading: str | None) -> bool:
        """Archiv einer beendeten Periode speichern. Endgültig abgeschlossene Perioden ändern sich nie mehr (Regel 4)."""
        for i, p in enumerate(self.data.periods):
            if p.period_id != period_id:
                continue
            if p.status == PeriodStatus.CLOSED:
                return False
            new = replace(p, archive=archive, status=PeriodStatus.CLOSED if final else PeriodStatus.CLOSING,
                          archived_at=dt_util.utcnow() if final else p.archived_at, end_reading=end_reading or p.end_reading)
            if new != p:
                self.data.periods[i] = new
                self.store.schedule_save(self.data)
                return True
            return False
        return False

    def set_contract_terms(
        self, meter_id: str, tariff: str | None, min_term_months: int | None, notice_period_weeks: int | None,
        billing_rule: Any = None, fixed_day: str | None = None,
    ) -> Contract:
        """Vertragsdaten des laufenden Vertrags ändern: Tarifname, Mindestlaufzeit, Kündigungsfrist und (1.0.3) die
        Abrechnungsregel mit Stichtag. Die Regel nur, solange von diesem Vertrag noch keine Periode gespeichert ist
        (beendete Perioden bleiben unverändert, Regel 3/4); sonst ``ContractLocked``."""
        from .engine.model import BillingRule  # noqa: PLC0415

        contract = billing.contract_on(self.contracts(meter_id), self.today()) or (self.contracts(meter_id) or [None])[-1]
        if contract is None:
            raise billing.BillingError("Für diesen Zähler gibt es keinen Vertrag")
        new = replace(contract, tariff=tariff, min_term_months=min_term_months, notice_period_weeks=notice_period_weeks)
        if billing_rule is not None:
            rule = BillingRule(billing_rule)
            fixed = fixed_day.strip() if rule == BillingRule.FIXED_DAY and fixed_day else None

            def key(r: BillingRule, f: str | None) -> tuple:
                if r != BillingRule.FIXED_DAY:
                    return (r,)
                try:
                    return (r, billing.parse_fixed_day(f))
                except billing.BillingError:
                    return (r, f)

            if key(rule, fixed) != key(contract.billing_rule, contract.fixed_day):
                if rule == BillingRule.MANUAL or contract.billing_rule == BillingRule.MANUAL:
                    raise billing.BillingError("Perioden von Hand lassen sich hier nicht umstellen")
                self.sync_periods()  # eine gerade beendete, noch nicht gespeicherte Periode zählt mit
                if self.contract_locked(contract.contract_id):
                    raise ContractLocked("Von diesem Vertrag ist schon eine Periode gespeichert")
                new = replace(new, billing_rule=rule, fixed_day=fixed)
                if billing.validate_contract(new):
                    raise billing.BillingError("; ".join(billing.validate_contract(new)))
                chain = [new if c.contract_id == contract.contract_id else c for c in self.contracts(meter_id)]
                specs = billing.periods_for_chain(chain, self.today(), self.actual_ends(meter_id))  # wirft BillingError
                if any(s.contract_id == contract.contract_id and s.end_date < self.today() for s in specs):
                    # die neue Regel ergäbe eine schon beendete Periode: deren Daten wären nie richtig eingefroren worden
                    raise ContractLocked("Mit dieser Regel wäre eine Periode schon beendet")
                # Prognose-Schnappschüsse galten für das alte Periodenende (abgeleitete Daten, nicht vergleichbar)
                prefix = f"{contract.contract_id}-"
                self.data.snapshots = [s for s in self.data.snapshots if not s.period_id.startswith(prefix)]
        self.data.contracts = [new if c.contract_id == contract.contract_id else c for c in self.data.contracts]
        return new

    def contract_locked(self, contract_id: str) -> bool:
        """Regel des Vertrags nicht mehr änderbar: eine seiner Perioden ist gespeichert (beendet)."""
        return any(p.contract_id == contract_id for p in self.data.periods)

    def resets(self, meter_id: str) -> list[tuple[datetime, float]]:
        return [(r.at, r.prev_raw) for r in self.data.sensor_resets if r.meter_id == meter_id]

    def add_reset(self, meter_id: str, at: datetime, prev_raw: float) -> bool:
        """Neustart eines Impulszählers merken (doppelte innerhalb von 2 Stunden ignoriert)."""
        for r in self.data.sensor_resets:
            if r.meter_id == meter_id and abs((r.at - at).total_seconds()) < 7200:
                return False
        self.data.sensor_resets.append(SensorReset(meter_id, dt_util.as_utc(at), float(prev_raw)))
        self.store.schedule_save(self.data)
        return True

    def reconcile_meter(self, meter_id: str) -> Reconciliation | None:
        """Zähler mit Sensor mit den Ablesungen abgleichen (0.9): Tageswerte angleichen, Hinweis unter Reparaturen."""
        meter = self.meters.get(meter_id)
        if meter is None or not meter.entity:
            return None
        rec = reconcile(meter, self.data.readings, self.daily(meter_id), self.tz)
        changed = apply_reconciliation(self.daily(meter_id), rec, self.tz)
        if changed and self.put_daily(changed):
            self.store.schedule_save(self.data)
        issue_id = f"{ISSUE_RECONCILE}_{meter_id}"
        last = rec.last
        if rec.notice and last is not None:
            de = str(self.hass.config.language or "de").startswith("de")

            def num(v: float, fmt: str) -> str:
                txt = format(v, fmt)
                return txt.replace(".", ",") if de else txt

            datefmt = "%d.%m.%Y" if de else "%Y-%m-%d"
            ir.async_create_issue(
                self.hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING, translation_key=ISSUE_RECONCILE,
                translation_placeholders={
                    "meter": meter.name or meter_id, "pct": num(last.deviation_pct, "+.1f"),
                    "von": last.start.astimezone(self.tz).strftime(datefmt), "bis": last.end.astimezone(self.tz).strftime(datefmt),
                    "fehlt": num(last.missing or 0.0, ".2f"), "unit": meter.unit,
                    "angeglichen": ("ja" if last.applied else "nein") if de else ("yes" if last.applied else "no"),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return rec

    def invalidate_reading(self, meter_id: str, reading_id: str, reason: str | None) -> Reading:
        """Ablesung als ungültig markieren. Der Wert bleibt erhalten (Regel 3)."""
        idx = self._reading_index(meter_id, reading_id)
        old = self.data.readings[idx]
        note = f"{old.note + ' · ' if old.note else ''}ungültig: {reason}" if reason else old.note
        self.data.readings[idx] = replace(old, quality=Quality.INVALID, note=note)
        return self.data.readings[idx]

    def _reading_index(self, meter_id: str, reading_id: str) -> int:
        for i, r in enumerate(self.data.readings):
            if r.reading_id == reading_id and r.meter_id == meter_id:
                return i
        raise KeyError(reading_id)

    def add_follow_up(self, new: Contract) -> tuple[Contract, Contract]:
        """Anbieterwechsel: alter Vertrag endet am Vortag, neuer Vertrag wird angehängt.
        Beendete Perioden bleiben unangetastet (Regel 3)."""
        self.sync_periods()
        billing.check_not_in_ended_period(new.start_date, self.stored_periods(new.meter_id))
        old, created = billing.add_follow_up(self.data.contracts, new)
        self.data.contracts = [old if c.contract_id == old.contract_id else c for c in self.data.contracts]
        self.data.contracts.append(created)
        return old, created

    def set_period_end(self, meter_id: str, actual_end: date) -> BillingPeriod:
        """Tatsächlicher Ablesetermin: Ende der laufenden oder der zuletzt beendeten Periode verschieben (±10 Tage).

        Frühere Perioden bleiben unverändert; die Regel bleibt, nur diese eine Periode endet anders.
        """
        today = self.today()
        specs = billing.periods_for_chain(self.contracts(meter_id), today, self.actual_ends(meter_id))
        candidates = [s for s in specs if not s.is_final][-2:]  # zuletzt beendete und laufende
        spec = next((s for s in candidates if abs((actual_end - s.regular_end).days) <= billing.MAX_READING_SHIFT_DAYS), None)
        if spec is None:
            raise billing.BillingError(
                f"Kein reguläres Periodenende in der Nähe von {actual_end} (nur die laufende oder die zuletzt beendete Periode)"
            )
        billing.shifted_end(spec, actual_end)
        if any(p.period_id == spec.period_id and p.status == PeriodStatus.CLOSED for p in self.data.periods):
            raise billing.BillingError("Die Periode ist abgeschlossen (Endablesung oder Rechnung erfasst) und wird nicht mehr verändert")
        if any(p.start_date > spec.start_date for p in self.stored_periods(meter_id)):
            raise billing.BillingError("Die folgende Periode ist schon beendet und wird nicht mehr verändert")
        status = PeriodStatus.CLOSING if actual_end < today else PeriodStatus.OPEN
        bp = replace(billing.to_billing_period(spec, status), end_date=actual_end, regular_end=spec.regular_end)
        self.data.periods = [p for p in self.data.periods if p.period_id != spec.period_id] + [bp]
        return bp

    def append_manual_period(self, meter_id: str, end: date) -> Contract:
        """Regel 'von Hand': nächste Periode an den laufenden (sonst letzten) Vertrag anhängen."""
        chain = self.contracts(meter_id)
        contract = billing.contract_on(chain, self.today()) or (chain[-1] if chain else None)
        if contract is None:
            raise billing.BillingError("Für diesen Zähler gibt es keinen Vertrag")
        new = billing.append_manual_period(contract, end, self.today())
        self.data.contracts = [new if c.contract_id == new.contract_id else c for c in self.data.contracts]
        return new

    def put_daily(self, values: list[DailyConsumption]) -> int:
        """Tageswerte einsetzen bzw. ersetzen (abgeleitete Daten). Liefert die Anzahl geänderter Tage.

        Ein verwendbarer Wert wird nie durch "fehlend" oder "ungültig" aus der Statistik ersetzt (z. B. nach
        einem Recorder-Purge); Tageswerte hängen damit nicht am Recorder (Entscheidung E). Werte aus Ablesungen
        dürfen sich ändern, weil sie nur von den eigenen Ablesungen abhängen.
        """
        index = {(d.meter_id, d.date): i for i, d in enumerate(self.data.daily)}
        changed = 0
        for v in values:
            key = (v.meter_id, v.date)
            if key in index:
                cur = self.data.daily[index[key]]
                if usable(cur.quality) and not usable(v.quality) and v.source != "readings":
                    continue
                if usable(cur.quality) and "ersatzquelle" in v.quality_flags and "ersatzquelle" not in cur.quality_flags:
                    continue  # eigener Wert (Zähler oder Ablesung) bleibt, auch wenn die Statistik dort inzwischen fehlt
                if v.heating_hours is None and cur.heating_hours is not None:
                    # Brennerdaten älter als der Recorder-Verlauf nicht verlieren
                    v = replace(v, heating_hours=cur.heating_hours, burner_starts=cur.burner_starts, cycling=cur.cycling,
                                mean_power_kw=cur.mean_power_kw)
                if cur != v:
                    self.data.daily[index[key]] = v
                    changed += 1
            else:
                index[key] = len(self.data.daily)
                self.data.daily.append(v)
                changed += 1
        return changed

    # ------------------------------------------------------------ Preise, Abschläge, Zahlungen, Rechnungen (0.6)

    def _contract_for(self, meter_id: str, day: date) -> Contract:
        contract = billing.contract_on(self.contracts(meter_id), day)
        if contract is None:
            raise billing.BillingError(f"Am {day} läuft für diesen Zähler kein Vertrag")
        return contract

    def _not_in_ended_period(self, meter_id: str, day: date, what: str) -> None:
        ended = self.stored_periods(meter_id)
        if ended and day <= max(p.end_date for p in ended):
            raise billing.BillingError(
                f"{what} ab {day} fällt in eine beendete Abrechnungsperiode; beendete Perioden werden nicht verändert"
            )

    def set_price(self, meter_id: str, valid_from: date, **values: Any) -> PriceSegment:
        """Preisabschnitt ab ``valid_from``. Der vorherige Abschnitt endet am Vortag; gleicher Beginn ersetzt (Korrektur)."""
        self._not_in_ended_period(meter_id, valid_from, "Ein Preis")
        contract = self._contract_for(meter_id, valid_from)
        seg = PriceSegment(contract_id=contract.contract_id, valid_from=valid_from, **values)
        out: list[PriceSegment] = []
        for s in self.data.prices:
            if s.contract_id != contract.contract_id:
                out.append(s)
                continue
            if s.valid_from == valid_from:
                continue  # ersetzt
            if s.valid_from < valid_from and (s.valid_to is None or s.valid_to >= valid_from):
                s = replace(s, valid_to=valid_from - timedelta(days=1))
            out.append(s)
        out.append(seg)
        self.data.prices = out
        return seg

    def set_advance(self, meter_id: str, valid_from: date, amount: float, pay_day: int | None = None,
                    rhythm: int | None = None, max_per_period: int | None = None) -> AdvancePlan:
        """Abschlag ab ``valid_from`` (neue Stufe im Plan). Zahltag, Rhythmus und Höchstzahl optional mitändern."""
        self._not_in_ended_period(meter_id, valid_from, "Ein Abschlag")
        contract = self._contract_for(meter_id, valid_from)
        plan = next((p for p in self.data.advance_plans if p.contract_id == contract.contract_id), None)
        if plan is None:
            plan = AdvancePlan(contract.contract_id)
        # Zahltag und Rhythmus gelten ab dieser Stufe, frühere Termine bleiben unverändert
        steps = [s for s in plan.steps if s.from_date != valid_from] + [AdvanceStep(valid_from, float(amount), pay_day, rhythm)]
        new = replace(
            plan, steps=sorted(steps, key=lambda s: s.from_date),
            max_per_period=max_per_period if max_per_period is not None else plan.max_per_period,
        )
        self.data.advance_plans = [p for p in self.data.advance_plans if p.contract_id != contract.contract_id] + [new]
        return new

    def add_payment(self, meter_id: str, day: date, amount: float, kind: PaymentType, status: PaymentStatus) -> Payment:
        contract = self._contract_for(meter_id, day)
        p = Payment(new_id(), contract.contract_id, day, float(amount), kind, status)
        self.data.payments.append(p)
        return p

    def day_intervals(self, key: str, kind: str = "energy") -> dict[date, list[float | None]]:
        """Viertelstunden je Tag (1.2): Verbrauch eines Zählers (``key`` = Zähler) oder Preise einer Entität."""
        return {d.date: d.values for d in self.data.day_intervals if d.key == key and d.kind == kind}

    def put_day_interval(self, item: DayIntervals) -> bool:
        for i, d in enumerate(self.data.day_intervals):
            if d.key == item.key and d.kind == item.kind and d.date == item.date:
                if d == item:
                    return False
                self.data.day_intervals[i] = item
                return True
        self.data.day_intervals.append(item)
        return True

    def trim_history(self, before: date) -> bool:
        """Stunden- und Viertelstundenwerte vor ``before`` verwerfen (Speichergröße); Tageswerte bleiben."""
        changed = False
        n = len(self.data.day_intervals)
        self.data.day_intervals = [d for d in self.data.day_intervals if d.date >= before]
        changed |= len(self.data.day_intervals) != n
        for i, d in enumerate(self.data.daily):
            if d.hourly is not None and d.date < before:
                self.data.daily[i] = replace(d, hourly=None)
                changed = True
        return changed

    def price_kinds(self, meter_id: str) -> set[str]:
        """Preisarten der Verträge eines Zählers (windows, dynamic): bestimmen, welche Sensoren es gibt."""
        ids = {c.contract_id for c in self.contracts(meter_id)}
        out: set[str] = set()
        for p in self.data.prices:
            if p.contract_id in ids:
                if p.windows:
                    out.add("windows")
                if p.dynamic is not None:
                    out.add("dynamic")
        return out

    def reload_if_new_kinds(self, meter_id: str, before: set[str]) -> None:
        """Kommen Zeitfenster oder ein dynamischer Preis neu hinzu, die Integration neu laden (neue Sensoren)."""
        if self.price_kinds(meter_id) != before:
            self.store.schedule_save(self.data)
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)

    def interval_needs(self) -> tuple[dict[str, Meter], set[tuple[str, str | None]]]:
        """Zähler, für die Viertelstunden gesammelt werden, und die Preis-Entitäten (dynamischer Tarif, Vergleich)."""
        meters: dict[str, Meter] = {}
        ents: set[tuple[str, str | None]] = set()
        for m in self.meters.values():
            mine: set[tuple[str, str | None]] = set()
            if m.comparison is not None:
                mine.add((m.comparison.entity, m.comparison.attribute))
            ids = {c.contract_id for c in self.contracts(m.meter_id)}
            for p in self.data.prices:
                if p.contract_id in ids and p.dynamic is not None:
                    mine.add((p.dynamic.entity, p.dynamic.attribute))
            if mine and m.entity:
                meters[m.meter_id] = m
            ents |= mine
        return meters, ents

    def invoices(self, meter_id: str) -> list[Invoice]:
        """Rechnungen eines Zählers (am Zähler oder über seinen Vertrag), ohne korrigierte, nach Zeitraum sortiert."""
        own = {c.contract_id for c in self.contracts(meter_id)}
        out = [i for i in self.data.invoices if i.meter_id == meter_id or (i.meter_id is None and i.contract_id in own)]
        corrected = {i.corrects_invoice_id for i in out if i.corrects_invoice_id}
        return sorted((i for i in out if i.invoice_id not in corrected), key=lambda i: i.period_from)

    def add_invoice(self, meter_id: str, invoice_date: date, period_from: date, period_to: date, amount: float,
                    corrects: str | None = None, **details: Any) -> tuple[Invoice, list[str]]:
        """Rechnung erfassen (1.1: mit Menge, Ständen und Positionen; auch vor dem Vertragsbeginn, dann nur am Zähler).
        Anfangs- und Endstand werden Ablesungen (Quelle „Rechnung“), ein gleicher Stand zum gleichen Zeitpunkt nicht doppelt.
        Liefert die Rechnung und die IDs der neuen Ablesungen."""
        contract = billing.contract_on(self.contracts(meter_id), period_from) or billing.contract_on(self.contracts(meter_id), period_to)
        if contract is None and any(c.start_date <= period_to for c in self.contracts(meter_id)):
            # Zeitraum beginnt vor dem Vertrag und reicht hinein: am Vertrag, der im Zeitraum beginnt
            contract = min((c for c in self.contracts(meter_id) if period_from <= c.start_date <= period_to),
                           key=lambda c: c.start_date, default=None)
        if corrects and not any(i.invoice_id == corrects for i in self.data.invoices):
            raise KeyError(corrects)
        start_r, end_r = details.get("start_reading"), details.get("end_reading")
        if start_r is not None and end_r is not None and end_r < start_r:
            raise billing.BillingError("Der Endstand liegt unter dem Anfangsstand")
        if end_r is not None and period_to >= self.today():
            raise billing.BillingError("Ein Endstand zum Rechnungsende in der Zukunft ist nicht möglich")
        inv = Invoice(new_id(), contract.contract_id if contract else None, invoice_date, period_from, period_to, float(amount),
                      is_correction=bool(corrects), corrects_invoice_id=corrects, meter_id=meter_id, **details)
        self.data.invoices.append(inv)
        added: list[str] = []
        quality = Quality.ESTIMATED if inv.readings_estimated else Quality.REAL
        for value, day in ((inv.start_reading, period_from), (inv.end_reading, period_to + timedelta(days=1))):
            if value is None:
                continue
            ts = datetime.combine(day, datetime.min.time(), tzinfo=self.tz)
            near = [r for r in self.readings(meter_id) if usable(r.quality) and not r.superseded_by
                    and abs((r.timestamp - ts).total_seconds()) < 86400]
            # gleicher Stand: nicht doppelt; eine echte Ablesung am selben Tag geht einer (geschätzten) Rechnungsangabe vor
            if any(abs(r.value - value) < 1e-6 for r in near) or (quality != Quality.REAL and any(r.quality == Quality.REAL for r in near)):
                continue
            added.append(self.add_reading(meter_id, ts, value, quality, ReadingSource.INVOICE, note=f"Rechnung {inv.invoice_id}").reading_id)
        return inv, added

    def apply_invoice_proposals(self, invoice_id: str, proposals: list[dict]) -> list[Calibration]:
        """Vorschläge eines Rechnungsvergleichs übernehmen (nach Bestätigung unter Reparaturen)."""
        inv = next((i for i in self.data.invoices if i.invoice_id == invoice_id), None)
        if inv is None:
            raise KeyError(invoice_id)
        meter_id = inv.meter_id or next((c.meter_id for c in self.data.contracts if c.contract_id == inv.contract_id), None)
        out: list[Calibration] = []
        kinds = {"brennwert": "brennwert", "zustandszahl": "zustandszahl", "faktor_ersatzquelle": "faktor_ersatzquelle"}
        for p in proposals:
            kind = kinds.get(p.get("art"))
            if kind is None or meter_id is None:
                continue
            # Brennwert gilt für den Rechnungszeitraum; der Faktor der Ersatzquelle ab dem Rechnungsbeginn bis zum nächsten Faktor
            ranged = kind != "faktor_ersatzquelle"
            cal = Calibration(new_id(), meter_id, kind, float(p["wert"]), dt_util.utcnow(), invoice_id,
                              inv.period_from, inv.period_to if ranged else None)
            # gleiche Art aus derselben Rechnung ersetzt (erneut übernommen)
            self.data.calibrations = [c for c in self.data.calibrations if not (c.invoice_id == invoice_id and c.kind == kind)]
            self.data.calibrations.append(cal)
            out.append(cal)
        return out
