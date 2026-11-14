"""Reihen für die Diagramme der Auswertungskarte (Arbeitspaket 6). Die Karte rechnet nichts (Regel 2): alles hier.

- Streudiagramm: Verbrauch je Tag über Gradtage je Tag, Ofen-/Klimatage markiert, Regressionsgerade mit Qualität.
  Ableseperioden (nur Ablesungen) werden auf Tagesmittel umgerechnet.
- Kostenverlauf: kumulierte Kosten der laufenden Periode (Ist bis heute, danach Prognose) gegen die Abschlags-Treppe.
  Monatsweise gerechnet und auf die Summen der Sensoren abgestimmt (Ist = Kosten bisher, Ende = Prognose Kosten).
"""

from __future__ import annotations

from datetime import date, timedelta, tzinfo

from .balance import MeterResult
from .billing import calculate_costs
from .consumption import day_bounds
from .model import Medium, Meter, PriceSegment


def scatter(res: MeterResult) -> dict | None:
    """Punkte (x = Gradtage je Tag, y = kWh je Tag) und Gerade y = WW + Kennwert × x."""
    m = res.heat_model or res.power_heat_model  # Strom: Heizen am Hausstrom bzw. Zähler der Wärmepumpe
    if m is None:
        return None
    pts = []
    for s in res.samples:
        if s.days <= 0:
            continue
        # gemessener Verbrauch; Ofentage liegen dadurch unter der Geraden (die Gerade ist der Bedarf ohne Ofen)
        p = {"x": round(s.degree_days / s.days, 2), "y": round(s.consumption / s.days, 2)}
        if (s.stove_hours or 0) > 0:
            p["ofen"] = round(s.stove_hours, 1)
        if (s.hp_energy or 0) > 0:
            p["klima"] = round(s.hp_energy, 1)
        pts.append(p)
    line = None
    if m.heat_coefficient is not None:
        xmax = max((p["x"] for p in pts), default=20.0)
        ww = m.hot_water_baseload or 0.0
        line = {"x0": 0.0, "y0": round(ww, 3), "x1": round(xmax, 2), "y1": round(ww + m.heat_coefficient * xmax, 3)}
    return {
        "punkte": pts,
        "gerade": line,
        "kennwert": None if m.heat_coefficient is None else round(m.heat_coefficient, 3),
        "ww": None if m.hot_water_baseload is None else round(m.hot_water_baseload, 3),
        "r2": None if m.r_squared is None else round(m.r_squared, 3),
        "qualitaet": m.confidence.value,
        "je_periode": res.samples_per_period,
        "ofen_effekt": None if m.stove_coefficient is None else round(m.stove_coefficient, 3),
        "ofen_qualitaet": m.stove_quality.value if m.stove_quality else None,
    }


def _month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """[start, end] in Monatsabschnitte (jeweils erster bis letzter Tag, an den Rändern gekürzt)."""
    out = []
    d = start
    while d <= end:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        last = min(nxt - timedelta(days=1), end)
        out.append((d, last))
        d = last + timedelta(days=1)
    return out


def cost_curve(res: MeterResult, meter: Meter, prices: list[PriceSegment], tz: tzinfo, today: date) -> dict | None:
    """Kumulierte Kosten (Ist + Prognose) und Abschläge je Monatsende der laufenden Periode."""
    if res.period is None or res.contract is None:
        return None
    spec, contract = res.period, res.contract
    known_day = max(res.used_by_day) if res.used_by_day else today
    ww_flag = meter.medium == Medium.WASSER

    def chunk_cost(quantities: dict[date, float], first: date, last: date, billing_unit: bool) -> float:
        q = {k: v for k, v in quantities.items() if first <= k <= last}
        cb = calculate_costs(contract, prices, meter, q, day_bounds(first, tz)[0], day_bounds(last, tz)[1], tz,
                             quantities_are_billing_unit=billing_unit, wastewater=q if ww_flag else None)
        return cb.gross

    ist: list[list] = []
    prog: list[list] = []
    if res.actual is not None and res.actual.complete:
        chunks = _month_chunks(spec.start_date, min(known_day, spec.end_date))
        raw = [chunk_cost(res.used_by_day, a, b, False) for a, b in chunks]
        total = sum(raw)
        scale = res.actual.gross / total if total > 0 else 1.0  # auf "Kosten bisher" abstimmen (Grundpreis bis jetzt)
        cum = 0.0
        ist.append([spec.start_date.isoformat(), 0.0])
        for (a, b), v in zip(chunks, raw):
            cum += v * scale
            ist.append([b.isoformat(), round(cum, 2)])
        if res.forecast is not None and res.forecast.available and res.rest is not None and res.rest.complete:
            billing_unit = meter.medium in (Medium.GAS, Medium.FERNWAERME)
            rchunks = _month_chunks(known_day, spec.end_date)
            rraw = [chunk_cost(res.forecast.rest_by_day, a, b, billing_unit) for a, b in rchunks]
            rtotal = sum(rraw)
            rscale = res.rest.gross / rtotal if rtotal > 0 else 1.0
            pcum = cum
            prog.append([known_day.isoformat(), round(cum, 2)])
            for (a, b), v in zip(rchunks, rraw):
                pcum += v * rscale
                prog.append([b.isoformat(), round(pcum, 2)])
    stairs: list[list] = []
    if res.payments is not None and res.payments.known:
        cum = 0.0
        stairs.append([spec.start_date.isoformat(), 0.0])
        items = [(i.date, i.amount) for i in res.payments.installments if i.status != "storniert"] + list(res.payments.others)
        for day, amount in sorted(items, key=lambda x: x[0]):
            cum += amount
            stairs.append([day.isoformat(), round(cum, 2)])
    return {
        "beginn": spec.start_date.isoformat(),
        "ende": spec.end_date.isoformat(),
        "heute": known_day.isoformat(),
        "ist": ist,
        "prognose": prog,
        "abschlaege": stairs,
        "prognose_kosten": res.balance.forecast_cost if res.balance else None,
    }
