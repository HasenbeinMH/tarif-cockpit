"""Zeitfenster, Stunden- und Viertelstundenwerte (1.2): HT/NT, § 14a Modul 3, dynamischer Tarif.

Ein Tagesverbrauch wird in Zeitscheiben zerlegt:
1. Viertelstunden (aus der 5-Minuten-Statistik), wenn vollständig vorhanden,
2. sonst Stunden (``DailyConsumption.hourly``),
3. sonst ein typisches Tagesprofil (Anteile je Stunde aus den letzten 30 Tagen) – Kennzeichen ``fenster_geschaetzt``,
4. ohne Profil gleichmäßig über den Tag.
Die Scheiben werden immer auf den Tageswert skaliert (der Tageswert bleibt maßgeblich, z. B. nach dem Abgleich).

Preis einer Scheibe (``price_at``): absoluter Fensterpreis, sonst der dynamische Preis (+ Aufschlag), sonst der
Arbeitspreis des Abschnitts; dazu die Deltas aller passenden Fenster (§ 14a Modul 3). Maßgeblich ist der Beginn der
Scheibe in Ortszeit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from functools import lru_cache

from .model import PriceSegment, PriceWindow

DEFAULT = "standard"


def _minutes(hhmm: str) -> int:
    h, m = (hhmm or "0:0").split(":")
    return int(h) * 60 + int(m)


def window_matches(w: PriceWindow, local: datetime) -> bool:
    if w.weekdays and local.weekday() not in w.weekdays:
        return False
    if w.months and local.month not in w.months:
        return False
    m = local.hour * 60 + local.minute
    a, b = _minutes(w.start), _minutes(w.end)
    if a == b:
        return True  # ganzer Tag
    return a <= m < b if a < b else (m >= a or m < b)  # über Mitternacht


def price_at(seg: PriceSegment, local: datetime, dynamic_price: float | None = None) -> tuple[float | None, str]:
    """(Preis je Abrechnungseinheit, Name des Fensters) am Beginn einer Scheibe. None, wenn ein dynamischer Preis fehlt."""
    name = DEFAULT
    if seg.dynamic is not None:
        base = None if dynamic_price is None else dynamic_price + (seg.dynamic.markup or 0.0)
    else:
        base = seg.work_price
    delta = 0.0
    for w in seg.windows:
        if not window_matches(w, local):
            continue
        if w.work_price is not None:
            base, name = w.work_price, w.name
        if w.delta:
            delta += w.delta
            if name == DEFAULT:
                name = w.name
    return (None if base is None else base + delta), name


@lru_cache(maxsize=8192)
def slot_starts(day: date, tz: tzinfo, minutes: int) -> tuple[datetime, ...]:
    """Beginn jeder Scheibe eines lokalen Tags in UTC (23/25 Stunden an den Tagen der Zeitumstellung). Zwischengespeichert."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(UTC)
    out, t = [], start
    while t < end:
        out.append(t)
        t += timedelta(minutes=minutes)
    return tuple(out)


@lru_cache(maxsize=8192)
def quarter_index(day: date, tz: tzinfo) -> dict[datetime, int]:
    return {t: i for i, t in enumerate(slot_starts(day, tz, 15))}


@lru_cache(maxsize=8192)
def local_starts(day: date, tz: tzinfo, minutes: int) -> tuple[datetime, ...]:
    return tuple(t.astimezone(tz) for t in slot_starts(day, tz, minutes))


@dataclass(slots=True)
class Slots:
    starts: list[datetime]  # UTC
    minutes: int
    qty: list[float]
    source: str  # interval | hour | profil | gleich


