"""Einheiten: Umrechnung innerhalb einer Art (Energie, Volumen) und Gas m³ → kWh."""

from __future__ import annotations

_FACTORS: dict[str, tuple[str, float]] = {
    "Wh": ("energy", 0.001),
    "kWh": ("energy", 1.0),
    "MWh": ("energy", 1000.0),
    "L": ("volume", 0.001),
    "l": ("volume", 0.001),
    "m³": ("volume", 1.0),
    "m3": ("volume", 1.0),
}


def kind(unit: str | None) -> str | None:
    """Art einer Einheit: 'energy', 'volume' oder None (unbekannt)."""
    return _FACTORS.get(unit or "", (None, 0.0))[0]


def convert(value: float, from_unit: str | None, to_unit: str) -> float:
    """Wert in die Zieleinheit umrechnen. Gleiche oder fehlende Quelleinheit: unverändert.
    Verschiedene Arten (z. B. kWh → m³) sind ein Fehler."""
    if not from_unit or from_unit == to_unit:
        return value
    if from_unit not in _FACTORS or to_unit not in _FACTORS:
        raise ValueError(f"Einheit {from_unit!r} → {to_unit!r} unbekannt")
    k1, f1 = _FACTORS[from_unit]
    k2, f2 = _FACTORS[to_unit]
    if k1 != k2:
        raise ValueError(f"{from_unit} und {to_unit} sind nicht umrechenbar")
    return value * f1 / f2


def gas_factor(calorific: float | None, z_factor: float | None) -> float | None:
    """kWh je m³ (Brennwert × Zustandszahl). None, wenn ein Wert fehlt."""
    if not calorific or not z_factor:
        return None
    return calorific * z_factor
