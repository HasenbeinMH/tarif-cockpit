# Tarif-Cockpit

Kosten, Abschläge und Jahresprognose für Strom, Gas und Wasser auf einen Blick: **passt, Nachzahlung oder Rückzahlung**.
Eine Karte für Home Assistant im Stil von [energy-cockpit](https://github.com/msucimaker3112/energy-cockpit), mit denselben Farbschemen. Komplett deutsch.

## Was die Karte zeigt
- Pro Medium (Strom, Gas, Wasser) eine Kachel mit Urteil, Betrag und vier Balken: Kosten bisher, Abschläge bisher, Hochrechnung fürs Jahr, Abschläge fürs Jahr.
- Den passenden monatlichen Abschlag.
- Oben das Gesamturteil über alle Medien.
- Unten frei wählbare Kacheln (Zählerstände, Tarife, letzte Ablesung).

Die Karte **rechnet die Prognose nicht selbst**. Sie zeigt, was deine Sensoren liefern, und bildet daraus nur das Urteil:
`Differenz = Abschlag × Monate − Hochrechnung`. Positiv heißt Rückzahlung, negativ Nachzahlung. Liegt die Differenz unter 5 % der Abschläge, steht dort „Passt“.

## Installation
1. HACS öffnen, oben rechts Menü, **Benutzerdefinierte Repositories**.
2. `https://github.com/HasenbeinMH/tarif-cockpit` eintragen, Kategorie **Dashboard** (früher „Lovelace“).
3. `tarif-cockpit` herunterladen, Browser-Cache leeren (Strg+F5).
4. Karte hinzufügen: **Tarif-Cockpit**, oder als YAML wie unten.

## Konfiguration
```yaml
type: custom:tarif-cockpit-card
title: Tarife und Abrechnung
subtitle: Abrechnungsjahr ab 30.06.2026
theme: dunkel          # dunkel, graphit, hell, warm, auto, ha
tolerance_pct: 5       # ab welcher Abweichung nicht mehr "Passt" gilt
strom:
  cost: sensor.kosten_strom_abrechnungsjahr         # Kosten seit Abrechnungsbeginn (EUR)
  advance_paid: sensor.abschlage_strom_abrechnungsjahr  # bisher gezahlte Abschläge (EUR)
  forecast_cost: sensor.prognose_strom_kosten       # Hochrechnung bis Jahresende (EUR)
  forecast_kwh: sensor.prognose_strom_verbrauch     # optional, Hochrechnung in kWh
  advance: input_number.abschlag_strom              # monatlicher Abschlag (EUR)
gas:
  cost: sensor.kosten_gas_abrechnungsjahr
  advance_paid: sensor.abschlage_gas_abrechnungsjahr
  forecast_cost: sensor.prognose_gas_kosten
  forecast_kwh: sensor.prognose_gas_verbrauch
  advance: input_number.abschlag_gas
footer:
  - { name: Strombezug, entity: sensor.zahler_strombezug }
  - { name: Letzte Ablesung, entity: input_datetime.zahler_letzte_ablesung, format: date }
  - { name: Strom Arbeitspreis, entity: input_number.tarif_strom_arbeitspreis, scale: 100, unit: ct/kWh, decimals: 2 }
```

| Option | Bedeutung |
|---|---|
| `strom`, `gas`, `wasser` | Mindestens eines ist nötig. Weitere Felder je Medium: `name`, `color` (`#hex`), `months` (Abschläge pro Jahr, Standard 12) |
| `title`, `subtitle`, `icon` | Kopfzeile |
| `theme` | Farbschema wie bei energy-cockpit |
| `tolerance_pct` | Schwelle für „Passt“, Standard 5 |
| `footer` | Liste von Kacheln mit `entity`, `name`, `unit`, `decimals`, `scale`, `format: date` |
| `analysis` | Auswertung unter den Medien-Kacheln, siehe unten |

### Auswertung (z. B. Gas witterungsbereinigt)
Optional zeigt die Karte unter den Kacheln einen Auswertungsblock: Kennwert, Vergleich mit der Vorperiode, Kacheln für Verbrauch, Außentemperatur und Gradtage sowie zwei Verlaufsdiagramme (Verbrauch gegen Außentemperatur je Monat, Kennwert je Monat). Der Verlauf kommt aus der Langzeitstatistik der Sensoren. Solange noch kein Kennwert vorliegt, steht dort „Wartet auf Ablesung“.

```yaml
analysis:
  title: Gas witterungsbereinigt
  kennwert: sensor.gas_kennwert_je_gradtag          # kWh je Gradtag
  kennwert_previous: input_number.gas_kennwert_vorperiode   # optional, für den Vergleich
  consumption: sensor.gas_verbrauch_letzte_periode  # kWh
  temperature: sensor.gas_aussentemperatur_letzte_periode   # °C
  degree_days: sensor.gas_gradtage_letzte_periode
  extras:                                           # beliebige weitere Kacheln, z. B. Kaminofen
    - { name: Ofentage seit Ablesung, entity: input_number.ofentage_periode, unit: d, decimals: 0 }
    - { name: Ofenstunden seit Ablesung, entity: input_number.ofen_stunden_periode, unit: h, decimals: 0 }
  explain: Kennwert = kWh Gas je Gradtag. Bleibt er gleich, hat sich am Heizverhalten nichts geändert.
  months: 24          # Monate im Verlauf (höchstens 36)
  history: true       # false blendet die Diagramme aus
  color: '#fb923c'
```

Fehlt ein Sensor oder ist er nicht verfügbar, zeigt die Kachel „Noch keine Prognose“ bzw. „—“.

## Die Sensoren dazu
Die Karte erwartet Sensoren für Kosten, gezahlte Abschläge und Hochrechnung. Wie man sie in Home Assistant baut (Template-Helfer und eine tägliche Automation, die das Vorjahr aus der Langzeitstatistik holt), steht in der Anleitung unter [docs/sensoren.md](docs/sensoren.md).

## Entwickeln und testen
`test/index.html` öffnen (über einen lokalen Webserver, z. B. `python -m http.server`) zeigt die Karte mit Testdaten, mit Knöpfen für Farbschemen, Nachzahlung und fehlende Prognose.

## Hinweis
Die Karte liefert eine Hochrechnung und ersetzt keine Abrechnung deines Versorgers.

## Lizenz
MIT, siehe LICENSE.
