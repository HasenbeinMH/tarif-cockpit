"""Bereich Ergebnis: Saldo, Urteil, empfohlener Abschlag (Arbeitspaket 3.3) und die Auswertung eines Zählers.

``evaluate_meter`` verbindet die vier Bereiche, ohne sie zu vermischen:
Verbrauch (consumption) → Prognose als Menge (forecast) → Kosten und Zahlungen (billing) → Ergebnis (hier).
Eine Preisänderung ändert damit nie die Verbrauchsprognose; ein neuer Abschlagsplan nie den Verbrauch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, tzinfo
import math

from .billing import (
    CostBreakdown, PaymentState, PeriodSpec, add_years, calculate_costs, calculate_payments, current_period, energy_factor,
    segment_on,
)
from .consumption import ConsumptionState, calculate_consumption, day_bounds, valid_readings, continuous_value
from .forecast import Forecast, baseload_forecast, heat_forecast, submeter_forecast
from .model import AdvancePlan, Contract, DailyConsumption, Medium, Meter, Payment, PriceSegment, Reading
from .quality import usable
from .regression import HeatModel, ModelQuality, Sample, fit_heat_model

HEAT_MEDIA = (Medium.GAS, Medium.FERNWAERME)
MIN_DD_FOR_RATE = 50.0  # Gradtage, ab denen die Ofenstunden/Klima-Energie je Gradtag der laufenden Periode zählen


@dataclass(slots=True)
class PowerHeat:
    """Wärmeerzeuger am Haushaltsstrom (Split-Klima, Wärmepumpe, Elektroheizung) für die Strom-Prognose.

    ``measured``: Tagesenergie aus eigener Messung (Energie-/Leistungs-Entität); ohne Messung wird der witterungsabhängige
    Anteil des Hausstroms über die Gradtage geschätzt."""

    measured: Mapping[date, float | None] | None = None
    whole_meter: bool = False  # der ganze Zähler ist Heizstrom (Wärmepumpe am eigenen Zähler): keine Grundlast


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
    # Band (1.0): Prognose-Kosten und Saldo, wenn der Rest so kalt bzw. mild wird wie im kältesten/wärmsten Vorjahr
    forecast_cost_cold: float | None = None
    forecast_cost_warm: float | None = None
    saldo_cold: float | None = None
    saldo_warm: float | None = None


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
    used_by_day: dict[date, float] = field(default_factory=dict)  # Verbrauch je Tag der Periode (Zählereinheit)
    samples: list[Sample] = field(default_factory=list)  # Stichproben der Wärme-Regression (Streudiagramm)
    samples_per_period: bool = False
    power_heat_model: HeatModel | None = None  # Strom: witterungsabhängiger Anteil (Heizen am Hausstrom)
    indoor_split: dict | None = None  # Vergleich zum Vorjahr: Mehrverbrauch gesamt, davon Raumtemperatur, davon Verhalten


def _indoor_dd(d: DailyConsumption) -> float | None:
    """Gradtage aus der gemessenen Innentemperatur (statt Innenbezug): Heiztag → innen − außen, sonst 0."""
    if d.indoor_temperature is None or d.outdoor_temperature is None or d.degree_days is None:
        return None
    return max(d.indoor_temperature - d.outdoor_temperature, 0.0) if d.degree_days > 0 else 0.0


def _heat_samples(
    meter: Meter,
    daily: Mapping[date, DailyConsumption],
    readings: list[Reading],
    factor: float,
    today: date,
    tz: tzinfo,
    stove_hours: Mapping[date, float | None] | None = None,
    stove_relief: float | None = None,
    hp_energy: Mapping[date, float | None] | None = None,
) -> tuple[list[Sample], bool]:
    """Stichproben für die Regression: Tage (Sensor) oder Ableseperioden (nur Ablesungen). Letzte 365 Tage."""
    first = today - timedelta(days=365)
    if meter.entity:
        out = []
        for day, d in daily.items():
            if not (first <= day < today and usable(d.quality) and d.consumption is not None and d.degree_days is not None
                    and "ersatzquelle" not in d.quality_flags):
                continue
            # mit Ofen/Klima: fehlender Tageswert = unbekannt (None), nicht 0 (Regel 5)
            h = stove_hours.get(day) if stove_hours else 0.0
            e = hp_energy.get(day) if hp_energy else 0.0
            out.append(Sample(
                d.consumption * factor, 1.0, d.degree_days, d.outdoor_temperature,
                stove_hours=h, stove_assumed=(h or 0.0) * (stove_relief or 0.0), hp_energy=e,
                degree_days_indoor=_indoor_dd(d), t_indoor=d.indoor_temperature,
            ))
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
        h = sum((stove_hours or {}).get(x) or 0.0 for x in days)
        out.append(Sample(cons, float(len(days)), dd, sum(temps) / len(temps) if temps else None,
                          stove_hours=h, stove_assumed=h * (stove_relief or 0.0)))
    return out, True


def _rate_per_dd(values: Mapping[date, float | None], daily: Mapping[date, DailyConsumption], start: date, end: date,
                 known_day: date) -> float:
    """Ofenstunden bzw. Klima-Energie je Gradtag: laufende Periode bis heute; zu wenig Gradtage → gleiches Fenster im Vorjahr."""
    def ratio(first: date, last: date) -> tuple[float, float]:
        v_sum = dd_sum = 0.0
        d = first
        while d <= last:
            dv = daily.get(d)
            # nur Tage mit bekanntem Wert (fehlende Ofenstunden sind nicht 0)
            if dv is not None and dv.degree_days and values.get(d) is not None:
                dd_sum += dv.degree_days
                v_sum += values[d]
            d += timedelta(days=1)
        return v_sum, dd_sum

    v, dd = ratio(start, known_day - timedelta(days=1))
    if dd >= MIN_DD_FOR_RATE:
        return v / dd
    v, dd = ratio(add_years(start, -1), add_years(end, -1))
    return v / dd if dd >= MIN_DD_FOR_RATE else 0.0


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
    hot_water: bool = True,
    stove_hours: Mapping[date, float | None] | None = None,
    stove_relief: float | None = None,
    hp_energy: Mapping[date, float | None] | None = None,
    power_heat: PowerHeat | None = None,
    sensor_offset: float | None = None,
    forecast_dd: Mapping[date, float] | None = None,
) -> MeterResult:
    """Vollständige Auswertung eines Zählers für die laufende Periode.

    Wärme: ``hot_water`` (WW über diese Heizung), ``stove_hours`` und ``stove_relief`` (Ofenstunden je Tag, Annahme der
    Entlastung je Stunde), ``hp_energy`` (Strom der Klimageräte/Wärmepumpen je Tag, die dieses Medium entlasten können).
    Strom: ``power_heat`` (Heizen am Hausstrom, vor der Grundlast abgezogen)."""
    res = MeterResult()
    today = now.astimezone(tz).date()
    spec = current_period(contracts, today, actual_ends)
    if spec is None:
        res.flags.append("keine_periode")
        return res
    res.period = spec
    contract = next(c for c in contracts if c.contract_id == spec.contract_id)
    res.contract = contract
    cons = calculate_consumption(meter, readings, daily, spec.start_date, tz, current, sensor_offset)
    res.consumption = cons
    if cons.used is not None and cons.start_source == "daily_end_value" and current is not None:
        # Startwert aus der Statistik: angeglichene Tageswerte gelten (Ablesung schlägt Sensor), heute der Sensor
        today_ = now.astimezone(tz).date()
        days_ = [spec.start_date + timedelta(days=i) for i in range((today_ - spec.start_date).days)]
        vals = [daily.get(d) for d in days_]
        if days_ and all(v is not None and v.consumption is not None and usable(v.quality) for v in vals) \
                and any("abgeglichen" in v.quality_flags for v in vals) and vals[-1].end_value is not None:
            cons.used = round(sum(v.consumption for v in vals) + max(current[1] - vals[-1].end_value, 0.0), 6)
            cons.flags.append("abgleich_tageswerte")
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
    res.used_by_day = dict(used_by_day)

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
            samples, per_period = _heat_samples(meter, daily, readings, factor, today, tz, stove_hours, stove_relief, hp_energy)
            model = fit_heat_model(samples, per_period, hot_water=hot_water)
            res.samples, res.samples_per_period = samples, per_period
        res.heat_model = model
        dd_prev = {k: v.degree_days for k, v in daily.items()}
        # erwartete Entlastung je Gradtag im Rest der Periode (Ofen: gelernt oder Annahme; Klima: nur gelernt)
        relief = 0.0
        if stove_hours and model.stove_coefficient:
            relief += _rate_per_dd(stove_hours, daily, spec.start_date, spec.end_date, known_day) * model.stove_coefficient
        if hp_energy and model.hp_avoided_per_kwh and model.hp_quality in (ModelQuality.PRELIMINARY, ModelQuality.GOOD, ModelQuality.VERY_GOOD):
            relief += _rate_per_dd(hp_energy, daily, spec.start_date, spec.end_date, known_day) * model.hp_avoided_per_kwh
        fc = heat_forecast(model, dd_prev, known_day, spec.end_date, relief_per_dd=relief, forecast_dd=forecast_dd)
        res.indoor_split = indoor_split(daily, model, spec.start_date, known_day)
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
        fc_heat = None
        if power_heat is not None and used is not None:
            main_vals, used, fc_heat = _split_power_heat(res, power_heat, main_vals, used, daily, spec, known_day, today, forecast_dd)
        if power_heat is not None and power_heat.whole_meter and fc_heat is not None and fc_sub is None:
            # Wärmepumpe am eigenen Zähler: der ganze Zähler ist Heizstrom, keine Grundlast-Prognose
            fc = Forecast(rest=fc_heat.rest, rest_by_day=dict(fc_heat.rest_by_day), quality=fc_heat.quality,
                          method="waermepumpe_" + fc_heat.method, details={**fc_heat.details, "heizstrom_rest": fc_heat.rest})
            fc_heat = None
        else:
            fc = baseload_forecast(used, spec.start_date, known_day, spec.end_date, main_vals, elapsed, meter.annual_consumption)
        if fc_sub is not None and fc_sub.available and fc.available:
            fc.rest = round(fc.rest + fc_sub.rest, 4)
            for k, v in fc_sub.rest_by_day.items():
                fc.rest_by_day[k] = fc.rest_by_day.get(k, 0.0) + v
            fc.details["wallbox_rest"] = fc_sub.rest
        if fc_heat is not None and fc.available:
            fc.rest = round(fc.rest + (fc_heat.rest or 0.0), 4)
            for k, v in fc_heat.rest_by_day.items():
                fc.rest_by_day[k] = fc.rest_by_day.get(k, 0.0) + v
            fc.details["heizstrom_rest"] = fc_heat.rest
            fc.details["heizstrom_methode"] = fc_heat.method
        rest_billing_unit = False
    res.forecast = fc
    if fc.available and res.used_billing is not None and factor is not None:
        res.forecast_total = round(res.used_billing + (fc.rest if rest_billing_unit else fc.rest * factor), 4)

    # --- Kosten (Euro) und Zahlungen
    garden = usable_values(garden_daily) if garden_daily else {}
    if cons.used is not None:
        ww = {k: max(v - (garden.get(k) or 0.0), 0.0) for k, v in used_by_day.items()} if meter.medium == Medium.WASSER else None
        res.actual = calculate_costs(contract, prices, meter, used_by_day, start_dt, known_until, tz, wastewater=ww)
    ww_rest = None
    if fc.available and factor is not None:
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
    if forecast_cost is not None and fc.rest and "rest_kalt" in fc.details and ww_rest is None:
        for key, qty in (("cold", fc.details["rest_kalt"]), ("warm", fc.details["rest_warm"])):
            scaled = {d: v * qty / fc.rest for d, v in fc.rest_by_day.items()}
            band = calculate_costs(contract, prices, meter, scaled, known_until, end_dt, tz, quantities_are_billing_unit=rest_billing_unit)
            if band.complete:
                cost = round(res.actual.gross + band.gross, 2)
                setattr(res.balance, f"forecast_cost_{key}", cost)
                setattr(res.balance, f"saldo_{key}", round(res.payments.period_total - cost, 2) if res.payments.period_total else None)
    for cb in (res.actual, res.rest):
        if cb is not None:
            res.flags.extend(cb.flags)
    res.flags = sorted(set(res.flags))
    return res


def _split_power_heat(
    res: MeterResult,
    ph: PowerHeat,
    main_vals: dict[date, float | None],
    used: float,
    daily: Mapping[date, DailyConsumption],
    spec: PeriodSpec,
    known_day: date,
    today: date,
    forecast_dd: Mapping[date, float] | None = None,
) -> tuple[dict[date, float | None], float, Forecast | None]:
    """Heizen am Hausstrom vor der Grundlast abziehen (wie die Wallbox) und getrennt über die Gradtage fortschreiben.

    Mit eigener Messung: Tageswerte der Messung abziehen; Rest = eigene Gradtag-Regression der Messung (sonst Mittel
    der letzten 30 Tage). Ohne Messung: Hausstrom = Grundlast × Tage + b × Gradtage; abgezogen wird b × Gradtage, nur mit
    einem Modell ab "vorläufig" (sonst bleibt alles Grundlast, Flag ``heizstrom_nicht_getrennt``)."""
    first = today - timedelta(days=365)
    dd_prev = {k: v.degree_days for k, v in daily.items()}
    if ph.measured:
        meas = ph.measured
        samples = [Sample(v, 1.0, daily[k].degree_days or 0.0, daily[k].outdoor_temperature)
                   for k, v in meas.items() if v is not None and first <= k < today and k in daily and daily[k].degree_days is not None]
        model = fit_heat_model(samples, baseload=True, indoor=False)
        res.power_heat_model, res.samples = model, samples
        heat_used = sum(v for k, v in meas.items() if v is not None and spec.start_date <= k < known_day)
        base_vals = {k: (v - meas[k]) if v is not None and meas.get(k) is not None else v for k, v in main_vals.items()}
        fc = heat_forecast(model, dd_prev, known_day, spec.end_date, forecast_dd=forecast_dd) if model.usable else submeter_forecast(meas, known_day, spec.end_date)
        if not fc.available:
            res.flags.append("heizstrom_ohne_prognose")
            return main_vals, used, None
        res.flags.append("heizstrom_gemessen")
        return base_vals, max(used - heat_used, 0.0), fc
    samples = [Sample(v, 1.0, daily[k].degree_days or 0.0, daily[k].outdoor_temperature)
               for k, v in main_vals.items() if v is not None and first <= k < today and k in daily and daily[k].degree_days is not None]
    model = fit_heat_model(samples, baseload=True, indoor=False)
    res.power_heat_model, res.samples = model, samples
    k_dd = model.heat_coefficient or 0.0
    if not model.usable or k_dd <= 0:
        res.flags.append("heizstrom_nicht_getrennt")
        return main_vals, used, None
    weather = {k: k_dd * (daily[k].degree_days or 0.0) if k in daily and daily[k].degree_days is not None else 0.0 for k in main_vals}
    base_vals = {k: (v - weather[k]) if v is not None else None for k, v in main_vals.items()}
    heat_used = sum(weather[k] for k in main_vals if spec.start_date <= k < known_day and main_vals[k] is not None)
    fc = heat_forecast(replace(model, hot_water_baseload=0.0), dd_prev, known_day, spec.end_date, forecast_dd=forecast_dd)
    if not fc.available:
        res.flags.append("heizstrom_nicht_getrennt")
        return main_vals, used, None
    fc.method = "gradtage_hausstrom"
    res.flags.append("heizstrom_geschaetzt")
    return base_vals, max(used - heat_used, 0.0), fc


MIN_SPLIT_DAYS = 60


def indoor_split(daily: Mapping[date, DailyConsumption], model: HeatModel, start: date, known_day: date) -> dict | None:
    """Aufteilung "+8 %: +5 % Mehrverbrauch, +3 % durch höhere Raumtemperatur" gegen das gleiche Fenster im Vorjahr.

    Witterungsbereinigt (Verbrauch je Gradtag an Heiztagen) ändert sich der Verbrauch um ``gesamt``; davon erklärt die
    Änderung der mittleren Innentemperatur × %/K den Anteil ``raumtemperatur``, der Rest ist ``verhalten``.
    Nur bei ausreichender Datenlage (Regel 10): temperaturbereinigtes Modell ab "vorläufig", gelernter %/K-Wert und
    je mindestens 60 Heiztage mit Innentemperatur in beiden Fenstern."""
    if model.indoor_pct_quality in (None, ModelQuality.ASSUMPTION, ModelQuality.INSUFFICIENT) or not model.indoor_pct_per_k:
        return None
    if not model.usable:  # auch das Modell mit Außentemperatur muss mindestens "vorläufig" sein
        return None

    def window(first: date, last: date) -> tuple[float, float, list[float]]:
        cons = dd = 0.0
        tins: list[float] = []
        d = first
        while d <= last:
            v = daily.get(d)
            if v is not None and v.consumption is not None and v.degree_days and v.indoor_temperature is not None and usable(v.quality):
                cons += v.consumption
                dd += v.degree_days
                tins.append(v.indoor_temperature)
            d += timedelta(days=1)
        return cons, dd, tins

    c1, dd1, t1 = window(start, known_day - timedelta(days=1))
    c0, dd0, t0 = window(add_years(start, -1), add_years(known_day, -1) - timedelta(days=1))
    if len(t1) < MIN_SPLIT_DAYS or len(t0) < MIN_SPLIT_DAYS or dd1 <= 0 or dd0 <= 0 or c0 <= 0:
        return None
    total = ((c1 / dd1) / (c0 / dd0) - 1) * 100
    delta_t = sum(t1) / len(t1) - sum(t0) / len(t0)
    room = delta_t * model.indoor_pct_per_k
    return {"gesamt_pct": round(total, 1), "raumtemperatur_pct": round(room, 1), "verhalten_pct": round(total - room, 1),
            "innen_aenderung_k": round(delta_t, 2), "tage": len(t1)}
