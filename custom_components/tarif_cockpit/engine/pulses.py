"""Impulszähler (Arbeitspaket 2a): Impulse → Zählereinheit, Zählerrücksetzer überbrücken.

Ein Impulszähler liefert eine laufende Zahl von Impulsen (z. B. ESPHome ``pulse_counter`` total, Reed-Kontakt am Gaszähler).
Die Impulskonstante steht auf dem Zähler: entweder Impulse je Einheit (z. B. 100 Imp/m³) oder Einheit je Impuls
(z. B. 0,01 m³/Imp).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime


def unit_per_pulse(constant: float | None, mode: str = "per_unit") -> float | None:
    """Menge je Impuls. ``mode``: per_unit (Impulse je Einheit) oder per_pulse (Einheit je Impuls)."""
    if not constant or constant <= 0:
        return None
    return 1.0 / constant if mode == "per_unit" else constant


def scale(series: Mapping[datetime, float], k: float) -> dict[datetime, float]:
    return {t: v * k for t, v in series.items()}


def bridge_resets(series: Mapping[datetime, float]) -> tuple[dict[datetime, float], list[datetime]]:
    """Laufende Zählerstände ohne Rücksprünge: fällt der Rohwert (Neustart des Zählers bei 0), zählen die neuen
    Impulse ab dem letzten Stand weiter. Liefert die Reihe und die Zeitpunkte der Rücksetzer (zum Kennzeichnen)."""
    out: dict[datetime, float] = {}
    resets: list[datetime] = []
    offset = 0.0
    prev_raw: float | None = None
    for t in sorted(series):
        v = series[t]
        if prev_raw is not None and v < prev_raw - 1e-9:
            offset += prev_raw  # der Zähler begann wieder bei 0
            resets.append(t)
        out[t] = v + offset
        prev_raw = v
    return out, resets



def detect_resets(raw: Mapping[datetime, float], last_raw: float | None = None, eps: float = 1e-9) -> list[tuple[datetime, float]]:
    """Neustarts in einer Rohreihe (Einheit): Zeitpunkt und Stand davor. ``last_raw``: letzter bekannter Stand vor der Reihe."""
    out: list[tuple[datetime, float]] = []
    prev = last_raw
    for t in sorted(raw):
        v = raw[t]
        if prev is not None and v < prev - eps:
            out.append((t, prev))
        prev = v
    return out


def offset_at(resets: Iterable[tuple[datetime, float]], t: datetime) -> float:
    """Summe der Stände vor allen Neustarts bis einschließlich ``t`` (der Zähler begann jeweils wieder bei 0)."""
    return sum(prev for at, prev in resets if at <= t)


def apply_resets(raw: Mapping[datetime, float], resets: Iterable[tuple[datetime, float]]) -> dict[datetime, float]:
    resets = list(resets)
    return {t: v + offset_at(resets, t) for t, v in raw.items()}
