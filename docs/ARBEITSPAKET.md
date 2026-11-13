# Arbeitspaket Tarif-Cockpit → v1.0

Repo: `HasenbeinMH/tarif-cockpit` (Stand v0.3.0, eine Datei `tarif-cockpit.js`, 436 Zeilen)
Vorbild: `msucimaker3112/energy-cockpit` (MIT): Farbschemen, Editor-Baukasten, Assistent, Build, Screenshots
Ziel-HA: 2026.11 oder neuer (HACS ist jetzt der **Marketplace** unter Einstellungen → Marketplace)
Stand: 13.11.2026, Version 2 (eingearbeitet: externes Review „Verbesserungsvorschläge Tarif-Cockpit“)

> **Für Claude Code:** Zuerst Abschnitt 13 (verbindliche Entwicklungsregeln) und 12 (Grundsatzentscheidungen) lesen. Die Phasen bauen aufeinander auf; jede Phase endet mit Tests, Doku, Screenshots, Changelog, Versionsnummer und GitHub-Release. Grundsatzentscheidungen nicht eigenmächtig ändern, sondern nachfragen.

---

## 0. Ausgangslage (v0.3.0)

- Eine Karte `tarif-cockpit-card`: Kacheln je Medium (Strom/Gas/Wasser) mit Urteil, Betrag, vier Balken, passender Abschlag, Gesamturteil, Footer-Kacheln, Auswertungsblock (`analysis`, Gas witterungsbereinigt, SVG-Diagramme aus der Langzeitstatistik).
- Die Karte **rechnet nicht**. Die Prognose kommt aus Template-Helfern und einer täglichen Automation (00:20, `recorder.get_statistics`), siehe `docs/sensoren.md`.
- Abschlag = ein `input_number` × Monate. Abschlagsänderungen im laufenden Jahr gehen nicht.
- Kein visueller Editor, kein Assistent. README beschreibt HACS.

## 1. Architektur

**Ein Repo, Typ Integration `tarif_cockpit`, das die Karten mitliefert.**

```
custom_components/tarif_cockpit/
  __init__.py            # Setup; Frontend-Registrierung gekapselt in frontend.py
  frontend.py            # StaticPath + Ressource registrieren (gegen min./aktuelle HA-Version testen)
  manifest.json          # domain, version, config_flow: true, dependencies: [recorder, frontend, http]
  config_flow.py         # Haushalt (Entry), Zähler + Wärmeerzeuger (Subentries), Optionen
  coordinator.py         # ereignisgesteuerte Neuberechnung je Zähler, tägliche Konsistenzprüfung
  store.py               # persistente Daten + Store-Migrationen (Version im Store)
  sensor.py  services.yaml  services.py  diagnostics.py
  engine/                # reiner Rechenkern, KEINE HA-Imports (Regel 1)
    model.py             # Datenobjekte (Abschnitt 2)
    consumption.py       # 1. Verbrauchsmodell: Ablesungen, Impulse, Tageswerte, Qualitätsflags
    billing.py           # 2. Abrechnung: Perioden, Preise, Grundpreis, Zahlungen, Rechnungen
    degree_days.py  regression.py  quality.py
    forecast.py          # 3. Prognose: Gradtage, Regression, Wetter, Wärmeerzeuger
    balance.py           # 4. Ergebnis: Saldo, Urteil, empfohlener Abschlag
  translations/de.json  translations/en.json
  frontend/tarif-cockpit.js   # Build-Ergebnis (beide Karten + Editoren)
src/                   # Karten-Quellen, Aufbau wie energy-cockpit (cards, editor-kit, wizard, i18n)
tools/build.mjs  tools/make-screenshots.py
test/*.html            # Karten mit Testdaten (auch Grundlage der Screenshots)
tests/engine/          # pytest Rechenkern (ohne HA)
tests/integration/     # pytest-homeassistant-custom-component (echte HA-Testumgebung)
hacs.json  README.md  CHANGELOG.md  docs/
```

Bild zur Einordnung: Die Integration ist der FB mit Instanz-DB (rechnet, hält Zustände persistent), die Karten sind die HMI-Bilder dazu.

**Vier Bereiche im Rechenkern, strikt getrennt** (Entscheidung E-Architektur):

| Bereich | Eingang | Ausgang | ändert sich bei |
|---|---|---|---|
| Verbrauch | Zählerstände, Ablesungen, Impulse, Statistik | Tageswerte mit Qualitätsflags | neuer Ablesung/Messwert, Korrektur |
| Abrechnung | Verbrauch, Verträge, Preise, Zahlungen | Ist-Kosten, gezahlte Abschläge | Preis, Plan, Zahlung |
| Prognose | Tageswerte, Gradtage, Wetter, Wärmeerzeuger | Restverbrauch je Tag (kWh) mit Qualität | neuen Tageswerten, Wetter |
| Ergebnis | Ist-Kosten, Prognose × Preise, Plan | Saldo, Urteil, empfohlener Abschlag | allem davor |

Explizite, einzeln testbare Funktionen: `calculate_consumption`, `calculate_forecast` (liefert **Mengen, keine Euro**), `calculate_actual_costs`, `calculate_payments`, `calculate_balance`, `calculate_recommended_advance`.
Folgen: Eine Preisänderung ändert nie die Verbrauchsprognose; ein neuer Wetterbericht ändert nie Ist-Kosten; ein neuer Abschlagsplan ändert nie die Verbrauchsstatistik; eine korrigierte Ablesung rechnet gezielt alles Abhängige neu.

