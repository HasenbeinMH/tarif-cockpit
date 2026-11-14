"""Wärme-Regression mit Qualitätsbewertung (Arbeitspaket 3.2, Entscheidungen C, G). Eigene kleine Implementierung (Regel 7).

Modell: ``V = WW-Grundlast × Tage + Kennwert × Gradtage [− Ofen-Effekt × Ofenstunden] [− Entlastung × Klima-Energie]``
(ohne Achsenabschnitt). Stichproben sind Tage (Datenstufe 2) oder Ableseperioden (Datenstufe 1).

- Warmwasser nur, wenn es über die Heizung läuft (``hot_water``) und es Sommer-/Übergangsdaten gibt; sonst WW = 0.
- Ofen und Split-Klima/Wärmepumpe bekommen einen eigenen Term erst, wenn es je mindestens ``MIN_COMPARISON_DAYS``
  Tage mit und ohne Betrieb bei ähnlichen Gradtagen gibt (Entscheidung C). Vorher:
  Ofen: Annahme aus der Nennleistung (``Sample.stove_assumed``) wird zum Verbrauch addiert, damit der Kennwert
  nicht verfälscht wird; Klima: Betriebstage bleiben aus der Schätzung heraus, eine Entlastung gibt es nicht.
- Eine Annahme für den Kennwert gibt es nicht: Reichen die Daten nicht, ist die Qualität "unzureichend" (Regel 10).
- Zweiter Kennwert "temperaturbereinigt" mit Gradtagen aus der gemessenen Innentemperatur (wenn vorhanden).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
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
MIN_COMPARISON_DAYS = 10  # Vergleichstage je Gruppe (mit/ohne Ofen bzw. Klima), Entscheidung C
COMPARISON_BAND_KD = 2.0  # "ähnliche Gradtage": ± 2 Kd
ASSUMED_PCT_PER_K = 6.0  # Mehrverbrauch je Kelvin Raumtemperatur, nur Annahme
MIN_INDOOR_DAYS = 60


class ModelQuality(StrEnum):
    ASSUMPTION = "annahme"
    INSUFFICIENT = "unzureichend"
    PRELIMINARY = "vorlaeufig"
    GOOD = "gut"
    VERY_GOOD = "sehr_gut"


USABLE_FOR_FORECAST = (ModelQuality.PRELIMINARY, ModelQuality.GOOD, ModelQuality.VERY_GOOD)


@dataclass(slots=True, frozen=True)
class Sample:
    """Eine Stichprobe: Verbrauch (kWh) über ``days`` Tage mit ``degree_days`` Gradtagen; Temperaturmittel für die Spanne.

    Optional: Ofenstunden, Annahme der Ofen-Entlastung in kWh, Energie der Klimageräte/Wärmepumpen am Hausstrom
    (die dieses Medium entlasten könnten) und Gradtage aus der gemessenen Innentemperatur."""

    consumption: float
    days: float
    degree_days: float
    t_mean: float | None = None
    stove_hours: float | None = 0.0  # None = unbekannt (Ofen vorhanden, aber für diesen Tag keine Betriebsstunden)
    stove_assumed: float = 0.0
    hp_energy: float | None = 0.0  # None = unbekannt
    degree_days_indoor: float | None = None
    t_indoor: float | None = None


@dataclass(slots=True)
class HeatModel:
    heat_coefficient: float | None = None  # kWh je Gradtag
    hot_water_baseload: float | None = None  # kWh je Tag
    r_squared: float | None = None
    sample_count: int = 0
    temp_range_k: float | None = None
    confidence: ModelQuality = ModelQuality.INSUFFICIENT
    flags: list[str] = field(default_factory=list)
    # Kaminofen: Entlastung in kWh je Ofenstunde (gelernt oder Annahme)
    stove_coefficient: float | None = None
    stove_quality: ModelQuality | None = None
    # Split-Klima/Wärmepumpe am Hausstrom: vermiedene kWh dieses Mediums je kWh Strom (nur gelernt)
    hp_avoided_per_kwh: float | None = None
    hp_quality: ModelQuality | None = None
    # temperaturbereinigt (Gradtage aus der gemessenen Innentemperatur)
    heat_coefficient_indoor: float | None = None
    indoor_confidence: ModelQuality | None = None
    indoor_pct_per_k: float | None = None
    indoor_pct_quality: ModelQuality | None = None
    indoor_mean: float | None = None

    @property
    def usable(self) -> bool:
        return self.confidence in USABLE_FOR_FORECAST and self.heat_coefficient is not None

    def as_dict(self) -> dict:
        def r(v: float | None, n: int = 3) -> float | None:
            return None if v is None else round(v, n)

        out = {
            "heat_coefficient": r(self.heat_coefficient),
            "hot_water_baseload": r(self.hot_water_baseload),
            "r_squared": r(self.r_squared),
            "sample_count": self.sample_count,
            "temp_range_k": r(self.temp_range_k, 1),
            "confidence": self.confidence.value,
            "flags": list(self.flags),
        }
        if self.stove_quality is not None:
            out.update(stove_coefficient=r(self.stove_coefficient), stove_quality=self.stove_quality.value)
        if self.hp_quality is not None:
            out.update(hp_avoided_per_kwh=r(self.hp_avoided_per_kwh), hp_quality=self.hp_quality.value)
        if self.indoor_confidence is not None:
            out.update(heat_coefficient_indoor=r(self.heat_coefficient_indoor), indoor_confidence=self.indoor_confidence.value,
                       indoor_pct_per_k=r(self.indoor_pct_per_k, 2),
                       indoor_pct_quality=self.indoor_pct_quality.value if self.indoor_pct_quality else None,
                       indoor_mean=r(self.indoor_mean, 2))
        return out


# ---------------------------------------------------------------- Rechnen


def solve_least_squares(rows: Sequence[Sequence[float]], y: Sequence[float]) -> list[float] | None:
    """Kleinste Quadrate ohne Achsenabschnitt über die Normalgleichungen (Gauß mit Spaltenpivot). None, wenn singulär."""
    n = len(rows[0]) if rows else 0
    if n == 0 or len(rows) < n:
        return None
    a = [[sum(r[i] * r[j] for r in rows) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * yi for r, yi in zip(rows, y)) for i in range(n)]
    scale = max(abs(a[i][i]) for i in range(n)) or 1.0
    for col in range(n):
        piv = max(range(col, n), key=lambda i: abs(a[i][col]))
        if abs(a[piv][col]) <= 1e-9 * scale:
            return None
        a[col], a[piv] = a[piv], a[col]
        b[col], b[piv] = b[piv], b[col]
        for i in range(col + 1, n):
            f = a[i][col] / a[col][col]
            for j in range(col, n):
                a[i][j] -= f * a[col][j]
            b[i] -= f * b[col]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (b[i] - sum(a[i][j] * x[j] for j in range(i + 1, n))) / a[i][i]
    return x


def _span(samples: Sequence[Sample]) -> float:
    temps = [s.t_mean for s in samples if s.t_mean is not None]
    return (max(temps) - min(temps)) if temps else 0.0


def _r_squared(ys: Sequence[float], preds: Sequence[float]) -> float | None:
    mean = sum(ys) / len(ys)
    ss_tot = sum((v - mean) ** 2 for v in ys)
    ss_res = sum((v - p) ** 2 for v, p in zip(ys, preds))
    if ss_tot <= 0:
        return None
    return 1 - ss_res / ss_tot


def comparison_days(samples: Sequence[Sample], key: Callable[[Sample], float]) -> tuple[int, int]:
    """Vergleichstage (Entscheidung C): Heiztage mit Betrieb, zu denen es einen Tag ohne Betrieb mit ähnlichen Gradtagen
    gibt, und umgekehrt. Liefert (mit, ohne)."""
    heating = [s for s in samples if s.degree_days > 0 and s.days == 1]
    on = [s.degree_days for s in heating if key(s) > 0]
    off = [s.degree_days for s in heating if key(s) <= 0]

    def matched(group: list[float], other: list[float]) -> int:
        other = sorted(other)
        count = 0
        for g in group:
            # binäre Suche wäre schneller; die Mengen sind klein (≤ 365)
            if any(abs(o - g) <= COMPARISON_BAND_KD for o in other):
                count += 1
        return count

    return matched(on, off), matched(off, on)


def _enough_comparison(samples: Sequence[Sample], key: Callable[[Sample], float]) -> bool:
    with_, without = comparison_days(samples, key)
    return with_ >= MIN_COMPARISON_DAYS and without >= MIN_COMPARISON_DAYS


def _quality(r2: float | None, n: int, days_total: float, span: float, per_period: bool) -> ModelQuality:
    r2 = r2 if r2 is not None else 0.0
    if r2 >= R2_VERY_GOOD and not per_period and days_total >= VERY_GOOD_DAYS and span >= VERY_GOOD_SPAN_K:
        return ModelQuality.VERY_GOOD
    if r2 >= R2_GOOD and n >= (GOOD_MIN_PERIODS if per_period else GOOD_MIN_DAYS):
        return ModelQuality.GOOD
    if r2 >= R2_PRELIMINARY:
        return ModelQuality.PRELIMINARY
    return ModelQuality.INSUFFICIENT


def fit_heat_model(
    samples: list[Sample],
    per_period: bool = False,
    hot_water: bool = True,
    baseload: bool = False,
    indoor: bool = True,
) -> HeatModel:
    """Kennwert (und ggf. WW-Grundlast, Ofen- und Klima-Term) schätzen und die Qualität bewerten.

    ``hot_water=False``: Warmwasser läuft nicht über diese Heizung, WW-Term fest 0.
    ``baseload=True``: Tage-Term immer schätzen (Strom: Grundlast + witterungsabhängiger Anteil)."""
    samples = [s for s in samples if s.days > 0 and s.consumption >= 0]
    model = HeatModel()
    min_n = MIN_PERIODS if per_period else MIN_DAYS
    # Unbekannte Ofenstunden/Klima-Energie an Heiztagen sind nicht 0 (Regel 5): solche Tage herausnehmen, wenn genug übrig
    # bleibt; sonst als 0 behandeln und kennzeichnen. Außerhalb der Heizperiode zählen beide nicht (Klima kühlt dann).
    for attr, flag in (("stove_hours", "ofen"), ("hp_energy", "klima")):
        unknown = [s for s in samples if getattr(s, attr) is None and s.degree_days > 0]
        if unknown:
            rest = [s for s in samples if not (getattr(s, attr) is None and s.degree_days > 0)]
            if len(rest) >= min_n and _span(rest) >= MIN_SPAN_K:
                samples = rest
                model.flags.append(f"{flag}_unbekannte_tage_ausgeschlossen")
            else:
                model.flags.append(f"{flag}_stunden_unvollstaendig" if flag == "ofen" else "klima_unvollstaendig")
    samples = [replace(s, stove_hours=s.stove_hours or 0.0 if s.degree_days > 0 else 0.0,
                       stove_assumed=s.stove_assumed if s.degree_days > 0 else 0.0,
                       hp_energy=s.hp_energy or 0.0 if s.degree_days > 0 else 0.0) for s in samples]
    model.sample_count = len(samples)
    temps = [s.t_mean for s in samples if s.t_mean is not None]
    model.temp_range_k = (max(temps) - min(temps)) if temps else None
    enough = len(samples) >= min_n
    if not enough or model.temp_range_k is None or model.temp_range_k < MIN_SPAN_K:
        model.confidence = ModelQuality.INSUFFICIENT
        model.flags.append("zu_wenig_daten" if not enough else "zu_geringe_temperaturspanne")
        return model

    # --- Ofen und Klima: eigener Term nur mit Vergleichstagen (nur bei Tageswerten)
    has_stove = any(s.stove_hours > 0 for s in samples)
    has_hp = any(s.hp_energy > 0 for s in samples)
    learn_stove = has_stove and not per_period and _enough_comparison(samples, lambda s: s.stove_hours)
    learn_hp = has_hp and not per_period and _enough_comparison(samples, lambda s: s.hp_energy)
    if has_hp and not learn_hp:
        rest = [s for s in samples if s.hp_energy <= 0]
        if len(rest) >= min_n and _span(rest) >= MIN_SPAN_K:
            samples = rest  # Klimatage verfälschen sonst den Kennwert; Entlastung erst mit Vergleichstagen
            model.flags.append("klimatage_ausgeschlossen")
            model.sample_count = len(samples)
            model.temp_range_k = _span(samples)
        model.hp_quality = ModelQuality.INSUFFICIENT
        model.flags.append("klima_zu_wenig_vergleichstage")

    def target(s: Sample, with_assumption: bool) -> float:
        return s.consumption + (s.stove_assumed if with_assumption else 0.0)

    summer = sum(1 for s in samples if s.degree_days == 0)
    use_days = baseload or (hot_water and summer >= (2 if per_period else MIN_SUMMER_SAMPLES))
    if not hot_water and not baseload:
        model.flags.append("ww_aus")

    def build(days_term: bool, stove_term: bool, hp_term: bool) -> tuple[list[str], list[list[float]], list[float]]:
        cols = (["days"] if days_term else []) + ["dd"] + (["stove"] if stove_term else []) + (["hp"] if hp_term else [])
        rows = []
        for s in samples:
            row = []
            for c in cols:
                row.append({"days": s.days, "dd": s.degree_days, "stove": -s.stove_hours, "hp": -s.hp_energy}[c])
            rows.append(row)
        # Annahme nur, solange es keine Vergleichstage gibt; mit Vergleichstagen zählen nur die Daten (Entscheidung C)
        ys = [target(s, has_stove and not learn_stove) for s in samples]
        return cols, rows, ys

    stove_term, hp_term = learn_stove, learn_hp
    coef: dict[str, float] = {}
    for _ in range(4):  # Terme mit unsinnigem Vorzeichen nacheinander herausnehmen
        cols, rows, ys = build(use_days, stove_term, hp_term)
        x = solve_least_squares(rows, ys)
        if x is None:
            model.confidence = ModelQuality.INSUFFICIENT
            model.flags.append("nicht_loesbar" if any(s.degree_days > 0 for s in samples) else "keine_heiztage")
            return model
        coef = dict(zip(cols, x))
        if use_days and coef.get("days", 0.0) < 0 and not baseload:
            use_days = False
            model.flags.append("ww_nicht_getrennt")
            continue
        if stove_term and coef.get("stove", 0.0) <= 0:
            stove_term = False
            model.flags.append("ofen_kein_effekt")
            continue
        if hp_term and coef.get("hp", 0.0) <= 0:
            hp_term = False
            model.flags.append("klima_kein_effekt")
            continue
        break
    if hot_water and not use_days and "ww_nicht_getrennt" not in model.flags and not baseload:
        model.flags.append("ww_nicht_getrennt")

    k = coef.get("dd", 0.0)
    ww = coef.get("days", 0.0) if use_days else 0.0
    model.heat_coefficient, model.hot_water_baseload = k, ww
    cols, rows, ys = build(use_days, stove_term, hp_term)
    preds = [sum(coef[c] * v for c, v in zip(cols, row)) for row in rows]
    model.r_squared = _r_squared(ys, preds)
    model.confidence = _quality(model.r_squared, len(samples), sum(s.days for s in samples), model.temp_range_k or 0.0, per_period)
    if model.confidence == ModelQuality.INSUFFICIENT:
        model.flags.append("geringe_erklaerung")
    if k <= 0:
        model.confidence = ModelQuality.INSUFFICIENT
        model.flags.append("kennwert_nicht_positiv")

    if has_stove:
        if stove_term:
            model.stove_coefficient = coef["stove"]
            model.stove_quality = model.confidence
        elif learn_stove:
            # genug Vergleichstage, aber kein Effekt messbar: keine Annahme mehr (die Daten sagen "keine Entlastung")
            model.stove_coefficient = 0.0
            model.stove_quality = model.confidence
        else:
            hours = sum(s.stove_hours for s in samples)
            assumed = sum(s.stove_assumed for s in samples)
            model.stove_coefficient = assumed / hours if hours > 0 and assumed > 0 else None
            model.stove_quality = ModelQuality.ASSUMPTION if model.stove_coefficient else ModelQuality.INSUFFICIENT
            if not learn_stove:
                model.flags.append("ofen_annahme")
    if hp_term:
        model.hp_avoided_per_kwh = coef["hp"]
        model.hp_quality = model.confidence

    if indoor and not per_period:
        _fit_indoor(model, samples, hot_water, baseload)
    return model


def _fit_indoor(model: HeatModel, samples: list[Sample], hot_water: bool, baseload: bool) -> None:
    """Temperaturbereinigter Kennwert: dasselbe Modell mit Gradtagen aus der gemessenen Innentemperatur.
    %/K = 1 / mittlere Differenz innen–außen an Heiztagen (gelernt); ohne Innenwerte 6 %/K als Annahme."""
    with_in = [s for s in samples if s.degree_days_indoor is not None]
    if len(with_in) < MIN_DAYS:
        model.indoor_pct_per_k = ASSUMED_PCT_PER_K
        model.indoor_pct_quality = ModelQuality.ASSUMPTION
        if with_in:
            model.indoor_confidence = ModelQuality.INSUFFICIENT
        return
    sub = fit_heat_model(
        [replace(s, degree_days=s.degree_days_indoor or 0.0, degree_days_indoor=None) for s in with_in],
        hot_water=hot_water, baseload=baseload, indoor=False,
    )
    model.heat_coefficient_indoor = sub.heat_coefficient if sub.usable else None
    model.indoor_confidence = sub.confidence
    heating = [s for s in with_in if (s.degree_days_indoor or 0) > 0]
    tins = [s.t_indoor for s in with_in if s.t_indoor is not None]
    model.indoor_mean = sum(tins) / len(tins) if tins else None
    if sub.usable and heating:
        diff = sum(s.degree_days_indoor or 0.0 for s in heating) / len(heating)
        model.indoor_pct_per_k = 100.0 / diff if diff > 0 else ASSUMED_PCT_PER_K
        model.indoor_pct_quality = sub.confidence if diff > 0 and len(with_in) >= MIN_INDOOR_DAYS else ModelQuality.ASSUMPTION
    else:
        model.indoor_pct_per_k = ASSUMED_PCT_PER_K
        model.indoor_pct_quality = ModelQuality.ASSUMPTION
