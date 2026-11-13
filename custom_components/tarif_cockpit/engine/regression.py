"""Wärme-Regression mit Qualitätsbewertung (Arbeitspaket 3.2, Entscheidung G). Eigene kleine Implementierung (Regel 7).

Modell: ``V = WW-Grundlast × Tage + Kennwert × Gradtage`` (ohne Achsenabschnitt).
Stichproben sind Tage (Datenstufe 2) oder Ableseperioden (Datenstufe 1).
Warmwasser wird nur getrennt geschätzt, wenn es Sommer-/Übergangsdaten gibt (Stichproben ohne Gradtage);
sonst steckt es im Kennwert (WW = 0, Flag ``ww_nicht_getrennt``). Eine Annahme gibt es nicht: Reichen die Daten
nicht, ist die Qualität "unzureichend" und es gibt keine Prognose (Regel 10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# Startwerte, im Test justierbar
MIN_DAYS = 21
MIN_PERIODS = 4
MIN_SPAN_K = 5.0
R2_PRELIMINARY = 0.6
R2_GOOD = 0.8
GOOD_MIN_DAYS = 42
GOOD_MIN_PERIODS = 6
VERY_GOOD_DAYS = 90
VERY_GOOD_SPAN_K = 10.0
R2_VERY_GOOD = 0.85
MIN_SUMMER_SAMPLES = 7  # Tage ohne Gradtage, damit WW getrennt geschätzt wird


class ModelQuality(StrEnum):
    ASSUMPTION = "annahme"
    INSUFFICIENT = "unzureichend"
    PRELIMINARY = "vorlaeufig"
    GOOD = "gut"
    VERY_GOOD = "sehr_gut"


USABLE_FOR_FORECAST = (ModelQuality.PRELIMINARY, ModelQuality.GOOD, ModelQuality.VERY_GOOD)


@dataclass(slots=True, frozen=True)
class Sample:
    """Eine Stichprobe: Verbrauch (kWh) über ``days`` Tage mit ``degree_days`` Gradtagen; Temperaturmittel für die Spanne."""

    consumption: float
    days: float
    degree_days: float
    t_mean: float | None = None


@dataclass(slots=True)
class HeatModel:
    heat_coefficient: float | None = None  # kWh je Gradtag
    hot_water_baseload: float | None = None  # kWh je Tag
    r_squared: float | None = None
    sample_count: int = 0
    temp_range_k: float | None = None
    confidence: ModelQuality = ModelQuality.INSUFFICIENT
    flags: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.confidence in USABLE_FOR_FORECAST and self.heat_coefficient is not None

    def as_dict(self) -> dict:
        return {
            "heat_coefficient": None if self.heat_coefficient is None else round(self.heat_coefficient, 3),
            "hot_water_baseload": None if self.hot_water_baseload is None else round(self.hot_water_baseload, 3),
            "r_squared": None if self.r_squared is None else round(self.r_squared, 3),
            "sample_count": self.sample_count,
            "temp_range_k": None if self.temp_range_k is None else round(self.temp_range_k, 1),
            "confidence": self.confidence.value,
            "flags": list(self.flags),
        }


def _r_squared(samples: list[Sample], predict) -> float | None:
    ys = [s.consumption for s in samples]
    mean = sum(ys) / len(ys)
    ss_tot = sum((y - mean) ** 2 for y in ys)
    ss_res = sum((s.consumption - predict(s)) ** 2 for s in samples)
    if ss_tot <= 0:
        return None
    return 1 - ss_res / ss_tot


def fit_heat_model(samples: list[Sample], per_period: bool = False) -> HeatModel:
    """Kennwert (und ggf. WW-Grundlast) schätzen und die Qualität bewerten."""
    samples = [s for s in samples if s.days > 0 and s.consumption >= 0]
    model = HeatModel(sample_count=len(samples))
    temps = [s.t_mean for s in samples if s.t_mean is not None]
    model.temp_range_k = (max(temps) - min(temps)) if temps else None
    enough = len(samples) >= (MIN_PERIODS if per_period else MIN_DAYS)
    if not enough or model.temp_range_k is None or model.temp_range_k < MIN_SPAN_K:
        model.confidence = ModelQuality.INSUFFICIENT
        model.flags.append("zu_wenig_daten" if not enough else "zu_geringe_temperaturspanne")
        return model

    summer = sum(1 for s in samples if s.degree_days == 0)
    sxx = sum(s.degree_days ** 2 for s in samples)
    if summer >= (2 if per_period else MIN_SUMMER_SAMPLES):
        # Zwei Regressoren (Tage, Gradtage) ohne Achsenabschnitt: Normalgleichungen 2×2
        a11 = sum(s.days ** 2 for s in samples)
        a12 = sum(s.days * s.degree_days for s in samples)
        b1 = sum(s.days * s.consumption for s in samples)
        b2 = sum(s.degree_days * s.consumption for s in samples)
        det = a11 * sxx - a12 * a12
        if det <= 0:
            model.confidence = ModelQuality.INSUFFICIENT
            model.flags.append("nicht_loesbar")
            return model
        ww = (b1 * sxx - a12 * b2) / det
        k = (a11 * b2 - a12 * b1) / det
        if ww < 0:  # physikalisch unsinnig: WW nicht getrennt schätzbar
            ww, k = 0.0, b2 / sxx
            model.flags.append("ww_nicht_getrennt")
    else:
        if sxx <= 0:
            model.confidence = ModelQuality.INSUFFICIENT
            model.flags.append("keine_heiztage")
            return model
        ww, k = 0.0, sum(s.degree_days * s.consumption for s in samples) / sxx
        model.flags.append("ww_nicht_getrennt")

    model.heat_coefficient, model.hot_water_baseload = k, ww
    model.r_squared = _r_squared(samples, lambda s: ww * s.days + k * s.degree_days)
    r2 = model.r_squared if model.r_squared is not None else 0.0
    days_total = sum(s.days for s in samples)
    span = model.temp_range_k or 0.0
    if r2 >= R2_VERY_GOOD and not per_period and days_total >= VERY_GOOD_DAYS and span >= VERY_GOOD_SPAN_K:
        model.confidence = ModelQuality.VERY_GOOD
    elif r2 >= R2_GOOD and len(samples) >= (GOOD_MIN_PERIODS if per_period else GOOD_MIN_DAYS):
        model.confidence = ModelQuality.GOOD
    elif r2 >= R2_PRELIMINARY:
        model.confidence = ModelQuality.PRELIMINARY
    else:
        model.confidence = ModelQuality.INSUFFICIENT
        model.flags.append("geringe_erklaerung")
    if k <= 0:
        model.confidence = ModelQuality.INSUFFICIENT
        model.flags.append("kennwert_nicht_positiv")
    return model
