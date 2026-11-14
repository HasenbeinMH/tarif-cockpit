"""Bereich Verbrauch: Tageswerte mit Qualitätsflags (Arbeitspaket 2a, Entscheidung E).

Zwei Wege zum Tageswert:
- ``aggregate_day``: aus Stundenwerten der Langzeitstatistik (Zählerstand als laufende Summe, Temperatur als Mittel)
- ``daily_from_readings``: aus Ablesungen von Hand, linear verteilt (Qualität "interpolated")

Grundsätze: Fehlende Daten sind ``None`` mit Qualität "missing", nie 0 (Regel 5). Ein Zählertausch wird
über alten Endstand und neuen Startstand überbrückt. Verbrauch bleibt in der Zählereinheit.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from .degree_days import degree_days
from .model import DailyConsumption, Meter, Reading
from .quality import Quality, usable

# Mindestanteil vorhandener Stunden für ein Temperatur-Tagesmittel
MIN_TEMP_HOURS_SHARE = 0.75


def day_bounds(day: date, tz: tzinfo) -> tuple[datetime, datetime]:
    """Beginn und Ende eines lokalen Kalendertags (Ende exklusiv) in UTC.

    In UTC, weil Python bei gleicher Zeitzone mit Wanduhrzeit rechnet: 23- und 25-Stunden-Tage der
    Zeitumstellung kämen sonst als 24 Stunden heraus.
    """
    start = datetime.combine(day, time(0), tzinfo=tz).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz).astimezone(UTC)
    return start, end


def _floor_hour(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def hours_of_day(day: date, tz: tzinfo) -> int:
    """Anzahl Stunden des lokalen Tags: 23 oder 25 an den Tagen der Zeitumstellung."""
    start, end = day_bounds(day, tz)
    return int((end - start).total_seconds() // 3600)


def aggregate_day(
    meter_id: str,
    day: date,
    tz: tzinfo,
    sums: Mapping[datetime, float],
    outdoor: Mapping[datetime, float] | None = None,
    indoor: Iterable[Mapping[datetime, float]] = (),
    heating_limit: float = 15.0,
    indoor_ref: float = 20.0,
    states: Mapping[datetime, float] | None = None,
) -> DailyConsumption:
    """Tageswert aus Stundenwerten.

    ``states``: optional der Zählerstand am Ende jeder Stunde; daraus wird ``end_value`` (Stand am Tagesende).

    ``sums``: Zählerstand als laufende Summe am Ende jeder Stunde, Schlüssel = Stundenbeginn (aware).
    Verbrauch = Summe am Ende des Tages − Summe am Ende des Vortags. Fehlt einer der beiden Randwerte,
    fehlt der Tag ("missing"). Lücken innerhalb des Tags schaden nicht, weil die Summe durchläuft.
    ``outdoor``/``indoor``: Stundenmittel der Temperaturen. Unter 75 % vorhandener Stunden kein Tagesmittel.
    """
    start, end = day_bounds(day, tz)
    flags: list[str] = []
    # Die Statistik hat volle UTC-Stunden. In Zeitzonen mit halber oder Viertelstunde Versatz (z. B. Indien)
    # liegt Mitternacht nicht auf diesem Raster: Dann gilt die letzte volle Stunde vor Mitternacht als Tagesgrenze.
    off_grid = start != _floor_hour(start) or end != _floor_hour(end)
    last_hour = _floor_hour(end) - timedelta(hours=1)
    prev_last = _floor_hour(start) - timedelta(hours=1)
    norm = {k.astimezone(UTC): v for k, v in sums.items()}
    s_end, s_prev = norm.get(last_hour), norm.get(prev_last)
    end_value = {k.astimezone(UTC): v for k, v in (states or {}).items()}.get(last_hour)
    consumption: float | None = None
    quality = Quality.MISSING
    if s_end is not None and s_prev is not None:
        consumption = round(s_end - s_prev, 6)
        quality = Quality.ESTIMATED if off_grid else Quality.REAL
        if off_grid:
            flags.append("tagesgrenze_verschoben")
        if consumption < 0:
            # Zählerstand rückwärts ohne erfassten Zählertausch: nicht verwenden
            consumption, quality = None, Quality.INVALID
            flags.append("rueckwaerts")
    else:
        flags.append("randwert_fehlt")

    n_hours = hours_of_day(day, tz)

    def mean(series: Mapping[datetime, float] | None, name: str) -> float | None:
        if not series:
            return None
        vals = [v for k, v in series.items() if start <= k.astimezone(UTC) < end and v is not None]
        if len(vals) < n_hours * MIN_TEMP_HOURS_SHARE:
            flags.append(f"{name}_unvollstaendig")
            return None
        if len(vals) < n_hours:
            flags.append(f"{name}_luecken")
        return round(sum(vals) / len(vals), 3)

    t_out = mean(outdoor, "aussen")
    indoor_means = [m for m in (mean(s, "innen") for s in indoor) if m is not None]
    t_in = round(sum(indoor_means) / len(indoor_means), 3) if indoor_means else None
    return DailyConsumption(
        meter_id=meter_id,
        date=day,
        consumption=consumption,
        end_value=end_value,
        degree_days=degree_days(t_out, heating_limit, indoor_ref),
        outdoor_temperature=t_out,
        indoor_temperature=t_in,
        quality=quality,
        quality_flags=flags,
        source="statistics",
    )


def valid_readings(readings: Iterable[Reading], meter_id: str) -> list[Reading]:
    """Verwendbare Ablesungen eines Zählers, zeitlich sortiert (ungültige und ersetzte fallen weg)."""
    out = [r for r in readings if r.meter_id == meter_id and usable(r.quality) and not r.superseded_by]
    return sorted(out, key=lambda r: r.timestamp)


def continuous_value(meter: Meter, reading: Reading, tz: tzinfo) -> float:
    """Zählerstand als durchlaufender Wert über Zählertausche hinweg.

    Ablesungen ab dem Tag des Tauschs (lokal) gehören zum neuen Zähler: Ihr Wert wird um
    (alter Endstand − neuer Startstand) erhöht.
    """
    day = reading.timestamp.astimezone(tz).date()
    offset = sum(rep.old_end - rep.new_start for rep in meter.replacements if rep.date <= day)
    return reading.value + offset


def daily_from_readings(meter: Meter, readings: Iterable[Reading], first: date, last: date, tz: tzinfo) -> list[DailyConsumption]:
    """Tageswerte von ``first`` bis ``last`` (einschließlich) aus Ablesungen, linear verteilt.

    Zwischen zwei gültigen Ablesungen steigt der Stand gleichmäßig. Ein Tag bekommt einen Wert, wenn er
    vollständig zwischen der ersten und der letzten Ablesung liegt; fällt eine Ablesung in den Tag, setzt sich
    sein Wert aus beiden Abschnitten zusammen. Sonst ist der Tag "missing". Fällt der Stand in einem
    Abschnitt, der den Tag berührt, ist der Tag "invalid".
    """
    rs = valid_readings(readings, meter.meter_id)
    points: list[tuple[datetime, float]] = []
    for r in rs:
        t, v = r.timestamp.astimezone(UTC), continuous_value(meter, r, tz)
        if points and points[-1][0] == t:
            points[-1] = (t, v)  # gleicher Zeitpunkt: die spätere Ablesung gilt
        else:
            points.append((t, v))

    def value_at(t: datetime) -> float:
        for (t0, v0), (t1, v1) in zip(points, points[1:]):
            if t0 <= t <= t1:
                return v0 + (v1 - v0) * (t - t0).total_seconds() / (t1 - t0).total_seconds()
        raise ValueError(t)

    out: list[DailyConsumption] = []
    day = first
    while day <= last:
        start, end = day_bounds(day, tz)
        value: float | None = None
        quality = Quality.MISSING
        flags: list[str] = []
        if len(points) >= 2 and points[0][0] <= start and end <= points[-1][0]:
            touching = [(a, b) for a, b in zip(points, points[1:]) if a[0] < end and b[0] > start]
            if any(b[1] < a[1] for a, b in touching):
                quality = Quality.INVALID
                flags.append("rueckwaerts")
            else:
                value = round(value_at(end) - value_at(start), 6)
                quality = Quality.INTERPOLATED
                if len(touching) > 1:
                    flags.append("ablesung_im_tag")
        else:
            flags.append("keine_umschliessenden_ablesungen")
        out.append(
            DailyConsumption(
                meter_id=meter.meter_id, date=day, consumption=value, quality=quality, quality_flags=flags, source="readings"
            )
        )
        day += timedelta(days=1)
    return out


def latest_reading(readings: Iterable[Reading], meter_id: str) -> Reading | None:
    rs = valid_readings(readings, meter_id)
    return rs[-1] if rs else None


# ---------------------------------------------------------------- Verbrauch der laufenden Periode (0.6)


@dataclass(slots=True)
class ConsumptionState:
    """Verbrauch seit Periodenbeginn bis ``known_until`` in der Zählereinheit."""

    start_value: float | None = None
    start_source: str | None = None  # reading | daily_end_value
    known_until: datetime | None = None  # bei Zählern mit Sensor: jetzt; sonst Zeitpunkt der letzten Ablesung
    used: float | None = None
    quality: Quality = Quality.MISSING
    flags: list[str] = field(default_factory=list)


def _offset_on(meter: Meter, day: date) -> float:
    return sum(rep.old_end - rep.new_start for rep in meter.replacements if rep.date <= day)


def value_at(meter: Meter, readings: Iterable[Reading], t: datetime, tz: tzinfo, tolerance: timedelta = timedelta(hours=24)) -> float | None:
    """Durchlaufender Zählerstand zum Zeitpunkt t: zwischen zwei Ablesungen linear, sonst die nächste Ablesung
    innerhalb ``tolerance``. None, wenn keine passende Ablesung da ist."""
    rs = valid_readings(readings, meter.meter_id)
    pts = [(r.timestamp.astimezone(UTC), continuous_value(meter, r, tz)) for r in rs]
    t = t.astimezone(UTC)
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0).total_seconds() / (t1 - t0).total_seconds()
    near = [(abs((tp - t).total_seconds()), v) for tp, v in pts if abs(tp - t) <= tolerance]
    return min(near)[1] if near else None


def calculate_consumption(
    meter: Meter,
    readings: Iterable[Reading],
    daily: Mapping[date, DailyConsumption],
    period_start: date,
    tz: tzinfo,
    current: tuple[datetime, float] | None,
    sensor_offset: float | None = None,
) -> ConsumptionState:
    """Verbrauch seit Periodenbeginn.

    ``sensor_offset`` (Abgleich, 0.9): Ablesung − Sensorstand bei der letzten Ablesung. Kommt der Startwert aus einer
    Ablesung, wird der Sensorstand damit auf die Ablesungen bezogen (wie eine Referenz bei jeder Ablesung).

    Startwert: Ablesung zum Periodenbeginn (bzw. linear dazwischen), sonst Zählerstand am Ende des Vortags aus
    den Tageswerten. Endwert: ``current`` (Zählerstand jetzt, in der Zählereinheit) oder die letzte Ablesung.
    """
    readings = list(readings)
    st = ConsumptionState()
    t0 = day_bounds(period_start, tz)[0]
    start = value_at(meter, readings, t0, tz)
    if start is not None:
        st.start_value, st.start_source = start, "reading"
    else:
        prev = daily.get(period_start - timedelta(days=1))
        if prev is not None and prev.end_value is not None:
            st.start_value = prev.end_value + _offset_on(meter, period_start - timedelta(days=1))
            st.start_source = "daily_end_value"
            st.flags.append("startwert_aus_statistik")
    if current is None and meter.entity:
        # Zähler mit Sensor, aber Sensor gerade nicht verfügbar: nicht still auf eine alte Ablesung zurückfallen
        st.flags.append("sensor_nicht_verfuegbar")
        return st
    if current is not None:
        when, raw = current
        end_value = raw + _offset_on(meter, when.astimezone(tz).date())
        if sensor_offset is not None and st.start_source == "reading":
            # Sensor durchlaufend (Tauschoffset) + Abgleich-Offset der letzten Ablesung
            end_value = raw + _offset_on(meter, when.astimezone(tz).date()) + sensor_offset
            st.flags.append("abgleich_offset")
        st.known_until = when
        quality = Quality.REAL
    else:
        last = latest_reading(readings, meter.meter_id)
        if last is None or last.timestamp.astimezone(tz).date() < period_start:
            st.flags.append("keine_ablesung_in_periode")
            return st
        end_value = continuous_value(meter, last, tz)
        st.known_until = last.timestamp
        quality = Quality(last.quality) if last.quality != Quality.REAL else Quality.REAL
    if st.start_value is None:
        st.flags.append("kein_startwert")
        return st
    used = end_value - st.start_value
    if used < 0:
        st.quality = Quality.INVALID
        st.flags.append("rueckwaerts")
        return st
    st.used = round(used, 6)
    st.quality = quality
    return st


@dataclass(slots=True)
class WindowSum:
    """Summe der Tageswerte in einem Zeitfenster, mit Abdeckung."""

    total: float | None
    days: int
    covered: int
    scaled: bool = False

    @property
    def coverage(self) -> float:
        return self.covered / self.days if self.days else 0.0


def window_sum(values: Mapping[date, float | None], first: date, last: date, min_coverage: float = 0.8) -> WindowSum:
    """Summe von ``first`` bis ``last`` (einschließlich). Fehlende Tage werden bei ausreichender Abdeckung auf die
    volle Tageszahl hochgerechnet (``scaled``); darunter ist die Summe None (fehlend, nicht 0)."""
    if last < first:
        return WindowSum(0.0, 0, 0)
    n = (last - first).days + 1
    vals = [values.get(first + timedelta(days=i)) for i in range(n)]
    got = [v for v in vals if v is not None]
    if not got or len(got) / n < min_coverage:
        return WindowSum(None, n, len(got))
    total = sum(got)
    scaled = len(got) < n
    if scaled:
        total = total * n / len(got)
    return WindowSum(round(total, 6), n, len(got), scaled)