- Die Karte behält einen **Sensor-Modus** (heutige YAML-Konfiguration) als Fallback ohne Integration.
- **Warum nicht Tariffy als Rechenkern?** Tariffy (weskona/tariffy) liefert Abrechnungsprognose, empfohlenen Abschlag und Folgetarife, hat laut Vorstellung aber keine Gradtag-Rechnung, keine Wärmeerzeuger, kein Warmwasser und keinen dokumentierten Abschlagsplan. Ideen werden übernommen (Abschnitt 10).
- `hacs.json` bleibt nötig: Der Marketplace aktualisiert Custom-Repositories ohne `hacs.json` nicht.

## 1a. Für alle Nutzer, nicht nur für Daniels Haus

**Grundregeln**
- Keine fest eingebauten Entitätsnamen. `getStubConfig` und Vorschläge kommen aus dem, was im jeweiligen HA vorhanden ist; Daniels Setup erscheint nur als Beispiel in der Doku.
- Alles außer einem Zähler mit Vertrag ist optional. Nicht konfigurierte Teile blendet die Karte aus, statt „—“ zu zeigen.
- Jede Funktion hat eine Rückfallebene, wenn Daten fehlen (Tabelle unten).
- Einheiten, Währung und Zahlenformat aus HA (`hass.config.currency`, `hass.locale`, `unit_system`); Sprache **Deutsch und Englisch**.
- Der Assistent beginnt mit **Fragen statt Feldern**: „Womit heizt du?“, „Wie wird Warmwasser erzeugt?“, „Hast du PV/Speicher/Wallbox?“, „Eigentümer oder Mieter?“, „Wie oft zahlst du Abschläge?“. Nicht zutreffende Schritte entfallen.

**Abzudeckende Voraussetzungen** (Spalte „ab“ = Version)

| Thema | Varianten | ab |
|---|---|---|
| Heizung | Gas, Fernwärme, Wärmepumpe (eigener Zähler oder am Hausstrom), Split-Klima, Elektro, Kaminofen, Kombinationen | 0.8 |
| | Öl, Pellets (Lieferungen statt Abschläge, Füllstand) | nach 1.0 |
| Warmwasser | über die Heizung, Durchlauferhitzer/Boiler (Strom), Wärmepumpe, Solarthermie (nur Hinweis) | 0.8 |
| Strom | Festpreis, mit/ohne PV und Speicher, Wallbox getrennt, § 14a als fester Rabatt | 0.6 |
| | HT/NT (Zweitarifzähler), dynamischer Tarif (Viertelstunde), § 14a zeitvariabel | nach 1.0 (Datenmodell ab 0.5 vorbereitet) |
| Abrechnung | 12/11 Abschläge, monatlich/zweimonatlich/vierteljährlich, Rumpfjahr, Anbieterwechsel, Preiswechsel, Bonus/Gutschrift | 0.6 |
| Fernwärme | Arbeitspreis, Grundpreis, Leistungspreis (kW), Messpreis; kWh/MWh | 0.8 |
| Wasser | Frischwasser und Abwasser mit getrennten Preisbestandteilen, Grundgebühren, Gartenwasser-Abzug, Niederschlagswasser fest | 0.6 |
| Mieter | Vorauszahlung an den Vermieter, Heizkostenverteiler | nach 1.0 |
| Daten | Zähler-Sensor, nur Ablesungen, gar kein Zähler (nur Rechnung) | 0.5 |
| | Impulse mit Tagesregression | 0.9 |

**Rückfallebenen bei fehlenden Daten**

| Fehlt | Ersatz |
|---|---|
| Vorjahr in der Langzeitstatistik | Jahresverbrauch laut letzter Rechnung, Verteilung nach Standardlastprofil (Strom) bzw. Gradtagen (Wärme) |
| Außentemperatur-Sensor | Wetter-Entität (Historie und Vorhersage) |
| Gradtage des Vorjahres | Mehrjahresmittel bzw. Normwerte aus der Wetter-Historie |
| Zähler | Ablesungen von Hand; Erinnerung als Event, Versand macht der Nutzer |
| Kennwert | Annahme je Gebäudetyp/Baujahr (Startwert, Qualität „Annahme“), wird mit Daten ersetzt |

**Tests**: Szenario-Fixtures für die Haushalte im Umfang der jeweiligen Version (bis 1.0 mindestens: Daniels Haus; Mietwohnung nur Strom; Wärmepumpe am eigenen Zähler ohne PV; Fernwärme; Haus ohne Zähler-Sensoren nur mit Ablesungen; Anbieterwechsel mit Rumpfjahr). Die Testseiten der Karten haben einen Szenario-Umschalter. Doku: je Szenario ein Beispiel mit Screenshot in `docs/BEISPIELE.md`.

## 2. Datenmodell

### 2.1 Wo was gespeichert wird (Entscheidung E)

| Daten | Speicher |
|---|---|
| Haushalt, Zähler-Stammdaten, Wärmeerzeuger | Config Entry / Subentries |
| Verträge, Preisabschnitte, Abrechnungsperioden, Abschlagspläne, Zahlungen, Rechnungen | persistenter Store (zeitliche Historie, **keine** Subentries) |
| Ablesungen (mit Qualitätsflag) | persistenter Store |
| **Tageswerte** (`DailyConsumption`) | eigene persistente Tagesaggregation, unabhängig vom Recorder |
| Gelernte Kennwerte mit Qualität, Prognose-Schnappschüsse | persistenter Store |
| HA-Langzeitstatistik | ergänzende Quelle (Backfill, Vorjahr), nicht Primärdaten |
| Sensorzustände | HA State Machine |

