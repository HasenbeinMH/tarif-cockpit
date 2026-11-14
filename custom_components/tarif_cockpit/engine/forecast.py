"""Bereich Prognose: Restverbrauch bis zum Ende der laufenden Periode. Liefert **Mengen, keine Euro** (Arbeitspaket 1).

- Grundlast (Strom, Wasser): Vorjahr im gleichen Kalenderfenster; die bisherige Abweichung zum Vorjahr
  (begrenzt auf 70–150 %) wirkt zur Hälfte auf den Rest. Rückfallebenen: Durchschnitt seit Periodenbeginn
  (ab 30 Tagen, "vorläufig"), Jahresverbrauch laut letzter Rechnung tagesanteilig ("Annahme"), sonst keine Prognose.
- Wallbox (Entscheidung D): Unterzähler vor der Grundlast abgezogen und getrennt fortgeschrieben.
- Wärme: Kennwert × Rest-Gradtage (+ WW-Grundlast × Resttage) aus dem Vorjahresfenster. Ohne belastbares Modell
  (mindestens "vorläufig") keine Prognose (Regel 10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from .billing import add_years
from .consumption import window_sum
from .regression import HeatModel, ModelQuality

RATIO_MIN, RATIO_MAX = 0.7, 1.5
MIN_DAYS_OWN_AVERAGE = 30
MIN_DAYS_WALLBOX = 14
MIN_COVERAGE_PREV_YEAR = 0.8
MIN_COVERAGE_DEGREE_DAYS = 0.5


@dataclass(slots=True)
class Forecast:
    rest: float | None = None  # Restmenge bis Periodenende
    rest_by_day: dict[date, float] = field(default_factory=dict)
    quality: ModelQuality = ModelQuality.INSUFFICIENT
    method: str = "keine"  # vorjahr | mittel_seit_beginn | jahresrechnung | waerme | keine
    details: dict = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.rest is not None


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)] if last >= first else []


def _spread(total: float, days: list[date], weights: Mapping[date, float | None] | None = None) -> dict[date, float]:
    """Restmenge auf Tage verteilen: nach Gewichten (z. B. Vorjahrestage), sonst gleichmäßig."""
    if not days:
        return {}
    w = [max(weights.get(d) or 0.0, 0.0) for d in days] if weights else []
    s = sum(w)
    if not w or s <= 0:
        return {d: total / len(days) for d in days}
    return {d: total * wi / s for d, wi in zip(days, w)}


def _shift_back(values: Mapping[date, float | None], days: list[date]) -> dict[date, float | None]:
    """Werte des Vorjahres auf die Tage dieses Jahres legen."""
    return {d: values.get(add_years(d, -1)) for d in days}


def baseload_forecast(
    used: float | None,
    period_start: date,
    known_day: date,
    period_end: date,
    prev_values: Mapping[date, float | None],
    elapsed_days: float,
    annual: float | None = None,
) -> Forecast:
    """Grundlast-Prognose. ``prev_values``: Tagesverbrauch (auch des Vorjahres), None für fehlende Tage.
    ``known_day`` ist der Tag, bis zu dem der Verbrauch bekannt ist (dieser Tag zählt zum Rest, wie bisher)."""
    rest_days = _days(known_day, period_end)
    if not rest_days:
        return Forecast(rest=0.0, quality=ModelQuality.GOOD, method="periode_beendet")
    so_far = window_sum(prev_values, add_years(period_start, -1), add_years(known_day, -1) - timedelta(days=1), MIN_COVERAGE_PREV_YEAR)
    rest_prev = window_sum(prev_values, add_years(known_day, -1), add_years(period_end, -1), MIN_COVERAGE_PREV_YEAR)
    if used is not None and so_far.total and rest_prev.total is not None:
        ratio = min(max(used / so_far.total, RATIO_MIN), RATIO_MAX)
        rest = rest_prev.total * (1 + (ratio - 1) / 2)
        quality = ModelQuality.GOOD if min(so_far.coverage, rest_prev.coverage) >= 0.95 else ModelQuality.PRELIMINARY
        return Forecast(
            rest=round(rest, 4), rest_by_day=_spread(rest, rest_days, _shift_back(prev_values, rest_days)),
            quality=quality, method="vorjahr",
            details={"vorjahr_bisher": round(so_far.total, 3), "vorjahr_rest": round(rest_prev.total, 3), "verhaeltnis": round(ratio, 4),
                     "abdeckung": round(min(so_far.coverage, rest_prev.coverage), 3)},
        )
    if used is not None and elapsed_days >= MIN_DAYS_OWN_AVERAGE:
        rest = used / elapsed_days * len(rest_days)
        return Forecast(rest=round(rest, 4), rest_by_day=_spread(rest, rest_days), quality=ModelQuality.PRELIMINARY,
                        method="mittel_seit_beginn", details={"tage": round(elapsed_days, 2)})
    if annual:
        rest = annual * len(rest_days) / 365
        return Forecast(rest=round(rest, 4), rest_by_day=_spread(rest, rest_days), quality=ModelQuality.ASSUMPTION,
                        method="jahresrechnung", details={"jahresverbrauch": annual})
    return Forecast(details={"grund": "keine Vorjahresdaten und zu wenig eigene Daten"})


def submeter_forecast(sub_values: Mapping[date, float | None], known_day: date, period_end: date) -> Forecast:
    """Sonderverbraucher (Wallbox): Mittel der letzten 30 Tage × Resttage."""
    rest_days = _days(known_day, period_end)
    recent = [sub_values.get(known_day - timedelta(days=i)) for i in range(1, 31)]
    got = [v for v in recent if v is not None]
    if len(got) < MIN_DAYS_WALLBOX:
        return Forecast(details={"grund": "zu wenig Tage des Unterzählers"})
    avg = sum(got) / len(got)
    rest = avg * len(rest_days)
    return Forecast(rest=round(rest, 4), rest_by_day=_spread(rest, rest_days), quality=ModelQuality.PRELIMINARY,
                    method="mittel_30_tage", details={"tage": len(got), "mittel_je_tag": round(avg, 3)})


def heat_forecast(
    model: HeatModel,
    prev_degree_days: Mapping[date, float | None],
    known_day: date,
    period_end: date,
    relief_per_dd: float = 0.0,
) -> Forecast:
    """Wärme-Prognose in kWh: Kennwert × Rest-Gradtage aus dem Vorjahresfenster (+ WW × Resttage).

    ``relief_per_dd``: erwartete Entlastung je Gradtag (Kaminofen, Split-Klima), z. B. Ofenstunden je Gradtag × Ofen-Effekt;
    wird vom Kennwert abgezogen (nie unter 0)."""
    rest_days = _days(known_day, period_end)
    if not rest_days:
        return Forecast(rest=0.0, quality=model.confidence, method="periode_beendet")
    if not model.usable:
        return Forecast(quality=model.confidence, details={"grund": "kein belastbarer Kennwert", **model.as_dict()})
    shifted = _shift_back(prev_degree_days, rest_days)
    dd = window_sum(shifted, rest_days[0], rest_days[-1], MIN_COVERAGE_DEGREE_DAYS)
    if dd.total is None:
        return Forecast(quality=model.confidence, details={"grund": "Gradtage des Vorjahres fehlen"})
    k, ww = model.heat_coefficient or 0.0, model.hot_water_baseload or 0.0
    k_eff = max(k - max(relief_per_dd, 0.0), 0.0)
    rest = k_eff * dd.total + ww * len(rest_days)
    by_day = _spread(k_eff * dd.total, rest_days, shifted)
    for d in rest_days:
        by_day[d] = by_day.get(d, 0.0) + ww
    details = {"gradtage_rest": round(dd.total, 2), "hochgerechnet": dd.scaled, **model.as_dict()}
    if relief_per_dd > 0:
        details["entlastung_je_gradtag"] = round(relief_per_dd, 4)
        details["entlastung_rest"] = round((k - k_eff) * dd.total, 3)
    return Forecast(rest=round(rest, 4), rest_by_day=by_day, quality=model.confidence, method="waerme", details=details)
