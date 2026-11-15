"""Vergleich mit einem dynamischen Tarif (1.2): „Was hätte der bisherige Verbrauch mit Börsenpreis + Aufschlag gekostet?“

Verglichen wird nur über Tage, für die Preise je Viertelstunde vorliegen (sonst wäre der Vergleich erfunden, Regel 10):
- dynamisch: Menge je Zeitscheibe × (Preis der Entität + Aufschlag) + Grundpreis des Angebots je Tag,
- tatsächlich: dieselben Tage mit den eigenen Preisen (Arbeitspreis, Fenster) + eigener Grund- und Messpreis je Tag.
``diff`` = tatsächlich − dynamisch (positiv = dynamisch wäre günstiger gewesen). Hochgerechnet auf die Periode über
den Unterschied je kWh × Prognose-Menge (gekennzeichnet).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo

from .billing import calculate_costs, segment_on
from .model import BillingRule, Contract, DynamicPrice, Meter, PriceSegment


@dataclass(slots=True)
class Comparison:
    days: int = 0  # Tage mit Preisen
    days_total: int = 0  # Tage mit Verbrauch
    quantity: float = 0.0  # Abrechnungseinheit
    cost_actual: float | None = None
    cost_dynamic: float | None = None
    diff: float | None = None  # positiv = dynamisch günstiger
    mean_price_dynamic: float | None = None  # €/kWh inklusive Aufschlag (ohne Grundpreis)
    projected_diff: float | None = None
    interval_days: int = 0  # davon mit echten Viertelstunden (sonst Stunden)
    flags: list[str] = field(default_factory=list)
    by_day: list[tuple[date, float, float]] = field(default_factory=list)  # (Tag, tatsächlich, dynamisch) für die Kurve

    def as_dict(self) -> dict:
        r = (lambda v, n=2: None if v is None else round(v, n))
        return {"tage": self.days, "tage_gesamt": self.days_total, "menge": r(self.quantity, 1), "kosten_tatsaechlich": r(self.cost_actual),
                "kosten_dynamisch": r(self.cost_dynamic), "differenz": r(self.diff), "mittelpreis_dynamisch": r(self.mean_price_dynamic, 4),
                "hochrechnung_periode": r(self.projected_diff), "tage_viertelstunden": self.interval_days, "flags": list(self.flags)}


MIN_PRICE_COVERAGE = 0.75  # Anteil der Viertelstunden mit Preis, ab dem ein Tag verglichen wird


def compare_dynamic(
    meter: Meter,
    comparison: DynamicPrice,
    base_price: float | None,
    contract: Contract,
    segments: list[PriceSegment],
    used_billing_by_day: Mapping[date, float],
    tz: tzinfo,
    hourly: Mapping[date, Sequence[float | None]] | None,
    intervals: Mapping[date, Sequence[float | None]] | None,
    prices: Mapping[date, Sequence[float | None]] | None,
    profile: Sequence[float] | None,
    forecast_total: float | None = None,
    own_prices: Mapping[date, Sequence[float | None]] | None = None,
    tier_kw: dict | None = None,
    dynamic_mean: float | None = None,
) -> Comparison:
    """``prices``: Preise des Vergleichs; ``own_prices``: Preise des eigenen dynamischen Tarifs (falls es einer ist).
    Je Tag die ganzen Kosten (Arbeit, Grund-, Messpreis, Pauschalen) auf beiden Seiten, brutto. Mess- und § 14a-Anteile
    des eigenen Abschnitts gelten auch für den Vergleich (Messstelle und Netz bleiben gleich)."""
    out = Comparison(days_total=sum(1 for q in used_billing_by_day.values() if q))
    priced = {d for d, vals in (prices or {}).items() if vals and sum(1 for v in vals if v is not None) >= MIN_PRICE_COVERAGE * len(vals)}
    days = {d: q for d, q in used_billing_by_day.items() if d in priced and q is not None}
    out.days = len(days)
    if not days:
        out.flags.append("keine_preise")
        return out
    out.quantity = sum(days.values())
    out.interval_days = sum(1 for d in days if (intervals or {}).get(d))
    first = min(days)
    own_segs = [s for s in segments if s.contract_id == contract.contract_id]
    c_dyn = Contract("vergleich", meter.meter_id, "Vergleich", first, BillingRule.MANUAL, vat_rate=contract.vat_rate)
    base_kw = {"quantities_are_billing_unit": True, "hourly": hourly, "intervals": intervals, "profile": profile}
    tier_kw = dict(tier_kw or {})
    cum = tier_kw.pop("tier_before", 0.0)
    total_act = total_dyn = energy_dyn = 0.0
    for d in sorted(days):
        a = datetime.combine(d, datetime.min.time(), tzinfo=tz)
        b = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=tz)
        own = segment_on(own_segs, d)
        seg_dyn = PriceSegment("vergleich", d, 0.0, base_price or 0.0, dynamic=comparison,
                               metering_price=own.metering_price if own else None, rebate_yearly=own.rebate_yearly if own else None)
        dyn = calculate_costs(c_dyn, [seg_dyn], meter, {d: days[d]}, a, b, tz, prices=prices, **base_kw)
        act = calculate_costs(contract, segments, meter, {d: days[d]}, a, b, tz, prices=own_prices, dynamic_mean=dynamic_mean,
                              tier_before=cum, **tier_kw, **base_kw)
        cum += days[d]
        if not act.complete:
            out.flags.append("eigene_kosten_unvollstaendig")
            return out
        out.by_day.append((d, act.gross, dyn.gross))
        total_act += act.gross
        total_dyn += dyn.gross
        energy_dyn += dyn.energy
        out.flags.extend(f for f in dyn.flags if f in ("preis_geschaetzt", "fenster_geschaetzt"))
    out.cost_actual = total_act
    out.cost_dynamic = total_dyn
    out.diff = out.cost_actual - out.cost_dynamic
    out.mean_price_dynamic = energy_dyn / out.quantity if out.quantity else None
    if out.interval_days < out.days:
        out.flags.append("teils_stuendlich")
    if forecast_total and out.quantity:
        out.projected_diff = out.diff / out.quantity * forecast_total
        out.flags.append("hochgerechnet")
    out.flags = sorted(set(out.flags))
    return out