Store hat eine Versionsnummer und Migrationsfunktionen; beschädigte oder unvollständige Daten werden erkannt, gemeldet (Reparatur-Hinweis) und nie still verworfen.

### 2.2 Objekte

```
Household:      outdoor_temp_entity, weather_entity?, heating_limit=15, indoor_ref=20,
                tolerance_pct=5, rooms[{entity, area_m2?}]
Meter:          meter_id, medium, entity?, unit, conversion{calorific, z_factor},
                data_level, pulse_constant?, replacements[{date, old_end, new_start}]
Reading:        meter_id, timestamp, value, quality(real|estimated|interpolated|invalid), source
DailyConsumption: meter_id, date, consumption, degree_days, outdoor_temperature,
                indoor_temperature, heating_hours, fireplace_hours, quality_flags
Contract:       contract_id, meter_id, supplier, tariff, start_date, end_date?,
                billing_rule(contract_year|calendar_year|fixed_day TT.MM|manual),
                vat_mode(gross|net), vat_rate, min_term?, notice_period?, bonus?
BillingPeriod:  period_id, contract_id, start_date, end_date, start_reading, end_reading,
                status(open|closing|closed), is_partial(Rumpfjahr), archived_at?,
                archive{costs, payments, balance, prices_used, forecasts[]}
PriceSegment:   contract_id, valid_from, valid_to?, work_price, base_price,
                components?{energy, grid_fee, taxes_levies}, demand_price?(Fernwärme)
AdvancePlan:    contract_id, steps[{from, amount}], pay_day, rhythm(1|2|3 Monate)
Payment:        contract_id, date, amount, type(advance|one_off|credit|final|refund),
                status(planned|paid|cancelled)
Invoice:        contract_id, period_id?, invoice_date, period_from, period_to, amount,
                is_correction, corrects_invoice_id?          # Datenmodell ab 0.5, UI später
ForecastSnapshot: period_id, taken_at, forecast_kwh, forecast_cost, recommended_advance,
                quality                                       # monatlich + am Periodenende
HeatGenerator:  siehe 2.4
```

**Abrechnungsperiode ist die zentrale Einheit** für Berechnung und Archivierung, nicht der Vertrag (Entscheidung F). Ein Vertrag hat mehrere Perioden; eine Rechnung ist keine Periode; ein Abschlag ist keine Rechnung; eine Rechnung ist keine Zahlung (Entscheidung K). Unterschieden werden: Verbrauchskosten, gestellte Rechnungen, geplante Abschläge, tatsächliche Zahlungen.

### 2.3 Zähler, Vertragskette und Perioden

- Zähler bleibt bei einem Anbieterwechsel bestehen, mit ihm Ablesungen, Tageswerte und gelernte Kennwerte. Zählertausch: alter Endstand / neuer Startstand, Verbrauch läuft durch.
- **Vertragskette** je Zähler, lückenlos. Ein **Folgevertrag** kann vorab eingetragen werden und gilt ab seinem Beginn automatisch.
- **Abrechnungsregeln**:
  - `contract_year`: 12 Monate ab Vertragsbeginn (z. B. 15.03.–14.03.)
  - `calendar_year`: Stichtag 01.01.; erste Periode = **Rumpfjahr** Vertragsbeginn bis 31.12.
  - `fixed_day`: fester Tag TT.MM (beliebig, z. B. 30.06.); erste Periode Vertragsbeginn → nächster Stichtag
  - `manual`: Beginn und Ende je Periode von Hand
  - Ein abweichender tatsächlicher Ablesetermin (± einige Tage) verschiebt nur das Periodenende, die Regel bleibt
- Vertragsende: **Schlussrechnung** mit Wechselablesung (echt oder interpoliert, als Schätzwert markiert)
- Preise mit Gültigkeit, tagesgenau angewendet; Preisänderung ≠ neue Periode; brutto/netto eindeutig (`vat_mode`)
- Abschlagsplan mit Stufen; Anzahl ergibt sich aus der Periode (Rumpfjahr → weniger Abschläge); Einmalzahlungen/Gutschriften
- Prognose immer bis zum Ende der **laufenden Periode** (Rumpfjahr mit seinen eigenen Gradtagen bzw. seinem Lastprofil-Anteil)
- Liegt ein Wechsel vor dem Periodenende, zeigt die Karte „alter Vertrag bis Wechsel (Schlussrechnung)“ und „neuer Vertrag ab Wechsel“
- **Archiv**: Abgeschlossene Perioden frieren Preise, Zahlungen, Kosten, Saldo und alle Prognose-Schnappschüsse ein (Regel 4)
- Vorjahresvergleich = gleicher Kalenderzeitraum, nicht vorherige Periode
- Nach 1.0: Preisstaffeln/Mindestpreis, Rundungsregeln für centgenaue Rechnungsnachbildung

### 2.4 Wärmeerzeuger (Subentry, optional, beliebig viele)

