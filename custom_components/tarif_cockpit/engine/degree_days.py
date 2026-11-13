"""Gradtage je Tag (Gradtagzahl G_innen/Heizgrenze, z. B. G20/15).

Ein Tag zählt als Heiztag, wenn sein Tagesmittel unter der Heizgrenze liegt; dann trägt er
``innen − Tagesmittel`` Kelvin·Tage bei, sonst 0. Fehlt die Temperatur, fehlt auch der Gradtag (None, nie 0).
"""

from __future__ import annotations


def degree_days(t_mean: float | None, heating_limit: float = 15.0, indoor_ref: float = 20.0) -> float | None:
    """Gradtage eines Tages aus dem Tagesmittel der Außentemperatur (°C)."""
    if t_mean is None:
        return None
    if t_mean < heating_limit:
        return round(indoor_ref - t_mean, 3)
    return 0.0
