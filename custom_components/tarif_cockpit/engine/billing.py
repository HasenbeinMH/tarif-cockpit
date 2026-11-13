"""Bereich Abrechnung: Vertragskette und Abrechnungsperioden (Arbeitspaket 2.3, Entscheidung F).

Die Abrechnungsperiode ist die zentrale Einheit. Ein Vertrag hat mehrere Perioden; eine Preisänderung ist
keine neue Periode. Enthalten: Perioden nach Regel, Rumpfjahr, Schlussperiode beim Vertragsende, Verschiebung
durch den tatsächlichen Ablesetermin, Prüfung der Vertragskette (0.5); Kosten und Zahlungen (0.6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta, tzinfo

from .model import (
    AdvancePlan, BillingPeriod, BillingRule, Contract, Medium, Meter, Payment, PaymentStatus, PaymentType, PeriodStatus,
    PriceSegment, VatMode,
)
from .units import gas_factor

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


# ---------------------------------------------------------------- Kosten (0.6)

# Grundpreis je Monat → je Tag: × 12 / 365,25 (wie bisher in den Template-Sensoren; Rundungsregeln der Versorger nach 1.0)
DAYS_PER_YEAR = 365.25


@dataclass(slots=True)
class CostBreakdown:
    """Kosten eines Zeitraums. ``total`` ist im Preis-Modus des Vertrags (brutto oder netto), ``gross`` immer brutto."""

    energy: float = 0.0
    wastewater: float = 0.0
    base: float = 0.0
    fixed: float = 0.0
    demand: float = 0.0
    quantity: float = 0.0  # abgerechnete Menge (kWh bei Energie, m³ bei Wasser)
    total: float = 0.0
    gross: float = 0.0
    flags: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not any(f in self.flags for f in ("kein_preis", "brennwert_fehlt"))


def segment_on(segments: list[PriceSegment], day: date) -> PriceSegment | None:
    """Preisabschnitt, der an ``day`` gilt (der jüngste mit valid_from ≤ day und ohne abgelaufenes valid_to)."""
    best = None
    for s in segments:
        if s.valid_from <= day and (s.valid_to is None or day <= s.valid_to):
            if best is None or s.valid_from > best.valid_from:
                best = s
    return best


def energy_factor(meter: Meter, seg: PriceSegment | None) -> float | None:
    """Umrechnung Zählereinheit → abgerechnete Einheit. Gas in m³: Brennwert × Zustandszahl (Abschnitt, sonst Zähler)."""
    if meter.medium == Medium.GAS and meter.unit in ("m³", "m3"):
        cal = (seg.calorific if seg and seg.calorific else None) or meter.conversion.calorific
        z = (seg.z_factor if seg and seg.z_factor else None) or meter.conversion.z_factor
        return gas_factor(cal, z)
    if meter.unit == "MWh":
        return 1000.0
    return 1.0


def calculate_costs(
    contract: Contract,
    segments: list[PriceSegment],
    meter: Meter,
    quantities: Mapping[date, float],
    base_from: datetime,
    base_to: datetime,
    tz: tzinfo,
    quantities_are_billing_unit: bool = False,
    wastewater: Mapping[date, float] | None = None,
) -> CostBreakdown:
    """Kosten tagesgenau je Preisabschnitt.

    ``quantities``: Menge je Tag in der Zählereinheit (oder schon in kWh, wenn ``quantities_are_billing_unit``).
    Grund-, Mess-, Leistungspreis und feste Jahresbeträge laufen anteilig über die Zeit von ``base_from`` bis ``base_to``.
    """
    segs = [s for s in segments if s.contract_id == contract.contract_id]
    cb = CostBreakdown()
    for day, q in sorted(quantities.items()):
        seg = segment_on(segs, day)
        if seg is None:
            if q:
                cb.flags.append("kein_preis")
            continue
        factor = 1.0 if quantities_are_billing_unit else energy_factor(meter, seg)
        if factor is None:
            cb.flags.append("brennwert_fehlt")
            continue
        cb.quantity += q * factor
        cb.energy += q * factor * seg.work_price
    for day, q in sorted((wastewater or {}).items()):
        seg = segment_on(segs, day)
        if seg and seg.wastewater_price:
            cb.wastewater += q * seg.wastewater_price
    # zeitanteilige Bestandteile, tageweise mit Bruchteilen an den Rändern
    t = base_from.astimezone(UTC)
    end = base_to.astimezone(UTC)
    while t < end:
        local_day = t.astimezone(tz).date()
        day_end = datetime.combine(local_day + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(UTC)
        stop = min(day_end, end)
        day_start = datetime.combine(local_day, datetime.min.time(), tzinfo=tz).astimezone(UTC)
        # Anteil am lokalen Tag (23/25 Stunden an den Tagen der Zeitumstellung zählen als ein Tag)
        frac = (stop - t).total_seconds() / (day_end - day_start).total_seconds()
        seg = segment_on(segs, local_day)
        if seg is None:
            cb.flags.append("kein_preis")
        else:
            cb.base += frac * ((seg.base_price or 0.0) + (seg.metering_price or 0.0)) * 12 / DAYS_PER_YEAR
            cb.fixed += frac * (seg.fixed_yearly or 0.0) / DAYS_PER_YEAR
            if seg.demand_price and seg.demand_kw:
                cb.demand += frac * seg.demand_price * seg.demand_kw / DAYS_PER_YEAR
        t = stop
    cb.flags = sorted(set(cb.flags))
    cb.total = cb.energy + cb.wastewater + cb.base + cb.fixed + cb.demand
    cb.gross = cb.total * (1 + contract.vat_rate / 100) if contract.vat_mode == VatMode.NET else cb.total
    for name in ("energy", "wastewater", "base", "fixed", "demand", "quantity", "total", "gross"):
        setattr(cb, name, round(getattr(cb, name), 4))
    return cb


# ---------------------------------------------------------------- Zahlungen (0.6, Entscheidung K)


@dataclass(slots=True)
class Installment:
    date: date
    amount: float
    status: str  # faellig (Datum erreicht) | geplant | gezahlt (eigene Zahlung erfasst) | storniert


@dataclass(slots=True)
class PaymentState:
    paid_to_date: float = 0.0
    period_total: float = 0.0  # alle Abschläge und Zahlungen der Periode (bezahlt und geplant)
    installments: list[Installment] = field(default_factory=list)
    other: float = 0.0  # Einmalzahlungen abzüglich Gutschriften in der Periode
    next_date: date | None = None
    remaining: int = 0  # noch offene Abschläge nach heute
    future_other: float = 0.0  # geplante Einmalzahlungen/Gutschriften nach heute
    known: bool = True  # False: weder Abschlagsplan noch Zahlungen bekannt (dann nie "0 € gezahlt" behaupten)

    @property
    def per_period(self) -> int:
        return sum(1 for i in self.installments if i.status != "storniert")


def _add_months(d: date, months: int, day: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    nxt = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    last = (nxt - timedelta(days=1)).day
    return date(y, m, min(day, last))


def advance_on(plan: AdvancePlan, day: date) -> float | None:
    steps = [s for s in plan.steps if s.from_date <= day]
    return max(steps, key=lambda s: s.from_date).amount if steps else None


def plan_dates(plan: AdvancePlan, period_start: date, period_end: date) -> list[tuple[date, float]]:
    """Zahltermine einer Periode. Jede Stufe gilt ab ihrem Datum mit eigenem Zahltag/Rhythmus (sonst dem des Plans);
    der erste Termin einer Stufe ist der erste Zahltag ab ihrem Beginn. Frühere Termine ändern sich nie rückwirkend."""
    steps = sorted(plan.steps, key=lambda s: s.from_date)
    out: list[tuple[date, float]] = []
    for i, step in enumerate(steps):
        until = steps[i + 1].from_date - timedelta(days=1) if i + 1 < len(steps) else period_end
        lo, hi = max(step.from_date, period_start), min(until, period_end)
        if lo > hi:
            continue
        day = step.pay_day or plan.pay_day
        rhythm = max(step.rhythm or plan.rhythm, 1)
        first = _add_months(date(step.from_date.year, step.from_date.month, 1), 0, day)
        if first < step.from_date:
            first = _add_months(date(step.from_date.year, step.from_date.month, 1), 1, day)
        k = 0
        while k < 400:
            d = _add_months(date(first.year, first.month, 1), k * rhythm, day)
            k += 1
            if d > hi:
                break
            if d >= lo:
                out.append((d, step.amount))
    return out


def calculate_payments(plan: AdvancePlan | None, payments: list[Payment], period_start: date, period_end: date, today: date) -> PaymentState:
    """Abschläge laut Plan (Stufen, Rhythmus, Höchstzahl) und erfasste Zahlungen einer Periode.

    Eine erfasste Zahlung vom Typ Abschlag ersetzt den geplanten Abschlag desselben Monats; eine stornierte
    Abschlagszahlung streicht ihn. Gutschriften und Erstattungen mindern den gezahlten Betrag.
    """
    ps = PaymentState()
    pays = [p for p in payments if period_start <= p.date <= period_end]
    adv_by_month: dict[tuple[int, int], list[Payment]] = {}
    for p in pays:
        if p.type == PaymentType.ADVANCE:
            adv_by_month.setdefault((p.date.year, p.date.month), []).append(p)
    ps.known = plan is not None and bool(plan.steps) or bool(pays)
    if plan is not None:
        count = 0
        for d, amount in plan_dates(plan, period_start, period_end):
            if plan.max_per_period and count >= plan.max_per_period:
                break
            count += 1
            own = adv_by_month.pop((d.year, d.month), None)
            if own:
                if all(p.status == PaymentStatus.CANCELLED for p in own):
                    ps.installments.append(Installment(d, amount, "storniert"))
                else:
                    for p in own:
                        if p.status != PaymentStatus.CANCELLED:
                            ps.installments.append(Installment(p.date, p.amount, "gezahlt" if p.status == PaymentStatus.PAID else "geplant"))
            else:
                ps.installments.append(Installment(d, amount, "faellig" if d <= today else "geplant"))
    # Abschlagszahlungen ohne passenden Plan-Termin
    for own in adv_by_month.values():
        for p in own:
            if p.status != PaymentStatus.CANCELLED:
                ps.installments.append(Installment(p.date, p.amount, "gezahlt" if p.status == PaymentStatus.PAID else "geplant"))
    ps.installments.sort(key=lambda x: x.date)
    for inst in ps.installments:
        if inst.status == "storniert":
            continue
        ps.period_total += inst.amount
        if inst.date <= today and inst.status in ("faellig", "gezahlt"):
            ps.paid_to_date += inst.amount
        elif inst.date > today:
            ps.remaining += 1
            if ps.next_date is None:
                ps.next_date = inst.date
    for p in pays:
        if p.type == PaymentType.ADVANCE or p.status == PaymentStatus.CANCELLED:
            continue
        sign = -1 if p.type in (PaymentType.CREDIT, PaymentType.REFUND) else 1
        ps.other += sign * p.amount
        ps.period_total += sign * p.amount
        if p.date <= today and p.status == PaymentStatus.PAID:
            ps.paid_to_date += sign * p.amount
        elif p.date > today:
            ps.future_other += sign * p.amount
    ps.paid_to_date = round(ps.paid_to_date, 2)
    ps.period_total = round(ps.period_total, 2)
    ps.other = round(ps.other, 2)
    return ps