- Typ: Gastherme, Split-Klima/Luft-Luft-WP, Wasser-WP, Fernwärme, Kaminofen, Elektro-Direktheizung
- Energieträger → zugeordneter Zähler: **eigener Zähler** (Gas, WP-Tarif) oder **Haushaltsstrom** (Split-Klima am Hauszähler → Strombilanz)
- **Leistungsbereich Heizbetrieb** laut Datenblatt: Nennleistung (Pflicht, Vorschlag je Typ) und optional kleinste Modulationsleistung, z. B. 16 und 5 kW bei „5–16 kW“
  - Auswahl **Nennwärmeleistung** (Wärmeabgabe, 50/30 °C) oder **Nennwärmebelastung** (Gaseinsatz, Heizwert Hi). Zwei getrennte Umrechnungswege: Belastung × Hs/Hi (≈ 1,11 Erdgas) = Gaseinsatz nach Brennwert; Leistung ÷ Wirkungsgrad-Annahme × Hs/Hi. Annahmen als solche kennzeichnen
  - optional Maximalleistung Warmwasser (Spitzen dann kein Plausibilitätsfehler)
  - Hilfetext: „Steht auf dem Typschild oder im Datenblatt, Werte für den Heizbetrieb verwenden“
- Optionale Entitäten mit Vorschlägen: Leistung (W/kW), Modulation (%), erzeugte Wärme (kWh), Betriebszustand, Raumtemperatur
- Wärmepumpe/Split-Klima: COP/SCOP-Annahme, bis ein Wärmemengenzähler da ist; optional Raum, den sie heizt
- Kaminofen (nur wenn aktiviert): Raumtemperatur am Aufstellort für die Betriebserkennung (Anstieg ≥ 1,5 K in 30 min, nur in der Heizperiode; feste Schwelle als Alternative), Wirkungsgrad, wirksamer Anteil, Holzpreis und Holzverbrauch
- Flag **„macht zentrales Warmwasser“**

**Drei Größen strikt trennen** (Entscheidung I), je Erzeuger und Tag:

| Feld | Bedeutung |
|---|---|
| `energy_input` | eingesetzte Energie (Gas, Strom, Holz) |
| `thermal_output` | gemessene Wärme (nur mit Wärmemengenzähler) |
| `estimated_thermal_output` | geschätzte Wärme (Strom × COP, Ofenstunden × Nennleistung × Anteil) |
| `avoided_energy` | tatsächliche Entlastung anderer Erzeuger, **nur aus Verbrauchsdaten gelernt** |
| `measurement_quality` | gemessen / geschätzt / Annahme |

Beispiel: Split-Klima mit COP 4 erzeugt aus 1 kWh Strom ≈ 4 kWh Wärme. Daraus folgt nicht, dass die Therme 4 kWh weniger braucht. `avoided_energy` wird erst ausgewiesen, wenn die Datenlage es trägt (Abschnitt 3.2).

## 2a. Datenstufen je Zähler (optional: Impulszähler)

| Stufe | Quelle | Was dazukommt |
|---|---|---|
| 1 | Ablesung von Hand (`add_ablesung`) | Kosten, Abschläge, Prognose, Kennwert je Ableseperiode |
| 2 | Zählerstand-Sensor/Impulse (`total_increasing`) | Tageswerte, Tagesregression, Ofen-/Klima-Effekt messbar, Leistung, Takten |

**Gas mit Impulsen** (0.9): Tagesregression; Ofen- und Klima-Effekt messbar; Momentanleistung (m³/h × Brennwert × Zustandszahl), Brennerlaufzeit, Takten gegen die Modulationsuntergrenze; tägliche Aktualisierung.
**Nach 1.0**: Heizlast-Schätzung auf Normaußentemperatur, Überdimensionierung.
**Wasser mit Impulsen** (nach 1.0): Leckage-Erkennung über das Nachtminimum, Großverbräuche (Garten, Pool), Energie je Liter Warmwasser.
**Pflichten**: Impulskonstante einstellbar; Abgleich mit jeder Ablesung (Offset, Faktor, Hinweis > 2 %); Lücken sind „fehlend“, nie Nullverbrauch (Regel 5).
**Doku**: Tabelle „Was du je Datenstufe bekommst“ mit Screenshots.

## 3. Rechenkern

### 3.1 Abrechnung
- Ist-Kosten: Verbrauch × Arbeitspreis je Preisabschnitt + Grundpreis tagesgenau (+ Leistungs-/Messpreis), brutto/netto nach Vertrag
- Zahlungen: bezahlt bis heute, geplant bis Periodenende, Einmalzahlungen, Gutschriften

### 3.2 Prognose (Mengen, keine Euro)

**Wärme (Gas usw.)**
- Regression: `V = WW-Grundlast × Tage + Kennwert × Gradtage`; WW-Term nur mit Warmwasser-Flag, sonst 0
- **Qualitätsmodell** (Entscheidung G), Ergebnis immer mit Kennzahlen:
  ```
  {"heat_coefficient": 6.5, "hot_water_baseload": 1.2, "r_squared": 0.94,
   "sample_count": 180, "temp_range_k": 14.2, "confidence": "good"}
  ```
  | Stufe | Bedingung (Startwerte, im Test justieren) |
  |---|---|
  | Annahme | keine eigenen Daten, Startwert aus Assistent |
  | Unzureichend | < 4 Perioden bzw. < 21 Tage oder Temperaturspanne < 5 K |
  | Vorläufig | erste belastbare Schätzung, R² ≥ 0,6 |
  | Gut | mehrere Perioden mit unterschiedlicher Witterung, R² ≥ 0,8 |
  | Sehr gut | Tageswerte über ≥ 90 Tage mit Spanne ≥ 10 K, R² ≥ 0,85 |
  - WW-Grundlast und Kennwert getrennt nur ab „Vorläufig“ **und** wenn Sommer-/Übergangsdaten vorhanden; sonst WW als Annahme fixieren
  - Unter „Vorläufig“: Prognose als vorläufig kennzeichnen oder Annahme verwenden (Regel 10)
