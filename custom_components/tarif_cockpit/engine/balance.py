"""Bereich Ergebnis: Saldo, Urteil, empfohlener Abschlag (Arbeitspaket 3.3) und die Auswertung eines Zählers.

``evaluate_meter`` verbindet die vier Bereiche, ohne sie zu vermischen:
Verbrauch (consumption) → Prognose als Menge (forecast) → Kosten und Zahlungen (billing) → Ergebnis (hier).
Eine Preisänderung ändert damit nie die Verbrauchsprognose; ein neuer Abschlagsplan nie den Verbrauch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
import math

from .billing import (
    CostBreakdown, PaymentState, PeriodSpec, calculate_costs, calculate_payments, current_period, energy_factor, segment_on,
)
from .consumption import ConsumptionState, calculate_consumption, day_bounds, valid_readings, continuous_value
from .forecast import Forecast, baseload_forecast, heat_forecast, submeter_forecast
from .model import AdvancePlan, Contract, DailyConsumption, Medium, Meter, Payment, PriceSegment, Reading
from .quality import usable
from .regression import HeatModel, ModelQuality, Sample, fit_heat_model

HEAT_MEDIA = (Medium.GAS, Medium.FERNWAERME)


@dataclass(slots=True)
class Balance:
    actual_cost: float | None = None
    forecast_cost: float | None = None
    advances_period: float | None = None
    paid_to_date: float | None = None
    saldo: float | None = None  # positiv = Rückzahlung, negativ = Nachzahlung
    verdict: str | None = None  # passt | rueckzahlung | nachzahlung
    recommended_advance: float | None = None  # ab dem nächsten Zahltag
    fitting_advance: float | None = None  # Prognose / Anzahl Abschläge der Periode (wie bisher "passender Abschlag")
    next_pay_date: date | None = None
    remaining_installments: int = 0


def calculate_balance(forecast_cost: float | None, payments: PaymentState, tolerance_pct: float) -> Balance:
    if not payments.known:
        # Kein Abschlagsplan und keine Zahlungen: Saldo und Urteil wären erfunden (Regel 5/10)
        return Balance(forecast_cost=forecast_cost)
    b = Balance(forecast_cost=forecast_cost, advances_period=payments.period_total, paid_to_date=payments.paid_to_date,
                next_pay_date=payments.next_date, remaining_installments=payments.remaining)
    if forecast_cost is None:
        return b
    b.saldo = round(payments.period_total - forecast_cost, 2)
    if payments.period_total > 0 and abs(b.saldo) < payments.period_total * tolerance_pct / 100:
        b.verdict = "passt"
    else:
        b.verdict = "rueckzahlung" if b.saldo > 0 else "nachzahlung"
    n = payments.per_period
    if n:
        b.fitting_advance = math.ceil(forecast_cost / n)
    b.recommended_advance = calculate_recommended_advance(forecast_cost, payments)
    return b


def calculate_recommended_advance(forecast_cost: float, payments: PaymentState) -> float | None:
    """Abschlag ab dem nächsten Zahltag, damit die Periode ausgeglichen endet. None, wenn kein Abschlag mehr offen ist."""
    if payments.remaining <= 0:
        return None
    need = forecast_cost - payments.paid_to_date - payments.future_other
    return max(0, math.ceil(need / payments.remaining))


@dataclass(slots=True)
class MeterResult:
    period: PeriodSpec | None = None
    contract: Contract | None = None
    consumption: ConsumptionState | None = None
    used_billing: float | None = None  # bisheriger Verbrauch in der Abrechnungseinheit (kWh bzw. m³)
    forecast: Forecast | None = None
    forecast_total: float | None = None  # Prognose Verbrauch der Periode in der Abrechnungseinheit
    heat_model: HeatModel | None = None
    actual: CostBreakdown | None = None
    rest: CostBreakdown | None = None
    payments: PaymentState | None = None
    balance: Balance | None = None
    flags: list[str] = field(default_factory=list)


def _heat_samples(meter: Meter, daily: Mapping[date, DailyConsumption], readings: list[Reading], factor: float, today: date, tz: tzinfo) -> tuple[list[Sample], bool]:
    """Stichproben für die Regression: Tage (Sensor) oder Ableseperioden (nur Ablesungen). Letzte 365 Tage."""
    first = today - timedelta(days=365)
    if meter.entity:
        out = [
            Sample(d.consumption * factor, 1.0, d.degree_days, d.outdoor_temperature)
            for day, d in daily.items()
            if first <= day < today and usable(d.quality) and d.consumption is not None and d.degree_days is not None
            and "ersatzquelle" not in d.quality_flags
        ]
        return out, False
    rs = [r for r in valid_readings(readings, meter.meter_id) if r.timestamp.astimezone(tz).date() >= first]
    out = []
    for a, b in zip(rs, rs[1:]):
        d0, d1 = a.timestamp.astimezone(tz).date(), b.timestamp.astimezone(tz).date()
        days = [d0 + timedelta(days=i) for i in range((d1 - d0).days)]
        dds = [daily[x].degree_days for x in days if x in daily and daily[x].degree_days is not None]
        temps = [daily[x].outdoor_temperature for x in days if x in daily and daily[x].outdoor_temperature is not None]
        if not days or len(dds) < 0.9 * len(days):
            continue
        dd = sum(dds) * len(days) / len(dds)
        cons = (continuous_value(meter, b, tz) - continuous_value(meter, a, tz)) * factor
        out.append(Sample(cons, float(len(days)), dd, sum(temps) / len(temps) if temps else None))
    return out, True


def evaluate_meter(
    meter: Meter,
    contracts: list[Contract],
    prices: list[PriceSegment],
    plans: list[AdvancePlan],
    payments: list[Payment],
    readings: list[Reading],
    daily: Mapping[date, DailyConsumption],
    now: datetime,
    tz: tzinfo,
    current: tuple[datetime, float] | None,
    tolerance_pct: float = 5.0,
    actual_ends: dict[str, dict[date, date]] | None = None,
    sub_daily: Mapping[date, DailyConsumption] | None = None,
    garden_daily: Mapping[date, DailyConsumption] | None = None,
    heat_model_override: HeatModel | None = None,
) -> MeterResult:
    """Vollständige Auswertung eines Zählers für die laufende Periode."""
    res = MeterResult()
    today = now.astimezone(tz).date()
    spec = current_period(contracts, today, actual_ends)
    if spec is None:
        res.flags.append("keine_periode")
        return res
    res.period = spec
    contract = next(c for c in contracts if c.contract_id == spec.contract_id)
    res.contract = contract
    cons = calculate_consumption(meter, readings, daily, spec.start_date, tz, current)
    res.consumption = cons
    start_dt = day_bounds(spec.start_date, tz)[0]
    end_dt = day_bounds(spec.end_date, tz)[1]
    known_until = cons.known_until or now
    known_day = known_until.astimezone(tz).date()
    segs = [p for p in prices if p.contract_id == contract.contract_id]
    seg_now = segment_on(segs, known_day)
    factor = energy_factor(meter, seg_now)
    if factor is None:
        # Gas in m³ ohne Brennwert/Zustandszahl: keine kWh, keine Regression, keine Prognose (Regel 10)
        res.flags.append("brennwert_fehlt")

    # --- Verbrauch je Tag (für tagesgenaue Preise): Tageswerte, Rest auf den letzten bekannten Tag
    used_by_day: dict[date, float] = {}
    if cons.used is not None:
        d = spec.start_date
        while d < known_day:
            dv = daily.get(d)
            if dv is not None and dv.consumption is not None and usable(dv.quality):
                used_by_day[d] = dv.consumption
            d += timedelta(days=1)
        s = sum(used_by_day.values())
        if s > cons.used and s > 0:  # Tageswerte passen nicht zum Stand: anteilig kürzen
            used_by_day = {k: v * cons.used / s for k, v in used_by_day.items()}
            res.flags.append("tageswerte_angepasst")
        used_by_day[known_day] = used_by_day.get(known_day, 0.0) + max(cons.used - sum(used_by_day.values()), 0.0)
        # in der Abrechnungseinheit, tageweise mit dem jeweils gültigen Brennwert
        day_factors = [energy_factor(meter, segment_on(segs, k) or seg_now) for k in used_by_day]
        if factor is not None and all(f is not None for f in day_factors):
            res.used_billing = round(sum(q * f for q, f in zip(used_by_day.values(), day_factors)), 4)

    def usable_values(src: Mapping[date, DailyConsumption] | None) -> dict[date, float | None]:
        return {k: (v.consumption if usable(v.quality) else None) for k, v in (src or {}).items()}

    # --- Prognose (Mengen)
    elapsed = (known_until - start_dt).total_seconds() / 86400
    if meter.medium in HEAT_MEDIA:
        if factor is None:
            model = HeatModel(flags=["brennwert_fehlt"])
        elif heat_model_override is not None:
            model = heat_model_override
        else:
            samples, per_period = _heat_samples(meter, daily, readings, factor, today, tz)
            model = fit_heat_model(samples, per_period)
        res.heat_model = model
        dd_prev = {k: v.degree_days for k, v in daily.items()}
        fc = heat_forecast(model, dd_prev, known_day, spec.end_date)
        rest_billing_unit = True
    else:
        main_vals = usable_values(daily)
        used = cons.used
        fc_sub = None
        if sub_daily:
            sub_vals = usable_values(sub_daily)
            fc_sub = submeter_forecast(sub_vals, known_day, spec.end_date)
            if fc_sub.available and used is not None:
                # Tage ohne Wallbox-Wert: ganzer Verbrauch zählt als Grundlast (nicht als Wallbox = 0); als Lücke markiert
                gaps = [k for k in main_vals if main_vals[k] is not None and sub_vals.get(k) is None]
                sub_used = sum(v for k, v in sub_vals.items() if v is not None and spec.start_date <= k < known_day)
                base_vals = {k: (v - sub_vals[k]) if v is not None and sub_vals.get(k) is not None else v for k, v in main_vals.items()}
                main_vals, used = base_vals, max(used - sub_used, 0.0)
                res.flags.append("wallbox_getrennt")
                if any(spec.start_date <= k < known_day for k in gaps):
                    res.flags.append("wallbox_luecken")
        fc = baseload_forecast(used, spec.start_date, known_day, spec.end_date, main_vals, elapsed, meter.annual_consumption)
        if fc_sub is not None and fc_sub.available and fc.available:
            fc.rest = round(fc.rest + fc_sub.rest, 4)
            for k, v in fc_sub.rest_by_day.items():
                fc.rest_by_day[k] = fc.rest_by_day.get(k, 0.0) + v
            fc.details["wallbox_rest"] = fc_sub.rest
        rest_billing_unit = False
    res.forecast = fc
    if fc.available and res.used_billing is not None and factor is not None:
        res.forecast_total = round(res.used_billing + (fc.rest if rest_billing_unit else fc.rest * factor), 4)

    # --- Kosten (Euro) und Zahlungen
    garden = usable_values(garden_daily) if garden_daily else {}
    if cons.used is not None:
        ww = {k: max(v - (garden.get(k) or 0.0), 0.0) for k, v in used_by_day.items()} if meter.medium == Medium.WASSER else None
        res.actual = calculate_costs(contract, prices, meter, used_by_day, start_dt, known_until, tz, wastewater=ww)
    if fc.available and factor is not None:
        ww_rest = None
        if meter.medium == Medium.WASSER:
            # Gartenwasser geht auch im Rest nicht ins Abwasser: Gartenzähler wie die Wallbox fortschreiben
            g_fc = submeter_forecast(garden, known_day, spec.end_date) if garden else None
            g_rest = g_fc.rest_by_day if g_fc is not None and g_fc.available else {}
            ww_rest = {k: max(v - g_rest.get(k, 0.0), 0.0) for k, v in fc.rest_by_day.items()}
            if garden and not g_rest:
                res.flags.append("garten_ohne_prognose")
        res.rest = calculate_costs(contract, prices, meter, fc.rest_by_day, known_until, end_dt, tz,
                                   quantities_are_billing_unit=rest_billing_unit, wastewater=ww_rest)
    plan = next((p for p in plans if p.contract_id == contract.contract_id), None)
    res.payments = calculate_payments(plan, [p for p in payments if p.contract_id == contract.contract_id], spec.start_date, spec.end_date, today)
    forecast_cost = None
    if res.actual is not None and res.rest is not None and res.actual.complete and res.rest.complete:
        forecast_cost = round(res.actual.gross + res.rest.gross, 2)
    res.balance = calculate_balance(forecast_cost, res.payments, tolerance_pct)
    res.balance.actual_cost = round(res.actual.gross, 2) if res.actual is not None and res.actual.complete else None
    for cb in (res.actual, res.rest):
        if cb is not None:
            res.flags.extend(cb.flags)
    res.flags = sorted(set(res.flags))
    return res
