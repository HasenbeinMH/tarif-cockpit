"""Laufzeitdaten eines Haushalts (Config Entry): Store, Datenbestand, Haushalt, Zähler.

Alle Änderungen am Datenbestand laufen über diese Klasse: Ablesungen werden nur angehängt, Verträge nur
über den Folgevertrag geändert, abgeschlossene Perioden nie überschrieben (Regel 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import signal_updated
from .engine import billing
from .engine.model import (
    BillingPeriod, Contract, DailyConsumption, Dataset, Household, Meter, PeriodStatus, Reading, ReadingSource, new_id,
)
from .engine.quality import Quality, usable
from .store import TarifStore

_LOGGER = logging.getLogger(__name__)


@dataclass
class TarifRuntime:
    hass: HomeAssistant
    entry: ConfigEntry
    store: TarifStore
    data: Dataset
    household: Household
    meters: dict[str, Meter]  # meter_id (= subentry_id) → Zähler
    subentry_ids: frozenset[str] = frozenset()
    unsubs: list[Any] = field(default_factory=list)
    aggregator: Any = None  # aggregation.Aggregator, gesetzt beim Setup

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
    def changed(self, save: bool = True) -> None:
        if save:
            self.store.schedule_save(self.data)
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
    ) -> Reading:
        """Neue Ablesung anhängen. Mit ``replaces`` wird eine frühere Ablesung als ersetzt markiert (nicht gelöscht)."""
        reading = Reading(new_id(), meter_id, dt_util.as_utc(timestamp), float(value), quality, source, note)
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
            self.changed()

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
                if cur != v:
                    self.data.daily[index[key]] = v
                    changed += 1
            else:
                index[key] = len(self.data.daily)
                self.data.daily.append(v)
                changed += 1
        return changed