- **Kaminofen**: Startwert aus Nennleistung als Annahme; eigener Regressionsterm erst, wenn genug Vergleichstage mit und ohne Ofen bei ähnlichen Gradtagen vorliegen (Startwert: ≥ 10 je Gruppe), sonst Verwechslung von Wetter- und Ofeneffekt
- Split-Klima/WP am Haushaltsstrom: `avoided_energy` auf Gas ebenso erst ab ausreichender Datenlage
- Rest-Gradtage: nächste Tage aus `weather.get_forecasts` (daily), danach Vorjahr bzw. Mehrjahresmittel; optional Band kältestes/wärmstes Vorjahr

**Innentemperatur** (wenn Raumsensoren konfiguriert)
- Zwei Kennwerte: **wetterbereinigt** (Gradtage mit 20 °C) und **temperaturbereinigt** (Gradtage mit gemessenem Tagesmittel innen)
- Grundlage sind **historische Tagesmittel mit Qualitätsprüfung** (aus `DailyConsumption.indoor_temperature`), keine Momentwerte
- 6 %/K nur als Annahme; eigener Wert wird gelernt
- Anzeige der Aufteilung („+8 %: +5 % Mehrverbrauch, +3 % durch höhere Raumtemperatur“) nur bei ausreichender Datenlage

**Strom**
- Grundlast wie heute (Vorjahr bisher/Rest, Abweichung zur Hälfte fortgeschrieben, 70–150 %)
- Wallbox als Sonderverbraucher mit eigenem Zähler getrennt fortgeschrieben, vor der Grundlast abgezogen (Entscheidung D)
- Wärmeerzeuger am Haushaltsstrom: witterungsabhängiger Anteil eigene Regression, vor der Grundlast abgezogen
- **Dynamischer Tarif** (Entscheidung J): braucht Intervallverbrauch (Viertelstunden-Energie, ausreichend aufgelöste Leistung oder andere Intervallmessung). Zu klären: Preis-Sensor brutto oder nur Börsenpreis, fixe/variable Bestandteile, negative Preise, fehlende Preis- oder Verbrauchsintervalle, Zeitumstellung (doppelte/fehlende Stunde). Datenmodell ab 0.5 vorbereitet, aktiviert nur mit geeigneter Quelle, Umsetzung nach 1.0. Bis dahin: **externe Kostenquelle** erlauben (z. B. Kosten-Sensor von Tarifwacht) statt eigener Viertelstundenrechnung

### 3.3 Ergebnis
Saldo, Urteil (passt/Nachzahlung/Rückzahlung, mit Toleranz), empfohlener Abschlag ab dem nächsten Zahltag (für ausgeglichenes Periodenende), Monatsreihen Ist/Prognose/Abschläge, **Qualität der Prognose** als Attribut.

### 3.4 Prognose gegen Realität (Entscheidung L)
- `ForecastSnapshot` monatlich und am Periodenende einfrieren (Prognose kWh/€, empfohlener Abschlag, Qualität)
- Beim Abschluss: Prognose gegen tatsächlichen Verbrauch, tatsächliche Kosten, tatsächlichen Saldo
- Datenmodell ab 0.5, Speicherung ab 0.6, Visualisierung (Tabelle „März 2.300 € / Juni 2.260 € / … gegen 2.225 €“) in 1.0, mehrjährig nach 1.0

## 4. Integration: Coordinator, Entitäten, Services

**Coordinator ereignisgesteuert** (Entscheidung H), je Zähler mit Dirty-Flags `consumption`, `forecast`, `costs`, `payments`:

| Auslöser | neu berechnet |
|---|---|
| neuer Zählerstand / Tageswechsel | Verbrauch → Prognose → Ergebnis des Zählers |
| neue/korrigierte Ablesung | betroffene Periode(n), danach Abhängiges |
| Preisänderung | Kosten → Ergebnis (Prognose-Mengen unverändert) |
| neue Wettervorhersage | Restprognose → Ergebnis |
| Abschlagsplan/Zahlung | Zahlungen → Ergebnis |
| täglich 1× | vollständige Konsistenzprüfung |

Sensor-Updates entprellt (z. B. 30 s), damit Impulszähler nicht dauernd Neuberechnungen auslösen.

- Sensoren je Zähler (aktiver Vertrag, laufende Periode; Attribute: Lieferant, Periode, Regel, Qualität): `periode_ende`, `kosten_bisher`, `abschlaege_bisher`, `prognose_kosten`, `prognose_verbrauch`, `abschlaege_periode`, `saldo`, `urteil` (enum), `abschlag_empfohlen`, `prognose_qualitaet`; Wärme zusätzlich `kennwert`, `ww_grundlast`; gesamt `saldo_gesamt`
- Services: `add_ablesung` (zaehler, zeitpunkt, stand, qualitaet), `set_abschlag` (vertrag, ab, betrag), `add_zahlung`, `add_rechnung`, `set_preis`, `add_folgevertrag`, `recalculate`
- Event `tarif_cockpit_urteil_geaendert` für Benachrichtigungen; Reparatur-Hinweise (Repairs) bei Datenproblemen
- `diagnostics.py` für Fehlerberichte

