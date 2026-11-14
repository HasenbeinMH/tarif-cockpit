"""Gas mit Impulsen (Arbeitspaket 2a): Momentanleistung, Brennerlaufzeit, Starts und Takten.

Eingang sind die Zählerstand-Wechsel des Impulszählers (Zeitpunkt, Stand in der Zählereinheit, z. B. m³).
- Leistung zwischen zwei Impulsen: Δm³ / Δt × Brennwert × Zustandszahl (kWh je m³) = kW.
- ``max_gap``: längster Impulsabstand, bei dem der Brenner noch als durchgehend an gilt. Ergibt sich aus der Menge je
  Impuls und der kleinsten Leistung (1,5 × Impulsabstand bei kleinster Leistung, mindestens 6 Minuten).
- Ein Impuls nach einer Pause (Abstand > ``max_gap``) ist ein Start. Ein Lauf aus nur einem Impuls zählt als Start mit der
  Laufzeit eines Impulses bei kleinster Leistung (Schätzung).
- Laufzeit: Abschnitte zwischen Impulsen mit Abstand ≤ ``max_gap``, an Tagesgrenzen geteilt.
- Takten: mittlere Leistung im Betrieb höchstens 120 % der kleinsten Modulationsleistung und mehr als 3 Starts je
  Betriebsstunde, bei mindestens 30 Minuten Betrieb (Startwerte, im Test justierbar).
- Fehlende Daten sind nicht 0 (Regel 5): ohne Impulse, obwohl der Tag Verbrauch hat, bleiben die Werte leer (``None``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

MIN_GAP = timedelta(minutes=6)
DEFAULT_MIN_POWER_KW = 3.0
CYCLING_STARTS_PER_HOUR = 3.0
CYCLING_POWER_RATIO = 1.2
MIN_RUNTIME_H = 0.5


@dataclass(slots=True)
class BurnerDay:
    hours: float | None = None
    starts: int | None = None
    mean_power_kw: float | None = None
    energy_kwh: float | None = None
    cycling: bool | None = None
    flags: list[str] = field(default_factory=list)


def max_gap_for(unit_per_pulse: float | None, kwh_per_unit: float, min_power_kw: float | None) -> timedelta:
    """Längster Impulsabstand im Betrieb: 1,5 × Abstand zweier Impulse bei kleinster Leistung (mindestens 6 min)."""
    if not unit_per_pulse or not kwh_per_unit:
        return MIN_GAP
    p = min_power_kw or DEFAULT_MIN_POWER_KW
    interval_h = unit_per_pulse * kwh_per_unit / p
    return max(MIN_GAP, timedelta(hours=1.5 * interval_h))


def burner_day(changes: list[tuple[datetime, float]], start: datetime, end: datetime, kwh_per_unit: float,
               min_power_kw: float | None = None, max_gap: timedelta = MIN_GAP, unit_per_pulse: float | None = None) -> BurnerDay:
    """Auswertung eines Tages aus Zählerstand-Wechseln (Stand in der Zählereinheit, z. B. m³)."""
    pts = sorted((t, v) for t, v in changes if start - max_gap <= t < end + max_gap)
    res = BurnerDay()
    if not any(start <= t < end for t, _ in pts):
        res.hours, res.starts, res.flags = 0.0, 0, ["keine_impulse"]
        return res
    ref_power = min_power_kw or DEFAULT_MIN_POWER_KW
    on = 0.0
    energy = 0.0
    starts = 0
    prev: tuple[datetime, float] | None = None
    for i, (t, v) in enumerate(pts):
        if prev is None:
            prev = (t, v)
            continue
        t0, v0 = prev
        prev = (t, v)
        dv = v - v0
        if dv < 0:
            res.flags.append("ruecksprung")
            continue
        if dv == 0:
            continue
        a, b = max(t0, start), min(t, end)
        if t - t0 <= max_gap:
            if b > a:
                frac = (b - a) / (t - t0)
                on += (b - a).total_seconds() / 3600
                energy += dv * kwh_per_unit * frac
            # Start: erster Abschnitt nach einer Pause (vor t0 kam länger als max_gap kein Impuls)
            before = pts[i - 2] if i >= 2 else None
            if (before is None or t0 - before[0] > max_gap) and start <= t0 < end:
                starts += 1
        elif start <= t < end:
            # Impuls nach einer Pause: ein Start; folgt kein weiterer Impuls, ist es ein Lauf aus einem Impuls
            nxt = pts[i + 1] if i + 1 < len(pts) else None
            if nxt is None or nxt[0] - t > max_gap:
                starts += 1
                if unit_per_pulse:
                    on += unit_per_pulse * kwh_per_unit / ref_power
                energy += dv * kwh_per_unit
    res.hours = round(on, 3)
    res.starts = starts
    res.energy_kwh = round(energy, 3)
    res.mean_power_kw = round(energy / on, 3) if on > 0 else None
    if min_power_kw and res.mean_power_kw is not None and on >= MIN_RUNTIME_H:
        res.cycling = starts / on > CYCLING_STARTS_PER_HOUR and res.mean_power_kw <= min_power_kw * CYCLING_POWER_RATIO
    return res


def current_power(changes: list[tuple[datetime, float]], now: datetime, kwh_per_unit: float, max_gap: timedelta = MIN_GAP) -> float | None:
    """Momentanleistung in kW aus den letzten beiden Zählerstand-Wechseln; 0, wenn seit ``max_gap`` kein Impuls kam."""
    pts = sorted(changes)
    if not pts:
        return None
    if now - pts[-1][0] > max_gap:
        return 0.0
    if len(pts) < 2:
        return None
    (t0, v0), (t1, v1) = pts[-2], pts[-1]
    dt = (t1 - t0).total_seconds() / 3600
    if dt <= 0 or v1 < v0 or (t1 - t0) > max_gap:
        return None
    return round((v1 - v0) / dt * kwh_per_unit, 3)
