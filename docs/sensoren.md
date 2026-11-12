# Sensoren für das Tarif-Cockpit

Die Karte zeigt nur an. Die Zahlen kommen aus diesen Sensoren. Alle Namen sind Beispiele, die Karte nimmt jeden Sensor, den du in der Konfiguration einträgst.

## Was du schon haben musst
| Zweck | Beispiel | Einheit |
|---|---|---|
| Zählerstand Strom (Bezug) | `sensor.zahler_strombezug` | kWh |
| Zählerstand Gas | `sensor.zahler_gas` | m³ |
| Startstand und Beginn des Abrechnungsjahres | `input_number.abrechnung_strom_startstand`, `input_datetime.abrechnung_strom_beginn` (Gas entsprechend) | kWh, m³, Datum |
| Tarife | `input_number.tarif_strom_arbeitspreis`, `…_grundpreis`, `tarif_gas_brennwert`, `tarif_gas_zustandszahl` | EUR/kWh, EUR/Monat |
| Abschlag und Zahltag | `input_number.abschlag_strom`, `abschlag_gas`, `abschlag_zahltag` | EUR/Monat, Tag |
| Außentemperatur | `sensor.gw3000a_outdoor_temperature` (deine Wetterstation) | °C |
| Gas-Kennwert (optional) | `input_number.gas_kennwert` (kWh je Gradtag, aus der Gas-Auswertung) | kWh/Kd |

Kosten bisher und Abschläge bisher entstehen so:
- Kosten bisher = (Zählerstand − Startstand) × Arbeitspreis + Grundpreis × 12 × Tage / 365,25 (Gas: Zählerstand in m³ × Brennwert × Zustandszahl).
- Abschläge bisher = Anzahl der Zahltage seit Beginn × Abschlag.

## Hilfswerte (input_number)
| Name | Einheit | Wer füllt ihn |
|---|---|---|
| `prognose_strom_vorjahr_bisher` | kWh | Automation |
| `prognose_strom_vorjahr_rest` | kWh | Automation |
| `prognose_gas_gradtage_rest` | Kd | Automation |
| `prognose_gas_kennwert_annahme` | kWh/Kd, Startwert 6,5 | du |

## Automation: Vorjahreswerte
Läuft täglich um 00:20 und holt mit `recorder.get_statistics` (Tageswerte) aus der Langzeitstatistik:
- **Strom:** den Netzbezug des Vorjahres, getrennt in den Teil, der im Abrechnungsjahr schon vorbei ist (`vorjahr_bisher`), und den noch offenen Rest (`vorjahr_rest`). Quelle ist der Netzzähler des Wechselrichters oder Smart Meters (`total_increasing`).
- **Gas:** die Gradtage G20/15 des Vorjahres für den offenen Rest (Summe aus 20 °C − Tagesmittel an allen Tagen unter 15 °C). Fehlen Tage in der Statistik, wird auf die volle Tageszahl hochgerechnet.

## Prognose-Sensoren (Template-Helfer)
**Strom: Verbrauch**
```jinja
{% set used = states('sensor.zahler_strombezug') | float - states('input_number.abrechnung_strom_startstand') | float %}
{% set vb = states('input_number.prognose_strom_vorjahr_bisher') | float(0) %}
{% set ratio = [[used / vb if vb > 0 else 1, 0.7] | max, 1.5] | min %}
{{ (used + states('input_number.prognose_strom_vorjahr_rest') | float(0) * (1 + (ratio - 1) / 2)) | round(0) }}
```
Der bisherige Mehr- oder Minderverbrauch gegenüber dem Vorjahr (auf 70 bis 150 % begrenzt) wirkt zur Hälfte auf den Rest des Jahres.

**Gas: Verbrauch**
```jinja
{% set f = states('input_number.tarif_gas_brennwert') | float * states('input_number.tarif_gas_zustandszahl') | float %}
{% set used = (states('sensor.zahler_gas') | float - states('input_number.abrechnung_gas_startstand') | float) * f %}
{% set kw = states('input_number.gas_kennwert') | float(0) %}
{% set kw = kw if kw > 0 else states('input_number.prognose_gas_kennwert_annahme') | float(6.5) %}
{{ (used + kw * states('input_number.prognose_gas_gradtage_rest') | float(0)) | round(0) }}
```
Bis der erste echte Kennwert vorliegt, gilt die Annahme (Standard 6,5 kWh/Kd).

**Kosten** (je Medium, Einheit EUR)
```jinja
{{ (states('sensor.prognose_strom_verbrauch') | float * states('input_number.tarif_strom_arbeitspreis') | float
    + states('input_number.tarif_strom_grundpreis') | float * 12) | round(2) }}
```
Für Gas entsprechend mit `tarif_gas_arbeitspreis` und `tarif_gas_grundpreis`.

Die Karte bildet das Urteil selbst aus `advance`, `forecast_cost` und der Toleranz. Zusätzliche Differenz-, Urteil- und Abschlag-passend-Sensoren sind nur nötig, wenn du das Ergebnis auch außerhalb der Karte brauchst, zum Beispiel in einer Benachrichtigung.

## Grenzen
- Gas im Sommer: Warmwasser an Tagen ohne Heizbedarf steckt nicht in der Gradtag-Rechnung, die Hochrechnung liegt etwas zu niedrig.
- Ohne Langzeitstatistik aus dem Vorjahr (Strom) gibt es keine Prognose.
