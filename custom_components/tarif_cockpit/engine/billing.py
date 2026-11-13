"""Bereich Abrechnung: Vertragskette und Abrechnungsperioden (Arbeitspaket 2.3, Entscheidung F).

Die Abrechnungsperiode ist die zentrale Einheit. Ein Vertrag hat mehrere Perioden; eine Preisänderung ist
keine neue Periode. In 0.5 enthalten: Perioden nach Regel, Rumpfjahr, Schlussperiode beim Vertragsende,
Verschiebung durch den tatsächlichen Ablesetermin, Prüfung der Vertragskette.
Kosten und Zahlungen folgen in 0.6.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from .model import BillingPeriod, BillingRule, Contract, PeriodStatus

# Ein abweichender tatsächlicher Ablesetermin darf das Periodenende um höchstens so viele Tage verschieben
MAX_READING_SHIFT_DAYS = 10
# Sicherheitsgrenze gegen Endlosschleifen bei unsinnigen Daten
_MAX_PERIODS = 200


class BillingError(ValueError):
    """Fachlich unzulässige Eingabe (z. B. Stichtag 31.02., Lücke in der Vertragskette)."""


def parse_fixed_day(text: str | None) -> tuple[int, int]:
    """'TT.MM' → (Tag, Monat). 29.02. ist nicht erlaubt (gäbe es nicht in jedem Jahr)."""
    if not text:
        raise BillingError("Stichtag fehlt (Format TT.MM)")
    try:
        day_s, month_s = text.strip().rstrip(".").split(".")
        day, month = int(day_s), int(month_s)
        date(2025, month, day)  # kein Schaltjahr: schließt 29.02. aus
    except (ValueError, TypeError) as err:
        raise BillingError(f"Stichtag {text!r} ist kein gültiges Datum TT.MM (29.02. nicht erlaubt)") from err
    return day, month


def add_years(d: date, years: int) -> date:
    """Gleicher Kalendertag n Jahre später; 29.02. wird in Nicht-Schaltjahren zum 01.03."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return date(d.year + years, 3, 1)


def _anniversaries(contract: Contract, until: date) -> list[date]:
    """Regelmäßige Periodenanfänge (ohne den Vertragsbeginn selbst), aufsteigend, bis nach ``until``."""
    rule = contract.billing_rule
    start = contract.start_date
    out: list[date] = []
    if rule == BillingRule.CONTRACT_YEAR:
        n = 1
        while len(out) < _MAX_PERIODS:
            d = add_years(start, n)
            out.append(d)
            if d > until:
                break
            n += 1
    elif rule in (BillingRule.CALENDAR_YEAR, BillingRule.FIXED_DAY):
        day, month = (1, 1) if rule == BillingRule.CALENDAR_YEAR else parse_fixed_day(contract.fixed_day)
        year = start.year
        while len(out) < _MAX_PERIODS:
            d = date(year, month, day)
            if d > start:
                out.append(d)
                if d > until:
                    break
            year += 1
    return out


