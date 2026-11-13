"""Qualitätsmerkmale jeder Datenquelle (Regel 5).

Echt, geschätzt, interpoliert, fehlend, ungültig und Annahme sind unterscheidbar.
Fehlend ist nie null: Ein fehlender Tageswert hat den Verbrauch ``None``, nicht 0.
"""

from __future__ import annotations

from enum import StrEnum


class Quality(StrEnum):
    """Qualität einer Ablesung oder eines Tageswerts."""

    REAL = "real"  # gemessen oder abgelesen
    ESTIMATED = "estimated"  # geschätzt (z. B. Tag mit fehlenden Stunden, Schätzablesung)
    INTERPOLATED = "interpolated"  # zwischen zwei Ablesungen verteilt
    MISSING = "missing"  # keine Daten, Wert ist None
    INVALID = "invalid"  # ungültig, wird nicht verwendet
    ASSUMPTION = "assumption"  # Annahme (Startwert ohne eigene Daten)


# Qualitäten, die eine Ablesung haben darf
READING_QUALITIES = (Quality.REAL, Quality.ESTIMATED, Quality.INTERPOLATED, Quality.INVALID)

# Rangfolge: je höher, desto schlechter. Beim Zusammenfassen gilt die schlechteste Qualität.
_RANK = {
    Quality.REAL: 0,
    Quality.ESTIMATED: 1,
    Quality.INTERPOLATED: 2,
    Quality.ASSUMPTION: 3,
    Quality.MISSING: 4,
    Quality.INVALID: 5,
}


def worst(*qualities: Quality) -> Quality:
    """Schlechteste Qualität aus mehreren (z. B. Tag aus Stunden unterschiedlicher Qualität)."""
    if not qualities:
        return Quality.MISSING
    return max(qualities, key=lambda q: _RANK[Quality(q)])


def usable(quality: Quality | str) -> bool:
    """Darf ein Wert dieser Qualität in Rechnungen eingehen?"""
    return Quality(quality) not in (Quality.MISSING, Quality.INVALID)