## 5. Karte 1: Tarifübersicht (`tarif-cockpit-card`)

Bleibt wie im ersten Entwurf, mit diesen Änderungen:
- **Balken „Abschläge bisher“ und „Abschläge Periode“: grün statt grau** (`OK` = 52,211,153, in hellen Schemen `DARK[OK]`). Heute `.bar i.ref{background:rgba(var(--ov),.32)}` → eigene Variable `--adv`, per `advance_color` überschreibbar
- Mehrere Abschlagsstufen als Text, z. B. „4 × 165 € + 8 × 180 €“
- „Empfohlener Abschlag ab 01.12.: 182 €“; Kennzeichnung „vorläufig“ je nach Prognosequalität
- Tipp auf den Abschlag öffnet einen Dialog zum Ändern (ruft `set_abschlag`), nur mit Integration
- Anbieterwechsel in der Periode: zwei Teile (alt/neu)
- Auswertungsblock `analysis` wandert in Karte 2; in Karte 1 übergangsweise noch lesbar (Doku: „veraltet“)

## 6. Karte 2: Auswertung (`tarif-cockpit-analyse-card`)

- Übernimmt `_analysis()` und `_svgChart()` aus v0.3.0
- Neu: Streudiagramm Verbrauch über Gradtage mit Regressionsgerade und **Qualitätsangabe**; kumulierter Verlauf Kosten (Ist + Prognose) gegen die Abschlags-Treppe; Aufteilung je Wärmeerzeuger (Eingang, Wärme, Entlastung mit Qualität); Ofen-Kacheln nur wenn aktiviert; Warmwasser-Kachel nur mit Flag; Prognose-gegen-Realität (1.0)
- Gleiche Farbschemen und Optik wie Karte 1

## 7. Visueller Editor und Einrichtungsassistent

**Config Flow = eigentlicher Assistent**:
1. Haushalt: Situation abfragen (1a), Außentemperatur, Wetter-Entität, optional Raumtemperaturen
2. Zähler + Vertrag: Medium → Zähler-Entität (gefiltert nach `device_class`/Einheit) oder „nur Ablesungen“ → Lieferant, Vertragsbeginn, **„Wann rechnet dein Versorger ab?“** mit Vorschau der ersten Perioden („erste Abrechnung: 15.03.–31.12.2026, Rumpfjahr“) → Startstand → Preise (brutto/netto) → Abschlagsplan
3. Heizung: Wärmeerzeuger (Typ setzt Nennleistungs-Vorschlag), Zuordnung, optionale Entitäten mit Vorschlägen, Warmwasser-Flag, Kaminofen optional
4. Zusammenfassung mit erster Prognose und deren Qualität
Später: Optionen, „Neu konfigurieren“, eigener Ablauf **„Anbieter wechseln“** (Wechseldatum, Wechselablesung, neuer Vertrag).

**Karten-Editor** nach `energy-cockpit/src/editor-kit.js` + `wizard.js`: Reiter „Assistent“ und „Alle Felder“ (Fallback ohne `ha-form`); mit Integration nur Eintrag wählen + Darstellung; im Sensor-Modus Vorschläge nach Einheit/`device_class`/Stichwörtern mit „Vorschlag übernehmen“ und Live-Wert; `getStubConfig(hass)` ohne feste Namen; Quelle und MIT-Lizenz von energy-cockpit nennen.

## 8. Repo, Build, Tests, CI (Entscheidung M)

- `src/` + `tools/build.mjs` → `custom_components/tarif_cockpit/frontend/`
- **Rechenkern** (`tests/engine`, ohne HA): Abschlagsplan mit Stufen, Preiswechsel, Rumpfjahr, Anbieterwechsel, Schaltjahr, Zählertausch, Regression mit/ohne WW, Qualitätsstufen, Ofen erst ab Vergleichstagen, Split-Klima am Hausstrom, fehlende Tage ≠ 0, brutto/netto, Zahlungsstatus, Szenario-Fixtures
- **Integration** (`tests/integration`, `pytest-homeassistant-custom-component`): minimale und aktuelle HA-Version; Setup, Unload, erneutes Setup; Neustart/Wiederherstellung; Config-Entry- und Store-Migration; fehlender Recorder; fehlende/nicht verfügbare Sensoren; beschädigter Store; Frontend-Registrierung
- **Karten**: `test/*.html` mit Szenario-Umschalter; `node --check`
- GitHub Actions: `hassfest`, Marketplace-/HACS-Validierung (prüfen, ob `hacs/action` unter dem Marketplace noch der aktuelle Weg ist), beide pytest-Suiten, Build
- Releases als GitHub-Release, Tag = `manifest.json`-Version

## 9. Doku (README und docs/) mit Bildern

