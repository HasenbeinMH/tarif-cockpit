"""Rechenkern des Tarif-Cockpits.

Reiner Python-Code ohne Home-Assistant-Imports (Regel 1), mit pytest isoliert testbar.
Vier getrennte Bereiche (Entscheidung E): Verbrauch, Abrechnung, Prognose, Ergebnis.
In 0.5 enthalten: Datenmodell (model), Qualität (quality), Vertragskette und Perioden (billing),
Tageswerte aus Ablesungen und Stundenwerten (consumption), Gradtage (degree_days).
"""
