"""Abgleich eines Zähler-Sensors (Zählerstand oder Impulse) mit den Ablesungen (Arbeitspaket 2a).

Für jedes Intervall zwischen zwei gültigen Ablesungen: abgelesene Menge ΔA gegen die vom Sensor gemessene Menge ΔS.
- Faktor = ΔA / ΔS, Abweichung = (ΔS / ΔA − 1) × 100 %. ΔS < ΔA heißt: Impulse verloren.
- Die Ablesung gilt (Entscheidung von Daniel, 0.9): Tageswerte im Intervall werden mit dem Faktor angeglichen, als
  geschätzt markiert (Flag ``abgeglichen``); der Rohwert bleibt erhalten (``raw_consumption``), damit der Abgleich bei
  jeder neuen Ablesung neu und umkehrbar gerechnet werden kann.
- Fehlende Tage bleiben fehlend (Regel 5). Decken die vorhandenen Tage weniger als 80 % des Intervalls ab, wird nicht
  angeglichen (Flag ``abgleich_luecken``).
- Abweichungen über 30 % gelten als Fehler (falsche Ablesung, Zählertausch, falsche Impulskonstante): nicht angleichen,
  nur melden.
- Nach der letzten Ablesung: Offset = Ablesung − Sensorstand zum Ablesezeitpunkt (wie eine "Referenz" bei jeder Ablesung).
  Ist die letzte Ablesung ein Ausreißer, gilt der Offset der letzten plausiblen Ablesung.
- Nur echte Ablesungen (Qualität "real") zählen; Schätzungen (z. B. vom Versorger) gleichen nichts an.
- Zählertausch: Sensorstände werden wie die Ablesungen über den Tausch durchlaufend gerechnet.

Ein Tag gehört zu dem Intervall, das seine Tagesmitte (12 Uhr) enthält.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, tzinfo
from statistics import median

from .consumption import _offset_on, continuous_value, day_bounds, valid_readings
from .model import DailyConsumption, Meter, Reading
from .quality import Quality, usable

NOTICE_PCT = 2.0
OUTLIER_PCT = 30.0
MIN_COVERAGE = 0.8


@dataclass(slots=True)
class Interval:
    start: datetime
    end: datetime
    read: float  # abgelesene Menge
    measured: float | None  # vom Sensor gemessen
    factor: float | None = None
    deviation_pct: float | None = None
    missing: float | None = None  # abgelesen − gemessen (positiv: verlorene Impulse)
    applied: bool = False
    flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Reconciliation:
    intervals: list[Interval] = field(default_factory=list)
    offset: float | None = None  # Ablesung − Sensorstand (durchlaufend) bei der letzten plausiblen Ablesung
    offset_day: date | None = None
    last_reading: Reading | None = None
    factor_median: float | None = None
    flags: list[str] = field(default_factory=list)

    @property
    def last(self) -> Interval | None:
        """Letztes auswertbares Intervall (für Sensor und Hinweis)."""
        ok = [i for i in self.intervals if i.deviation_pct is not None]
        return ok[-1] if ok else None

    @property
    def notice(self) -> bool:
        last = self.last
        return last is not None and abs(last.deviation_pct or 0.0) >= NOTICE_PCT


def sensor_value_at(daily: Mapping[date, DailyConsumption], t: datetime, tz: tzinfo) -> float | None:
    """Sensorstand (Rohwert) zum Zeitpunkt t aus den Tageswerten: Stand am Ende des Vortags + Anteil des Tages."""
    local = t.astimezone(tz)
    d = local.date()
    prev = daily.get(d - timedelta(days=1))
    if prev is None or prev.end_value is None:
        return None
    a, b = day_bounds(d, tz)
    frac = (t - a).total_seconds() / (b - a).total_seconds()
    if frac <= 1e-9:
        return prev.end_value
    cur = daily.get(d)
    if cur is None:
        return None
    raw = cur.raw_consumption if cur.raw_consumption is not None else cur.consumption
    if cur.end_value is not None and frac >= 1 - 1e-9:
        return cur.end_value
    if raw is None:
        return None
    return prev.end_value + raw * frac


def _sensor_cont(meter: Meter, r: Reading, daily: Mapping[date, DailyConsumption], tz: tzinfo) -> float | None:
    """Sensorstand zum Ablesezeitpunkt, über Zählertausche durchlaufend (wie ``continuous_value`` der Ablesung)."""
    s = r.sensor_value if r.sensor_value is not None else sensor_value_at(daily, r.timestamp, tz)
    return None if s is None else s + _offset_on(meter, r.timestamp.astimezone(tz).date())


def reconcile(meter: Meter, readings: Iterable[Reading], daily: Mapping[date, DailyConsumption], tz: tzinfo) -> Reconciliation:
    rec = Reconciliation()
    rs = [r for r in valid_readings(readings, meter.meter_id) if r.quality == Quality.REAL]
    if not rs:
        return rec
    rec.last_reading = rs[-1]
    for a, b in zip(rs, rs[1:]):
        read = continuous_value(meter, b, tz) - continuous_value(meter, a, tz)
        sa = _sensor_cont(meter, a, daily, tz)
        sb = _sensor_cont(meter, b, daily, tz)
        iv = Interval(a.timestamp, b.timestamp, round(read, 6), None)
        if sa is not None and sb is not None:
            iv.measured = round(sb - sa, 6)
        if iv.measured is None or iv.measured <= 0 or read <= 0:
            iv.flags.append("nicht_auswertbar")
            rec.intervals.append(iv)
            continue
        iv.factor = read / iv.measured
        iv.deviation_pct = round((iv.measured / read - 1) * 100, 2)
        iv.missing = round(read - iv.measured, 6)
        if abs(iv.deviation_pct) > OUTLIER_PCT:
            iv.flags.append("ausreisser")
        else:
            # schon angeglichen (gespeicherte Tageswerte tragen das Kennzeichen)?
            d, last = a.timestamp.astimezone(tz).date(), b.timestamp.astimezone(tz).date()
            while d <= last:
                v = daily.get(d)
                if v is not None and "abgeglichen" in v.quality_flags and a.timestamp <= _noon(d, tz) < b.timestamp:
                    iv.applied = True
                    break
                d += timedelta(days=1)
        rec.intervals.append(iv)
    factors = [i.factor for i in rec.intervals if i.factor is not None and "ausreisser" not in i.flags]
    rec.factor_median = round(median(factors), 6) if factors else None
    # Offset: jüngste Ablesung mit bekanntem Sensorstand, die kein Ausreißer ist (Ausreißer = Ende eines Ausreißer-Intervalls)
    bad = {i.end for i in rec.intervals if "ausreisser" in i.flags}
    for r in reversed(rs):
        if r.timestamp in bad:
            rec.flags.append("offset_aus_frueherer_ablesung")
            continue
        s = _sensor_cont(meter, r, daily, tz)
        if s is not None:
            rec.offset = round(continuous_value(meter, r, tz) - s, 6)
            rec.offset_day = r.timestamp.astimezone(tz).date()
            break
    if rec.notice:
        rec.flags.append("abweichung")
    return rec


def _noon(d: date, tz: tzinfo) -> datetime:
    return datetime.combine(d, time(12), tzinfo=tz)


def apply_reconciliation(daily: Mapping[date, DailyConsumption], rec: Reconciliation, tz: tzinfo) -> list[DailyConsumption]:
    """Tageswerte angleichen (bzw. auf den Rohwert zurücksetzen). Liefert nur die geänderten Tage."""
    changed: list[DailyConsumption] = []
    target: dict[date, tuple[float, Interval]] = {}
    for iv in rec.intervals:
        if iv.factor is None or "ausreisser" in iv.flags:
            continue
        days = []
        d = iv.start.astimezone(tz).date()
        last = iv.end.astimezone(tz).date()
        while d <= last:
            if iv.start <= _noon(d, tz) < iv.end:
                days.append(d)
            d += timedelta(days=1)
        if not days:
            continue
        present = [d for d in days if d in daily and (daily[d].raw_consumption is not None or daily[d].consumption is not None)
                   and (usable(daily[d].quality) or "abgeglichen" in daily[d].quality_flags)]
        if len(present) < MIN_COVERAGE * len(days):
            iv.flags.append("abgleich_luecken")
            iv.applied = False
            continue
        iv.applied = True
        for d in present:
            target[d] = (iv.factor, iv)
    for d, v in daily.items():
        raw = v.raw_consumption if v.raw_consumption is not None else v.consumption
        if d in target:
            f, _ = target[d]
            orig_q = v.raw_quality if "abgeglichen" in v.quality_flags and v.raw_quality is not None else v.quality
            if abs(f - 1.0) < 1e-9:
                new = replace(v, consumption=raw, raw_consumption=None, raw_quality=None, quality=orig_q,
                              quality_flags=[x for x in v.quality_flags if x != "abgeglichen"])
            else:
                flags = [x for x in v.quality_flags if x != "abgeglichen"] + ["abgeglichen"]
                new = replace(v, consumption=round(raw * f, 6), raw_consumption=raw, raw_quality=orig_q, quality=Quality.ESTIMATED,
                              quality_flags=flags)
        elif "abgeglichen" in v.quality_flags:
            # nicht mehr in einem angeglichenen Intervall (z. B. Ablesung ungültig): Rohwert und ursprüngliche Qualität zurück
            new = replace(v, consumption=raw, raw_consumption=None, quality=v.raw_quality or Quality.REAL, raw_quality=None,
                          quality_flags=[x for x in v.quality_flags if x != "abgeglichen"])
        else:
            continue
        if new != v:
            changed.append(new)
    return changed