- **README neu**: Nutzen mit Screenshot oben, unterstützte Voraussetzungen (Tabelle aus 1a), **zwei Installationswege**: (1) über den Marketplace-Katalog, sobald gelistet; (2) Einstellungen → Marketplace → „Aus Link hinzufügen“ für Custom-Repositories. Ob für Weg 2 eine GitHub-Verbindung nötig ist und wie der Klickpfad genau heißt, in HA 2026.11 prüfen. Hinweis für HA ≤ 2026.10: HACS
- `docs/EINRICHTUNG.md` (Assistent mit Screenshots), `docs/RECHNUNG.md` (Formeln, Qualitätsstufen, Umrechnungswege), `docs/SENSOR-MODUS.md` (ehem. `sensoren.md`), `docs/MIGRATION.md` (von v0.3), `docs/BEISPIELE.md` (Szenarien), `CHANGELOG.md`
- **Screenshots** automatisch: `tools/make-screenshots.py` mit Headless-Chromium/Playwright (Linux-tauglich) aus `test/*.html` → `docs/img/`; Config-Flow-Screenshots aus HA zusätzlich von Hand

## 10. Ideen aus anderen Projekten

- **Tariffy**: „Anpassung empfohlen“, Warnschwelle, Folgetarif mit Stichtag, Kündigungsfrist → Abschnitt 3/4
- **Tarifwacht**: Preise mit Gültig-ab-Datum, rückwirkende Berechnung; als **externe Kostenquelle** für dynamische Tarife bis zur eigenen Lösung
- **degree-days (Ernst79)**, **heating_cooling_degree_days (alepee)**: Gradtag-Logik → eigener Rechner im Kern, optional vorhandenen Gradtag-Sensor nutzen
- **energy-cockpit Raum-Abrechnung**: Ampel-Fortschrittsbalken, Monatsarchiv mit eingefrorenen Beträgen → Archiv und Prognose gegen Realität
- Nach 1.0: Kühlgradtage, Jahresabrechnung erfassen → Kennwerte kalibrieren

## 11. Phasen und Abnahme

| Phase | Inhalt | Ziel / Abnahme | Modell · Aufwand |
|---|---|---|---|
| **P1 · 0.4** | Abschlagsbalken grün, Karte 2 abtrennen, `src/` + Build, Editor-Grundlage (Sensor-Modus), README auf Marketplace, Screenshot-Werkzeug | Technische Basis; beide Karten laufen im Sensor-Modus wie bisher, README mit Bildern | `opusplan` · medium |
| **P2 · 0.5** | Integration-Grundgerüst, Store + Migration, Haushalt, Zähler, Verträge, **Perioden** (alle Regeln, Rumpfjahr, Wechsel), manuelle Ablesungen mit Qualität, Tagesaggregation, vollständiges Datenmodell (inkl. Invoice, Payment, ForecastSnapshot, Intervall-Vorbereitung) | Stabile Datenhaltung; Integrationstests Setup/Unload/Neustart/Migration grün | Opus · high (Planung xhigh) |
| **P3 · 0.6** | Rechenkern Verbrauch/Abrechnung/Prognose/Ergebnis getrennt, Ist-Kosten, Zahlungen, Preiswechsel, brutto/netto, Wasser/Abwasser, Strom-Grundlast + Wallbox, Gas über Gradtage mit Qualitätsmodell, Sensoren, Services, Coordinator ereignisgesteuert, Prognose-Schnappschüsse | Funktionierende Abrechnung; Zahlen = bisherige Template-Sensoren (±1 %) | Opus · high |
| **P4 · 0.7** | Config Flow vollständig (Fragen-Assistent, Vorschau der Perioden, Anbieterwechsel-Ablauf), Karten-Editor mit Integration, Abschlagsdialog | Bedienbare Integration; Einrichtung ohne YAML in einem frischen HA | `opusplan` · medium |
| **P5 · 0.8** | Wärmeerzeuger (Eingang/Wärme/Entlastung getrennt), Warmwasser, Kaminofen (Vergleichstage), Split-Klima, Fernwärme, Innentemperatur-Bereinigung, Streudiagramm, Kostenverlauf | Erweiterte Prognose; Szenario-Tests Heizung grün | Opus · high |
| **P6 · 0.9** | Impulszähler, Tagesregression, Abgleich mit Ablesungen, Gas-Leistung und Takten | Erweiterte Datenauswertung; Abgleich-Test mit verlorenen Impulsen | Opus · medium |
| **P7 · 1.0** | Wettervorhersage für Rest-Gradtage, Archiv, Prognose gegen Realität (Anzeige), Benachrichtigung/Event, Kündigungsfrist, Migration von v0.3, Doku vollständig | Stabiler Release; Migration in Daniels HA abgeschlossen | `opusplan` · medium; **Live-Migration: Opus · high** |

**Modell und Aufwand** (Einschätzung, keine Vorgabe der Doku): Einstellen mit `/model …` und `/effort …` bzw. `claude --model opus --effort high`. Am Ende jeder Phase eine Prüfung durch einen frischen Subagenten (Opus · high) gegen die Abnahmekriterien. `max` nicht verwenden. Läuft eine Phase auf medium zu ungenau: eine Stufe höher.

**Muss in 1.0 funktionieren**: Strom, Gas, Wasser; manuelle Ablesungen und Zähler-Sensoren; Vertragsketten und Preisänderungen; Abschlagspläne; Anbieterwechsel und Rumpfjahre; Grundlast- und Wärmeprognose mit Qualität; Wallbox getrennt; zwei Karten mit visuellem Editor; Migration von v0.3.
**Nach 1.0**: dynamischer Tarif mit eigener Viertelstundenabrechnung, HT/NT, § 14a zeitvariabel, Leckage-Erkennung, Heizlast/Überdimensionierung, Öl/Pellets, Mieter-Modus, Kühlgradtage, Preisstaffeln/Rundungsregeln, mehrjährige Prognosegüte.

