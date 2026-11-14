"""Synthetische Tageswerte für die Heizungs-Szenarien (0.8): Temperaturjahr, Kennwert, Warmwasser, Ofen- und Klimatage.

Alles deterministisch (kein Zufall): "Rauschen" ist ein fester Wechsel ±noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import math

from engine.degree_days import degree_days
from engine.model import DailyConsumption
from engine.quality import Quality


def outdoor(d: date) -> float:
    """Jahresgang: Mitte Januar ca. 0 °C, Mitte Juli ca. 18 °C, mit kleinem Wochenwechsel."""
    doy = d.timetuple().tm_yday
    return 9.0 - 9.0 * math.cos(2 * math.pi * (doy - 20) / 365.0) + 1.5 * math.sin(doy * 0.9)


@dataclass
class Synth:
    daily: dict[date, DailyConsumption] = field(default_factory=dict)
    stove_hours: dict[date, float] = field(default_factory=dict)
    hp_energy: dict[date, float] = field(default_factory=dict)


def heat_year(
    meter_id: str,
    start: date,
    days: int,
    k: float = 6.0,
    ww: float = 8.0,
    noise: float = 0.0,
    stove_every: int = 0,
    stove_hours: float = 4.0,
    stove_effect: float = 7.0,
    hp_every: int = 0,
    hp_kwh_per_dd: float = 0.6,
    hp_avoided: float = 2.5,
    indoor: float | None = None,
    indoor_swing: float = 0.0,
    baseload_only: float | None = None,
) -> Synth:
    """Gas-/Wärmezähler (oder mit ``baseload_only`` Strom: Grundlast + k × Gradtage).

    Ofen an jedem ``stove_every``-ten Heiztag, Klima an jedem ``hp_every``-ten Heiztag. Mit ``indoor`` folgt der Verbrauch
    der gemessenen Innentemperatur (Gradtage innen statt 20 °C)."""
    out = Synth()
    heat_day = 0
    for i in range(days):
        d = start + timedelta(days=i)
        t = outdoor(d)
        dd = degree_days(t) or 0.0
        t_in = None
        dd_use = dd
        if indoor is not None:
            t_in = indoor + (indoor_swing if (i // 30) % 2 else -indoor_swing)
            dd_use = max(t_in - t, 0.0) if dd > 0 else 0.0
        if baseload_only is not None:
            v = baseload_only + k * dd
        else:
            v = ww + k * dd_use
        if dd > 0:
            heat_day += 1
            # bekannt "aus" ist 0, nicht fehlend (wie Betriebsstunden aus einer Betriebszustand-Entität)
            if stove_every:
                out.stove_hours[d] = 0.0
            if hp_every:
                out.hp_energy[d] = 0.0
            if stove_every and heat_day % stove_every == 0:
                out.stove_hours[d] = stove_hours
                v -= stove_effect * stove_hours
            if hp_every and heat_day % hp_every == 0:
                e = hp_kwh_per_dd * dd
                out.hp_energy[d] = e
                v -= hp_avoided * e
        v += noise if i % 2 else -noise
        out.daily[d] = DailyConsumption(meter_id, d, max(v, 0.0), degree_days=dd, outdoor_temperature=t,
                                        indoor_temperature=t_in, quality=Quality.REAL)
    return out