def day_slots(
    day: date, q: float, tz: tzinfo,
    hourly: Sequence[float | None] | None = None,
    intervals: Sequence[float | None] | None = None,
    profile: Sequence[float] | None = None,
) -> Slots:
    """Tagesmenge ``q`` auf Zeitscheiben verteilen (Quelle siehe Modulbeschreibung)."""
    quarters = slot_starts(day, tz, 15)
    hours = slot_starts(day, tz, 60)
    if intervals and len(intervals) == len(quarters) and all(v is not None and v >= 0 for v in intervals) and sum(intervals) > 0 \
            and _consistent(intervals, hourly, len(hours)):
        s = sum(intervals)
        return Slots(quarters, 15, [v * q / s for v in intervals], "interval")
    if hourly and len(hourly) == len(hours) and all(v is not None and v >= 0 for v in hourly) and sum(hourly) > 0:
        s = sum(hourly)
        return Slots(hours, 60, [v * q / s for v in hourly], "hour")
    if profile and len(profile) == 24 and sum(profile) > 0:
        w = [profile[h.astimezone(tz).hour] for h in hours]
        s = sum(w)
        if s > 0:
            return Slots(hours, 60, [x * q / s for x in w], "profil")
    return Slots(hours, 60, [q / len(hours)] * len(hours), "gleich")


def _consistent(intervals: Sequence[float], hourly: Sequence[float | None] | None, n_hours: int) -> bool:
    """Viertelstunden passen zu den (sprungbereinigten) Stundenwerten: je Stunde höchstens 5 % bzw. 0,01 Abweichung.
    Ohne Stundenwerte gelten sie."""
    if not hourly or len(hourly) != n_hours or any(v is None for v in hourly):
        return True
    for i, h in enumerate(hourly):
        s = sum(intervals[4 * i:4 * i + 4])
        if abs(s - h) > max(0.01, 0.05 * h):
            return False
    return True


def typical_profile(hourly_days: Sequence[tuple[date, Sequence[float | None]]], tz: tzinfo) -> list[float] | None:
    """Anteile je Stunde des Tages (0–23) aus vollständigen Stundenwerten; None ohne mindestens 7 Tage."""
    sums = [0.0] * 24
    n = 0
    for day, vals in hourly_days:
        hours = slot_starts(day, tz, 60)
        if not vals or len(vals) != len(hours) or any(v is None or v < 0 for v in vals):
            continue
        for h, v in zip(hours, vals):
            sums[h.astimezone(tz).hour] += v
        n += 1
    total = sum(sums)
    if n < 7 or total <= 0:
        return None
    return [x / total for x in sums]


def slot_price(prices: Sequence[float | None] | None, start: datetime, minutes: int, idx: Mapping[datetime, int]) -> float | None:
    """Dynamischer Preis einer Scheibe aus den Viertelstundenpreisen des Tages (``idx`` = ``quarter_index``): bei Stunden
    das Mittel der vier Viertelstunden; fehlt einer, das Mittel der vorhandenen; ganz ohne Preis None."""
    if not prices:
        return None
    i = idx.get(start)
    if i is None or len(prices) != len(idx):
        return None
    vals = [prices[j] for j in range(i, min(i + minutes // 15, len(prices))) if prices[j] is not None]
    return sum(vals) / len(vals) if vals else None


def window_usage(
    days: Mapping[date, float], segs_on: callable, tz: tzinfo,
    hourly: Mapping[date, Sequence[float | None]] | None = None,
    intervals: Mapping[date, Sequence[float | None]] | None = None,
    profile: Sequence[float] | None = None,
) -> tuple[dict[str, float], set[str]]:
    """Menge je Fenstername über mehrere Tage (für Sensor und Karte). ``segs_on(day)`` → Preisabschnitt des Tages."""
    out: dict[str, float] = {}
    sources: set[str] = set()
    for day, q in days.items():
        seg = segs_on(day)
        if seg is None or not seg.windows or not q:
            continue
        sl = day_slots(day, q, tz, (hourly or {}).get(day), (intervals or {}).get(day), profile)
        sources.add(sl.source)
        for t, x in zip(local_starts(day, tz, sl.minutes), sl.qty):
            _, name = price_at(seg, t, 0.0)
            out[name] = out.get(name, 0.0) + x
    return out, sources