**Grundsatz:** Ab P3 braucht die Prognose keine externen Template-Sensoren, Automationen oder Skripte mehr. Außerhalb bleiben nur Eingaben (z. B. Telegram-Ablesung → `add_ablesung`) und optionale Benachrichtigungen auf das Event.

**Migration in Daniels HA (nach P3, Parallelbetrieb 2 Wochen)**: Helfer (`input_number.abschlag_strom/gas` = 165/166 €, Startstände, `abschlag_zahltag`, Tarif-Helfer, Gas-Kennwerte, Ofen-Zähler) übernehmen; danach Automation 00:20, Template-Sensoren und Ofen-Erkennung abschalten, Telegram-Ablesung auf `add_ablesung` umstellen, Dashboard „Zähler“ auf die neuen Karten umstellen.

## 12. Grundsatzentscheidungen

Entschieden (13.11.2026):
- `[A]` **Ein Repo**, Integration liefert beide Karten mit; Sensor-Modus bleibt als Fallback.
- `[B]` Abschläge **in der Integration und per Dialog in der Karte** änderbar.
- `[C]` Kaminofen (wenn aktiviert) geht **in die Gasprognose ein**, eigener Faktor aber erst ab ausreichenden Vergleichstagen (vorher Annahme aus Nennleistung).
- `[D]` **Wallbox als getrennter Sonderverbraucher** in der Stromprognose, Teil von 1.0.
- `[E]` Datenhaltung: Tageswerte und Ablesungen im eigenen Store, unabhängig vom Recorder; Rechenkern in vier getrennte Bereiche.
- `[F]` **Abrechnungsperiode** als eigenständiges, zentrales Objekt.
- `[G]` Regression mit **Qualitätsbewertung** und Mindestdatenmenge.
- `[H]` Coordinator **ereignisgesteuert** mit Dirty-Flags je Zähler, täglich Konsistenzprüfung.
- `[I]` Wärmeerzeuger: Eingangsenergie, Wärme und tatsächliche Entlastung getrennt.
- `[J]` Dynamischer Tarif: Intervallverbrauch ist Voraussetzung; bis dahin externe Kostenquelle.
- `[K]` Rechnungen, Zahlungen und Abschläge getrennt.
- `[L]` Prognose-Schnappschüsse werden historisch eingefroren.
- `[M]` HA-Versionen, Config-Entry- und Store-Migrationen automatisiert testen.

Noch offen:
- Daten: Beginnt Daniels Abrechnungsjahr am 30.06. oder 30.07.? (Regel `fixed_day`)
- Zugriff: Claude Code braucht Schreibrechte auf das Repo (Session mit Push-Zugang).

## 13. Verbindliche Entwicklungsregeln für Claude Code

1. **Rechenkern unabhängig von HA**: keine HA-Imports in `engine/`, alles mit pytest isoliert testbar.
2. **Keine Fachberechnungen im Frontend**: JavaScript zeigt an und nimmt Eingaben entgegen. **Einzige Ausnahme**: der Sensor-Modus (ohne Integration) bildet wie in v0.3 nur das Urteil aus Abschlag, Hochrechnung und Toleranz.
3. **Keine stillen Datenverluste**: Ablesungen, Verträge und abgeschlossene Perioden werden durch Neuberechnungen oder Updates nie überschrieben.
4. **Historische Ergebnisse reproduzierbar**: Abgeschlossene Perioden mit den damals gültigen Preisen, Abschlägen und Ergebnissen archivieren.
5. **Jede Datenquelle hat Qualitätsmerkmale**: echt, geschätzt, interpoliert, fehlend, ungültig unterscheidbar; fehlend ist nie null.
6. **Keine fest eingebauten Entitätsnamen oder persönlichen Annahmen**.
7. **Keine unnötigen Abhängigkeiten**: zusätzliche Integrationen/Bibliotheken nur nach begründeter Entscheidung (Regression mit Bordmitteln bzw. kleiner eigener Implementierung).
8. **Abwärtskompatibilität**: YAML des Sensor-Modus bleibt funktionsfähig; Config-Entry- und Store-Migrationen getestet.
9. **Jede Phase eigenständig auslieferbar**: Tests, Doku, Screenshots, Changelog, Versionsnummer, GitHub-Release.
10. **Keine Aussagen ohne Datenbasis**: bei unzureichender Qualität Prognose „vorläufig“ kennzeichnen oder nicht anzeigen.
11. **Grundsatzentscheidungen (Abschnitt 12) nicht ohne Rücksprache ändern**: Architektur, Datenmodell, Formeln, Migrationsstrategie.
12. **Keine Phase beginnt mit offenen Fehlern der vorherigen.**
13. **Erinnerung an Modell und Aufwand**: Zu Beginn jeder Phase (vor dem Planmodus), vor der Live-Migration und in der Abschlussmeldung jeder Phase (für die nächste) nennt Claude Code das empfohlene Modell und den Aufwand aus der Tabelle in Abschnitt 11, z. B. „Für P2 bitte `/model opus` und `/effort high` setzen, für die Planung `/effort xhigh`“. Stimmen Modell oder Aufwand der Sitzung nicht, wartet Claude Code auf Daniels Bestätigung, bevor es weitermacht.
