"""Leckage-Erkennung Wasser (1.2) aus den Stundenwerten.

- **Nachtminimum:** In den Stunden 1–5 Uhr (lokal) liegt der kleinste Stundenverbrauch in drei Nächten hintereinander
  über der Schwelle (Standard 5 L/h). Ein tropfender Hahn oder eine laufende Spülung fällt so auf.
- **Dauerfluss:** An zwei Tagen hintereinander fließt in jeder Stunde mindestens 1 L.
Gartenwasser (Unterzähler) wird je Stunde abgezogen. Tage ohne vollständige Stundenwerte zählen nicht (fehlend ist
nicht „kein Verbrauch“, Regel 5); eine Lücke unterbricht die Folge.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta, tzinfo

from .model import DailyConsumption
from .windows import slot_starts

NIGHT_HOURS = (1, 2, 3, 4)
NIGHTS = 3
CONTINUOUS_DAYS = 2
DEFAULT_THRESHOLD_LPH = 5.0
CONTINUOUS_MIN_LPH = 1.0  # Dauerfluss erst ab 1 L in jeder Stunde (Rauschen und Rundung der Zähler zählen nicht)


@dataclass(slots=True)
class LeakResult:
    suspect: bool = False
    kind: str | None = None  # nachtminimum | dauerfluss
    days: list[date] = field(default_factory=list)
    night_min_lph: float | None = None  # kleinstes Nachtminimum der betroffenen Nächte
    checked_days: int = 0

    def as_dict(self) -> dict:
        return {"verdacht": self.suspect, "art": self.kind, "tage": [d.isoformat() for d in self.days],
                "nachtminimum_l_h": None if self.night_min_lph is None else round(self.night_min_lph, 1),
                "gepruefte_tage": self.checked_days}


def _to_litres(unit: str) -> float:
    return 1000.0 if unit in ("m³", "m3") else 1.0


def _hours_l(day: date, d: DailyConsumption | None, garden: DailyConsumption | None, factor: float, tz: tzinfo,
             garden_expected: bool = False) -> list[tuple[int, float]] | None:
    hours = slot_starts(day, tz, 60)
    if d is None or not d.hourly or len(d.hourly) != len(hours) or any(v is None for v in d.hourly):
        return None
    g = None
    if garden is not None or garden_expected:
        # Gartenzähler vorhanden: ohne seine vollständigen Stunden ist der Tag nicht prüfbar (Bewässerung nachts)
        if garden is None or not garden.hourly or len(garden.hourly) != len(hours) or any(v is None for v in garden.hourly):
            return None
        g = garden.hourly
    out = []
    for i, (t, v) in enumerate(zip(hours, d.hourly)):
        gv = g[i] if g else 0.0
        out.append((t.astimezone(tz).hour, max(v - gv, 0.0) * factor))
    return out


def detect_leak(
    daily: Mapping[date, DailyConsumption],
    unit: str,
    today: date,
    tz: tzinfo,
    garden: Mapping[date, DailyConsumption] | None = None,
    threshold_lph: float | None = None,
) -> LeakResult:
    thr = threshold_lph if threshold_lph is not None else DEFAULT_THRESHOLD_LPH
    f = _to_litres(unit)
    res = LeakResult()
    days = [today - timedelta(days=i) for i in range(1, max(NIGHTS, CONTINUOUS_DAYS) + 1)]  # gestern zuerst
    series = {d: _hours_l(d, daily.get(d), (garden or {}).get(d), f, tz, garden is not None) for d in days}
    res.checked_days = sum(1 for v in series.values() if v is not None)
    nights = []
    for d in days[:NIGHTS]:
        hrs = series[d]
        if hrs is None:
            break
        night = [v for h, v in hrs if h in NIGHT_HOURS]
        if not night:
            break
        nights.append((d, min(night)))
    if len(nights) == NIGHTS and all(v > thr for _, v in nights):
        return LeakResult(True, "nachtminimum", sorted(d for d, _ in nights), min(v for _, v in nights), res.checked_days)
    cont = []
    for d in days[:CONTINUOUS_DAYS]:
        hrs = series[d]
        if hrs is None or any(v < CONTINUOUS_MIN_LPH for _, v in hrs):
            break
        cont.append(d)
    if len(cont) == CONTINUOUS_DAYS:
        night_min = min((min((v for h, v in series[d] if h in NIGHT_HOURS), default=0.0) for d in cont), default=None)
        return LeakResult(True, "dauerfluss", sorted(cont), night_min, res.checked_days)
    return res