@dataclass(slots=True, frozen=True)
class PeriodSpec:
    """Berechnete Periode (noch ohne Status). period_id ist stabil: Vertrag + Beginn."""

    contract_id: str
    start_date: date
    end_date: date
    regular_end: date  # Ende nach Regel (vor Verschiebung durch den Ablesetermin)
    is_partial: bool
    is_final: bool

    @property
    def period_id(self) -> str:
        return f"{self.contract_id}-{self.start_date.isoformat()}"

    def contains(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date


def generate_periods(contract: Contract, until: date, actual_ends: dict[date, date] | None = None) -> list[PeriodSpec]:
    """Perioden eines Vertrags vom Beginn bis einschließlich der Periode, die ``until`` enthält.

    ``actual_ends`` ordnet einem Periodenende nach Regel das tatsächliche Ende zu (abweichender Ablesetermin,
    höchstens ±MAX_READING_SHIFT_DAYS). Die Regel bleibt: Nur diese Periode endet anders, die nächste beginnt
    am Tag danach, alle späteren Enden folgen wieder der Regel.
    Endet der Vertrag (end_date), endet die letzte Periode dort (Schlussrechnung, is_final).
    """
    actual_ends = actual_ends or {}
    end_limit = contract.end_date
    horizon = min(until, end_limit) if end_limit else until
    if horizon < contract.start_date:
        horizon = contract.start_date

    if contract.billing_rule == BillingRule.MANUAL:
        spans = sorted(contract.manual_periods, key=lambda s: s.start)
        if not spans:
            raise BillingError("Regel 'manual': keine Perioden eingetragen")
        if spans[0].start != contract.start_date:
            raise BillingError("Regel 'manual': erste Periode muss am Vertragsbeginn starten")
        out: list[PeriodSpec] = []
        for i, s in enumerate(spans):
            if s.end < s.start:
                raise BillingError(f"Regel 'manual': Periode {s.start} endet vor ihrem Beginn")
            if i and s.start != spans[i - 1].end + timedelta(days=1):
                raise BillingError(f"Regel 'manual': Lücke oder Überschneidung vor {s.start}")
            end = min(s.end, end_limit) if end_limit else s.end
            final = bool(end_limit and end == end_limit)
            out.append(PeriodSpec(contract.contract_id, s.start, end, s.end, final and end < s.end, final))
            if final or end >= horizon:
                break
        return out

    starts = _anniversaries(contract, horizon)
    regular_starts = [contract.start_date, *starts]
    out = []
    cur_start = contract.start_date
    for i, nxt in enumerate(starts):
        regular_end = nxt - timedelta(days=1)
        end = actual_ends.get(regular_end, regular_end)
        if abs((end - regular_end).days) > MAX_READING_SHIFT_DAYS:
            raise BillingError(
                f"Tatsächliches Periodenende {end} weicht mehr als {MAX_READING_SHIFT_DAYS} Tage von {regular_end} ab"
            )
        # Regelmäßige Länge: Abstand zwischen zwei Regel-Anfängen (erste Periode bei calendar/fixed oft kürzer)
        full_len = (regular_starts[i + 1] - regular_starts[i]).days
        regular_full = i > 0 or contract.billing_rule == BillingRule.CONTRACT_YEAR or _is_on_rule_day(contract)
        if end_limit and end_limit <= end:
            # Vertragsende in dieser Periode: Schlussperiode. Kürzer als nach Regel → Rumpfperiode.
            partial = end_limit < regular_end or not regular_full
            out.append(PeriodSpec(contract.contract_id, cur_start, end_limit, regular_end, partial, True))
            return out
        partial = not regular_full or (end - cur_start).days + 1 < full_len - MAX_READING_SHIFT_DAYS
        out.append(PeriodSpec(contract.contract_id, cur_start, end, regular_end, partial, False))
        cur_start = end + timedelta(days=1)
        if cur_start > horizon or len(out) >= _MAX_PERIODS:
            break
    if end_limit and cur_start <= horizon and cur_start <= end_limit and (not out or out[-1].end_date < end_limit):
        # Vertragsende vor dem nächsten Regel-Ende: Schlussperiode
        out.append(PeriodSpec(contract.contract_id, cur_start, end_limit, end_limit, True, True))
    return out


def _is_on_rule_day(contract: Contract) -> bool:
    """Beginnt der Vertrag genau am Stichtag? Dann ist die erste Periode kein Rumpfjahr."""
    s = contract.start_date
    if contract.billing_rule == BillingRule.CALENDAR_YEAR:
        return (s.day, s.month) == (1, 1)
    if contract.billing_rule == BillingRule.FIXED_DAY:
        return (s.day, s.month) == parse_fixed_day(contract.fixed_day)
    return True


def validate_contract(contract: Contract) -> list[str]:
    """Prüft einen einzelnen Vertrag (Regel-Angaben, Daten)."""
    errors: list[str] = []
    if contract.end_date and contract.end_date < contract.start_date:
        errors.append("Vertragsende liegt vor dem Beginn")
    try:
        if contract.billing_rule == BillingRule.FIXED_DAY:
            parse_fixed_day(contract.fixed_day)
        generate_periods(contract, contract.start_date)
    except BillingError as err:
        errors.append(str(err))
    return errors


def sort_chain(contracts: list[Contract]) -> list[Contract]:
    return sorted(contracts, key=lambda c: c.start_date)


def validate_chain(contracts: list[Contract]) -> list[str]:
    """Die Vertragskette eines Zählers muss lückenlos und überschneidungsfrei sein."""
    errors: list[str] = []
    chain = sort_chain(contracts)
    for prev, nxt in zip(chain, chain[1:]):
        if prev.end_date is None:
            errors.append(f"Vertrag {prev.supplier} ab {prev.start_date} hat kein Ende, danach folgt {nxt.supplier}")
        elif nxt.start_date != prev.end_date + timedelta(days=1):
            kind = "Lücke" if nxt.start_date > prev.end_date + timedelta(days=1) else "Überschneidung"
            errors.append(f"{kind} zwischen {prev.supplier} (bis {prev.end_date}) und {nxt.supplier} (ab {nxt.start_date})")
    return errors


def add_follow_up(contracts: list[Contract], new: Contract) -> tuple[Contract, Contract]:
    """Folgevertrag (Anbieterwechsel) ab ``new.start_date``.

    Beendet den Vertrag, der an diesem Tag läuft, am Vortag. Liefert (alter Vertrag geändert, neuer Vertrag).
    Bestehende Verträge werden nicht verändert, der Aufrufer ersetzt den alten Vertrag (Regel 3).
    """
    chain = sort_chain([c for c in contracts if c.meter_id == new.meter_id])
    if not chain:
        raise BillingError("Kein bestehender Vertrag: zuerst einen Vertrag anlegen")
    last = chain[-1]
    if last.end_date is not None and last.end_date + timedelta(days=1) != new.start_date:
        raise BillingError(f"Der letzte Vertrag endet am {last.end_date}; ein Folgevertrag muss am Tag danach beginnen")
    if new.start_date <= last.start_date:
        raise BillingError("Der Folgevertrag muss nach dem Beginn des laufenden Vertrags starten")
    errors = validate_contract(new)
    if errors:
        raise BillingError("; ".join(errors))
    old = replace(last, end_date=new.start_date - timedelta(days=1))
    return old, new


def check_not_in_ended_period(start: date, ended: list[BillingPeriod]) -> None:
    """Ein Folgevertrag darf keine bereits beendete (gespeicherte) Periode verändern (Regel 3)."""
    last_end = max((p.end_date for p in ended), default=None)
    if last_end is not None and start <= last_end:
        raise BillingError(
            f"Der Wechsel am {start} fällt in eine bereits beendete Abrechnungsperiode (bis {last_end}). "
            "Beendete Perioden werden nicht nachträglich geändert."
        )


def append_manual_period(contract: Contract, end: date, until: date) -> Contract:
    """Regel 'manual': nächste Periode anhängen (Beginn = Tag nach dem Ende der letzten). Liefert den neuen Vertrag."""
    if contract.billing_rule != BillingRule.MANUAL:
        raise BillingError("Perioden von Hand gibt es nur bei der Regel 'von Hand'")
    spans = sorted(contract.manual_periods, key=lambda s: s.start)
    start = spans[-1].end + timedelta(days=1) if spans else contract.start_date
    if end < start:
        raise BillingError(f"Die neue Periode muss nach dem {start - timedelta(days=1)} enden")
    if contract.end_date and end > contract.end_date:
        raise BillingError(f"Der Vertrag endet am {contract.end_date}")
    from .model import PeriodSpan  # noqa: PLC0415

    new = replace(contract, manual_periods=[*spans, PeriodSpan(start, end)])
    generate_periods(new, until)  # prüft die Kette
    return new


def shifted_end(spec: PeriodSpec, actual_end: date) -> date:
    """Tatsächliches Periodenende prüfen (abweichender Ablesetermin, höchstens ±MAX_READING_SHIFT_DAYS)."""
    if abs((actual_end - spec.regular_end).days) > MAX_READING_SHIFT_DAYS:
        raise BillingError(
            f"Das Ende {actual_end} weicht mehr als {MAX_READING_SHIFT_DAYS} Tage vom regulären Ende {spec.regular_end} ab"
        )
    if actual_end < spec.start_date:
        raise BillingError("Das Ende liegt vor dem Beginn der Periode")
    return actual_end


def contract_on(contracts: list[Contract], day: date) -> Contract | None:
    for c in sort_chain(contracts):
        if c.start_date <= day and (c.end_date is None or day <= c.end_date):
            return c
    return None


def period_status(spec: PeriodSpec, today: date, has_end_reading: bool, closed: bool = False) -> PeriodStatus:
    """open: läuft noch; closing: Ende vorbei, Endablesung fehlt; closed: abgeschlossen (Archiv)."""
    if closed:
        return PeriodStatus.CLOSED
    if today <= spec.end_date:
        return PeriodStatus.OPEN
    return PeriodStatus.CLOSED if has_end_reading else PeriodStatus.CLOSING


def periods_for_chain(contracts: list[Contract], until: date, actual_ends: dict[str, dict[date, date]] | None = None) -> list[PeriodSpec]:
    """Alle Perioden aller Verträge eines Zählers bis einschließlich ``until``, aufsteigend."""
    actual_ends = actual_ends or {}
    out: list[PeriodSpec] = []
    for c in sort_chain(contracts):
        if c.start_date > until:
            break
        out.extend(generate_periods(c, until, actual_ends.get(c.contract_id)))
    return out


def current_period(contracts: list[Contract], day: date, actual_ends: dict[str, dict[date, date]] | None = None) -> PeriodSpec | None:
    """Laufende Periode am Tag ``day`` (über alle Verträge des Zählers)."""
    for spec in periods_for_chain(contracts, day, actual_ends):
        if spec.contains(day):
            return spec
    return None


def to_billing_period(spec: PeriodSpec, status: PeriodStatus) -> BillingPeriod:
    return BillingPeriod(
        period_id=spec.period_id,
        contract_id=spec.contract_id,
        start_date=spec.start_date,
        end_date=spec.end_date,
        status=status,
        is_partial=spec.is_partial,
        is_final=spec.is_final,
    )
