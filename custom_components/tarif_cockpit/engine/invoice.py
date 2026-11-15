"""Jahresabrechnung gegen Integration (1.1): Menge, Brennwert und Kosten der Rechnung mit den eigenen Daten vergleichen
und daraus Vorschläge ableiten. Übernommen wird ein Vorschlag nur nach Bestätigung (Reparatur „Übernehmen“) als
``Calibration``; die Funktionen hier ändern nichts.

Vorschläge:
- ``brennwert``/``zustandszahl``: Werte laut Rechnung für genau den Rechnungszeitraum (Gas in m³).
- ``faktor_ersatzquelle``: Rechnung ÷ Ersatzquelle, wenn die Ersatzquelle (z. B. Wechselrichter) den größten Teil
  der Menge trägt und die Abweichung über der Toleranz liegt; begrenzt auf 0,8 … 1,25 (sonst nur ein Hinweis).
- Preis-Positionen (Arbeitspreis, Grundpreis) sind nur Hinweise: Preise ändert der Nutzer selbst.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta, tzinfo

from .billing import calculate_costs, energy_factor, segment_on
from .consumption import day_bounds
from .model import Calibration, Contract, DailyConsumption, Invoice, Medium, Meter, PriceSegment
from .quality import usable

MIN_COVERAGE = 0.9  # Anteil der Rechnungstage mit eigenem Tageswert, ab dem verglichen wird (Lücken hochgerechnet)
MIN_COVERAGE_PROPOSAL = 0.98  # ab hier auch ein Vorschlag für die Ersatzquelle (sonst nur ein Hinweis)
FACTOR_MIN, FACTOR_MAX = 0.8, 1.25
CALORIFIC_TOLERANCE = 0.005  # 0,5 % Unterschied beim Brennwert gilt als gleich
PRICE_TOLERANCE_EUR = 1.0  # Abweichung einer Preis-Position, ab der ein Hinweis kommt (zusätzlich zur Toleranz in %)


@dataclass(slots=True)
class InvoiceCheck:
    invoice_id: str
    period_from: date
    period_to: date
    coverage: float = 0.0
    quantity_invoice: float | None = None  # Zählereinheit
    quantity_own: float | None = None  # Zählereinheit
    by_source: dict[str, float] = field(default_factory=dict)  # zaehler | ersatzquelle | ablesungen
    deviation_pct: float | None = None
    calorific_invoice: float | None = None
    calorific_own: float | None = None
    cost_invoice: float | None = None
    cost_own: float | None = None  # mit der Menge der Rechnung und den eigenen Preisen gerechnet (zeigt Preisfehler)
    positions: dict[str, dict[str, float | None]] = field(default_factory=dict)  # arbeitspreis/grundpreis: rechnung, eigen
    proposals: list[dict] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.proposals or self.hints)

    def as_dict(self) -> dict:
        r = (lambda v, n=3: None if v is None else round(v, n))
        return {
            "rechnung": self.invoice_id, "von": self.period_from.isoformat(), "bis": self.period_to.isoformat(),
            "abdeckung": round(self.coverage, 3), "menge_rechnung": r(self.quantity_invoice), "menge_eigen": r(self.quantity_own),
            "quellen": {k: round(v, 3) for k, v in self.by_source.items()}, "abweichung_pct": r(self.deviation_pct, 1),
            "brennwert_rechnung": self.calorific_invoice, "brennwert_eigen": r(self.calorific_own, 4),
            "kosten_rechnung": r(self.cost_invoice, 2), "kosten_eigen": r(self.cost_own, 2),
            "positionen": {k: {kk: r(vv, 2) for kk, vv in v.items()} for k, v in self.positions.items()},
            "vorschlaege": list(self.proposals), "hinweise": list(self.hints), "flags": list(self.flags),
        }


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def invoice_quantity(inv: Invoice, meter: Meter, own_factor: float | None) -> float | None:
    """Menge der Rechnung in der Zählereinheit: Menge, sonst Endstand − Anfangsstand, sonst kWh ÷ Brennwert × Z."""
    if inv.quantity is not None:
        return inv.quantity
    if inv.start_reading is not None and inv.end_reading is not None:
        return inv.end_reading - inv.start_reading
    if inv.quantity_kwh is not None:
        if meter.medium == Medium.GAS and meter.unit in ("m³", "m3"):
            f = (inv.calorific * inv.z_factor) if inv.calorific and inv.z_factor else own_factor
            return inv.quantity_kwh / f if f else None
        return inv.quantity_kwh / (1000.0 if meter.unit == "MWh" else 1.0)
    return None


def compare_invoice(
    inv: Invoice,
    meter: Meter,
    contract: Contract | None,
    prices: list[PriceSegment],
    daily: Mapping[date, DailyConsumption],
    tz: tzinfo,
    tolerance_pct: float = 5.0,
    active_factor: float | None = None,
    slot_kw: dict | None = None,
) -> InvoiceCheck:
    """Rechnung mit den eigenen Tageswerten vergleichen (Menge je Quelle, Brennwert, Kosten je Position).

    ``daily`` sind die Tageswerte **ohne** übernommene Faktoren: Der Faktor der Ersatzquelle wird absolut vorgeschlagen
    (``active_factor`` = der im Rechnungszeitraum schon geltende, als „bisher“). Fehlende Tage werden für den Vergleich
    hochgerechnet (fehlend ist nie 0, Regel 5); einen Vorschlag gibt es erst ab 98 % Abdeckung."""
    chk = InvoiceCheck(inv.invoice_id, inv.period_from, inv.period_to)
    days = _days(inv.period_from, inv.period_to)
    segs = [p for p in prices if contract is not None and p.contract_id == contract.contract_id]
    own = {"zaehler": 0.0, "ersatzquelle": 0.0, "ablesungen": 0.0}
    have = 0
    by_day: dict[date, float] = {}
    for d in days:
        v = daily.get(d)
        if v is None or v.consumption is None or not usable(v.quality):
            continue
        have += 1
        by_day[d] = v.consumption
        src = "ersatzquelle" if "ersatzquelle" in v.quality_flags else ("ablesungen" if v.source == "readings" else "zaehler")
        own[src] += v.consumption
    chk.coverage = have / len(days) if days else 0.0
    chk.by_source = {k: v for k, v in own.items() if v}
    seg_mid = segment_on(segs, inv.period_to) if segs else None
    own_factor = energy_factor(meter, seg_mid)
    chk.quantity_invoice = invoice_quantity(inv, meter, own_factor)
    if meter.medium == Medium.GAS and meter.unit in ("m³", "m3") and contract is not None:
        # nur mit Vertrag: vor dem Vertrag gibt es keinen Preisabschnitt, den ein Brennwert ändern könnte
        chk.calorific_invoice = inv.calorific
        chk.calorific_own = (seg_mid.calorific if seg_mid and seg_mid.calorific else None) or meter.conversion.calorific
        if inv.calorific and chk.calorific_own and abs(inv.calorific / chk.calorific_own - 1) > CALORIFIC_TOLERANCE:
            chk.proposals.append({"art": "brennwert", "wert": inv.calorific, "von": inv.period_from.isoformat(),
                                  "bis": inv.period_to.isoformat(), "bisher": chk.calorific_own})
        z_own = (seg_mid.z_factor if seg_mid and seg_mid.z_factor else None) or meter.conversion.z_factor
        if inv.z_factor and z_own and abs(inv.z_factor / z_own - 1) > CALORIFIC_TOLERANCE:
            chk.proposals.append({"art": "zustandszahl", "wert": inv.z_factor, "von": inv.period_from.isoformat(),
                                  "bis": inv.period_to.isoformat(), "bisher": z_own})
    if chk.coverage < MIN_COVERAGE:
        chk.flags.append("zu_wenig_tageswerte")
    else:
        raw = sum(own.values())
        chk.quantity_own = raw * len(days) / have  # fehlende Tage hochgerechnet
        if have < len(days):
            chk.flags.append("hochgerechnet")
        if chk.quantity_invoice and chk.quantity_own:
            ersatz = own["ersatzquelle"]
            f_now = active_factor or 1.0
            # Abweichung so, wie die Integration heute rechnet (mit dem schon geltenden Faktor der Ersatzquelle)
            shown = chk.quantity_own + ersatz * (f_now - 1) * len(days) / have
            chk.deviation_pct = (shown / chk.quantity_invoice - 1) * 100
            if abs(chk.deviation_pct) > tolerance_pct:
                if ersatz >= 0.5 * raw and chk.coverage >= MIN_COVERAGE_PROPOSAL:
                    factor = (chk.quantity_invoice - own["zaehler"] - own["ablesungen"]) / ersatz
                    if FACTOR_MIN <= factor <= FACTOR_MAX:
                        chk.proposals.append({"art": "faktor_ersatzquelle", "wert": round(factor, 4), "bisher": round(f_now, 4)})
                    else:
                        chk.hints.append("menge_weicht_stark_ab")
                elif ersatz >= 0.5 * raw:
                    chk.hints.append("menge_weicht_ab_luecken")
                else:
                    chk.hints.append("menge_weicht_ab")  # Zähler oder Ablesungen: Ablesungen prüfen (Abgleich 0.9)
    # Kosten: mit der Menge der Rechnung, über die eigenen Tageswerte verteilt (Preisfehler statt Mengenfehler)
    if contract is not None and segs and any(p.dynamic is not None for p in segs):
        chk.flags.append("dynamisch_nicht_geprueft")  # Börsenpreise des Rechnungszeitraums liegen nicht vollständig vor
    elif contract is not None and segs and chk.quantity_invoice is not None:
        weights = by_day if by_day and sum(by_day.values()) > 0 else {d: 1.0 for d in days}
        s = sum(weights.values())
        qty = {d: chk.quantity_invoice * w / s for d, w in weights.items()}
        cal_meter = meter
        if inv.calorific or inv.z_factor:  # Brennwert der Rechnung, damit nur Preise verglichen werden
            segs = [replace(p, calorific=inv.calorific or p.calorific, z_factor=inv.z_factor or p.z_factor) for p in segs]
        f_inv = (inv.calorific * inv.z_factor) if inv.calorific and inv.z_factor else (own_factor or 1.0)
        kw = {k: v for k, v in (slot_kw or {}).items() if k in ("hourly", "profile")}
        cb = calculate_costs(contract, segs, cal_meter, qty, day_bounds(inv.period_from, tz)[0], day_bounds(inv.period_to, tz)[1], tz,
                             tier_scale=len(days) / 365, tier_total=chk.quantity_invoice * f_inv, **kw)
        if "fenster_geschaetzt" in cb.flags:
            chk.flags.append("fenster_geschaetzt")
        if cb.complete:
            vat = 1 + contract.vat_rate / 100 if contract.vat_mode.value == "net" else 1.0
            chk.cost_own = cb.gross
            chk.cost_invoice = inv.amount
            for key, mine, theirs in (("arbeitspreis", cb.energy * vat, inv.work_cost), ("grundpreis", (cb.base + cb.fixed + cb.demand) * vat, inv.base_cost)):
                chk.positions[key] = {"rechnung": theirs, "eigen": mine}
                if theirs is not None and abs(mine - theirs) > max(PRICE_TOLERANCE_EUR, abs(theirs) * tolerance_pct / 100):
                    chk.hints.append(f"{key}_pruefen")
            if inv.work_cost is None and inv.base_cost is None and inv.amount and \
                    abs(cb.gross - inv.amount) > max(PRICE_TOLERANCE_EUR, abs(inv.amount) * tolerance_pct / 100):
                chk.hints.append("betrag_pruefen")
        else:
            chk.flags.append("kosten_unvollstaendig")
    elif contract is None:
        chk.flags.append("ohne_vertrag")
    return chk


# ---------------------------------------------------------------- Kalibrierungen anwenden


def _active(c: Calibration, day: date) -> bool:
    return (c.valid_from is None or c.valid_from <= day) and (c.valid_to is None or day <= c.valid_to)


def calibrated_daily(daily: Mapping[date, DailyConsumption], calibrations: list[Calibration], meter_id: str) -> Mapping[date, DailyConsumption]:
    """Tageswerte der Ersatzquelle mit dem übernommenen Faktor (übrige Tage unverändert). Markiert mit ``kalibriert``."""
    cals = [c for c in calibrations if c.meter_id == meter_id and c.kind == "faktor_ersatzquelle"]
    if not cals:
        return daily
    out = dict(daily)
    for d, v in daily.items():
        if v.consumption is None or "ersatzquelle" not in v.quality_flags:
            continue
        f = factor_on(cals, d)
        if f is not None:
            out[d] = replace(v, consumption=round(v.consumption * f, 6), quality_flags=[*v.quality_flags, "kalibriert"])
    return out


def factor_on(cals: list[Calibration], day: date) -> float | None:
    """Faktor der Ersatzquelle an ``day``: die Kalibrierung mit dem jüngsten Beginn bis dahin (gilt bis zur nächsten),
    bei gleichem Beginn die zuletzt übernommene."""
    active = [c for c in cals if c.kind == "faktor_ersatzquelle" and _active(c, day)]
    if not active:
        return None
    return max(active, key=lambda c: (c.valid_from or date.min, c.applied_at)).value


def calibrated_prices(prices: list[PriceSegment], calibrations: list[Calibration], meter_id: str,
                      contract_ids: set[str]) -> list[PriceSegment]:
    """Brennwert/Zustandszahl laut Rechnung für ihren Zeitraum: Jeder Preisabschnitt wird an den Grenzen der Kalibrierungen
    in Stücke geteilt; ein Stück, das eine Kalibrierung abdeckt, bekommt deren Wert (je Art die zuletzt übernommene) als
    eigener Abschnitt, der den ursprünglichen dort überlagert. Sonst bleibt alles gleich."""
    cals = [c for c in calibrations if c.meter_id == meter_id and c.kind in ("brennwert", "zustandszahl")]
    if not cals:
        return prices
    end_max = date(9999, 12, 30)
    base = sorted((p for p in prices if p.contract_id in contract_ids), key=lambda p: p.valid_from)
    out = list(prices)
    for i, p in enumerate(base):
        nxt = next((q.valid_from for q in base[i + 1:] if q.valid_from > p.valid_from), None)
        p_end = min(x for x in (p.valid_to, nxt - timedelta(days=1) if nxt else None, end_max) if x is not None)
        cuts = {p.valid_from, p_end + timedelta(days=1)}
        for c in cals:
            for edge in (c.valid_from, (c.valid_to + timedelta(days=1)) if c.valid_to else None):
                if edge is not None and p.valid_from < edge <= p_end:
                    cuts.add(edge)
        bounds = sorted(cuts)
        for a, b1 in zip(bounds, bounds[1:]):
            b = b1 - timedelta(days=1)
            cover = [c for c in cals if (c.valid_from is None or c.valid_from <= a) and (c.valid_to is None or b <= c.valid_to)]
            if not cover:
                continue
            values: dict[str, float] = {}
            for kind, key in (("brennwert", "calorific"), ("zustandszahl", "z_factor")):
                mine = [c for c in cover if c.kind == kind]
                if mine:
                    values[key] = max(mine, key=lambda c: c.applied_at).value
            out.append(replace(p, valid_from=a, valid_to=b, **values))
    return out
