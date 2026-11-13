# Changelog

## 0.6.0 – 2026-11-13

Die Integration **rechnet selbst**: Kosten, Abschläge, Prognose, Saldo, Urteil und empfohlener Abschlag. Template-Sensoren, Helfer und die tägliche Automation werden für die Prognose nicht mehr gebraucht. Umstieg mit Parallelbetrieb: [docs/MIGRATION.md](docs/MIGRATION.md).

### Neu
- **Rechenkern** in vier getrennten Bereichen: Verbrauch → Prognose (nur Mengen) → Kosten und Zahlungen → Ergebnis.
- **Kosten** tagesgenau je Preisabschnitt: Arbeits-, Grund- und Messpreis, brutto/netto, Gas mit Brennwert/Zustandszahl je Abschnitt, Wasser mit Abwasser (ohne Gartenzähler) und festen Jahresbeträgen, Fernwärme mit Leistungspreis.
- **Abschläge und Zahlungen**: Plan mit Stufen, Zahltag, Rhythmus 1/2/3 Monate und Höchstzahl je Periode (z. B. 11), Einmalzahlungen, Gutschriften, Erstattungen, Stornos; Rechnungen getrennt erfasst.
- **Prognose** bis zum Ende der laufenden Periode: Strom und Wasser über das Vorjahr im gleichen Kalenderfenster (mit Rückfallebenen), **Wallbox** als Unterzähler getrennt fortgeschrieben, Gas und Fernwärme über einen **gelernten Kennwert** je Gradtag mit Warmwasser-Grundlast und **Qualitätsstufen** (annahme … sehr gut). Ohne belastbaren Kennwert keine Gasprognose.
- **Ersatzquelle für fehlende Historie** je Zähler (z. B. Wechselrichter-Bezugszähler, solange der Zähler-Sensor neu ist).
- **Sensoren je Zähler:** Kosten bisher, Abschläge bisher, Abschlag, Abschläge Periode, Prognose Verbrauch, Prognose Kosten, Saldo, Urteil, Abschlag empfohlen, Prognose-Qualität, bei Wärme Kennwert und Warmwasser-Grundlast; **Saldo gesamt** am Gerät Haushalt.
- **Aktionen:** `set_preis`, `set_abschlag`, `add_zahlung`, `add_rechnung`.
- **Coordinator ereignisgesteuert** mit Dirty-Flags je Zähler: Zählerstand (entprellt 30 s), Ablesung, Preis, Abschlag/Zahlung; täglich 00:05 vollständige Neuberechnung. Eine Preisänderung rechnet die Prognose-Mengen nicht neu.
- **Prognose-Schnappschüsse** am 1. jedes Monats und am Periodenende.
- **Einrichtung:** Zähler-Dialog mit Preisen und Abschlägen, Unterzähler (Wallbox, Gartenwasser), Jahresverbrauch laut Rechnung, Ersatzquelle; „Neu konfigurieren“ für die Stammdaten des Zählers.
- **Abgleich mit 0.3:** Mit Daniels Werten stimmen Kosten, Abschläge, Strom-Prognose, Differenz und passender Abschlag auf ±1 % (Tabelle in [docs/RECHNUNG.md](docs/RECHNUNG.md)).

- **Keine Aussagen ohne Daten:**
  - Ohne Abschlagsplan gibt es keinen Saldo.
  - Gas in m³ braucht Brennwert und Zustandszahl.
  - Ist der Zähler-Sensor nicht verfügbar, gilt der Stand vom Ende des Vortags, nie still der Startstand.
  - Der Gesamtsaldo bleibt leer, solange ein Zähler noch keinen Saldo hat.
- Abschlagsstufen mit eigenem Zahltag und Rhythmus. Der erste Termin ist der erste Zahltag ab Beginn der Stufe; frühere Termine ändern sich nie rückwirkend.

### Geändert
- Tagesaggregation: Eine nachträglich gesetzte Ersatzquelle füllt auch ältere fehlende Tage. Nach dem Update werden Tageswerte einmal neu aus der Statistik geholt, mit dem Zählerstand am Tagesende.
- Tagesaggregation: Zähler mit Sensor werden 400 Tage zurück nachgeholt, unabhängig vom Vertragsbeginn (für das Vorjahr), mit Zählerstand am Tagesende.
- Store 1.3 und Eintrag 1.3 mit Migration (neue Felder, bestehende Zähler sind Hauptzähler).

## 0.5.0 – 2026-11-13

Tarif-Cockpit ist jetzt eine **Integration**, die beide Karten mitliefert. Umstieg von der Dashboard-Installation: [docs/MIGRATION.md](docs/MIGRATION.md). Voraussetzung: Home Assistant 2026.11.

### Neu
- **Integration `tarif_cockpit`** mit Einrichtung in der Oberfläche: Haushalt (Außentemperatur, Heizgrenze, Innenbezug, Toleranz) und beliebig viele **Zähler** (Strom, Gas, Wasser, Fernwärme), je mit erstem Vertrag und Startstand. Die Einrichtung zeigt eine Vorschau der ersten Abrechnungsperioden.
- **Abrechnungsperioden** nach der Regel des Versorgers: Vertragsjahr, Kalenderjahr mit Rumpfjahr, fester Stichtag (TT.MM), von Hand. Schaltjahr, verschobener Ablesetermin (±10 Tage) und Anbieterwechsel mit Schlussperiode werden berücksichtigt.
- **Aktionen:** `add_ablesung` (auch als Korrektur einer früheren Ablesung), `ablesung_ungueltig`, `add_folgevertrag` (Anbieterwechsel), `set_periodenende` (abweichender Ablesetermin), `add_periode` (Abrechnung von Hand), `recalculate`.
- **Beendete Perioden werden eingefroren** und nicht mehr verändert; ein Wechsel in eine beendete Periode wird abgelehnt.
- **Eigene Tagesaggregation:** Tageswerte je Zähler aus der Langzeitstatistik (Zähler mit Sensor) oder aus Ablesungen (linear verteilt), mit Außen- und Raumtemperatur und Gradtagen. Fehlende Tage bleiben leer, nie 0.
- **Sensoren je Zähler:** Periodenende (mit Beginn, Rumpfjahr, Status, Lieferant), letzte Ablesung, abgelesener Zählerstand, Vollständigkeit der Tageswerte.
- **Vollständiges Datenmodell** inklusive Preisabschnitten, Abschlagsplänen, Zahlungen, Rechnungen, Prognose-Schnappschüssen und Vorbereitung für Intervallwerte (dynamische Tarife); genutzt ab 0.6.
- **Schutz vor Datenverlust:** eigener Speicher mit Versionsnummer und Migrationen. Fehlende oder beschädigte Daten werden unter Reparaturen gemeldet, nie still durch leere Daten ersetzt.
- Reparatur-Hinweise für eine noch vorhandene Dashboard-Installation und für Zählerstand-Sensoren ohne Langzeitstatistik. Diagnose-Download für Fehlerberichte.
- Neue Doku: [docs/DATENMODELL.md](docs/DATENMODELL.md), [docs/RECHNUNG.md](docs/RECHNUNG.md).

### Geändert
- Die Karten werden von der Integration ausgeliefert (`/tarif_cockpit/tarif-cockpit.js`), ein Eintrag unter Dashboard-Ressourcen ist nicht mehr nötig. Sie arbeiten in 0.5 weiter im Sensor-Modus; YAML aus 0.4 bleibt gültig.
- `tarif-cockpit.js` liegt nicht mehr im Hauptverzeichnis. Das Repository hat im Marketplace die Kategorie **Integration**.

### Intern
- Die Migrationen 1.1 → 1.2 (Store und Eintrag) sind künstliche Vorstufen ohne eigenes Release; sie belegen, dass der Migrationsweg funktioniert.
- Rechenkern `engine/` ohne Home-Assistant-Imports mit eigenen Tests (Perioden, Ablesungen, Tageswerte inkl. Zeitumstellung, Szenarien).
- Integrationstests mit `pytest-homeassistant` gegen HA 2026.11.0 und 2026.11.1 (Setup, Unload, Neustart, Migrationen, beschädigter Speicher, fehlender Recorder, Recorder-Statistik, Aktionen, Frontend), lokal in Docker (`tools/test-ha.ps1`) und in GitHub Actions; dazu hassfest und Marketplace-Prüfung.

## 0.4.0 – 2026-11-13

Technische Basis für die kommende Integration. Bestehendes YAML aus 0.3 funktioniert unverändert.

### Neu
- **Visueller Editor** für beide Karten. Der Reiter „Assistent“ führt Schritt für Schritt durch die Sensoren und schlägt passende Entitäten vor (nach Einheit, Geräteklasse und Stichwörtern), mit „Vorschlag übernehmen“ und dem aktuellen Wert der gewählten Entität. Der Reiter „Alle Felder“ zeigt das Formular von Home Assistant.
- **Zweite Karte `custom:tarif-cockpit-analyse-card`** für die Auswertung (Kennwert, Vergleich, Kacheln, Verlauf). Die Felder entsprechen dem bisherigen Block `analysis`.
- **Englische Oberfläche.** Sprache, Zahlenformat und Währung kommen aus Home Assistant.
- Neue Option `advance_color` für die Farbe der Abschlagsbalken, für die ganze Karte oder je Medium.
- Eine frisch hinzugefügte Karte schlägt passende Sensoren aus dem eigenen Home Assistant vor, ohne fest eingebaute Namen. Ohne Treffer zeigt sie „Noch nicht eingerichtet“ statt einer Fehlermeldung.

### Geändert
- Die Balken „Abschläge bisher“ und „Abschläge Jahr“ sind jetzt **grün** statt grau, in den hellen Schemen dunkler grün.
- Der Block `analysis` in `tarif-cockpit-card` ist **veraltet**. Er wird weiter angezeigt, in der Browser-Konsole erscheint ein Hinweis. Umstieg: [docs/MIGRATION.md](docs/MIGRATION.md).
- Ist Home Assistant auf Englisch eingestellt, zeigen die Karten jetzt englische Texte sowie Zahlen und Daten im eingestellten Format (vorher immer deutsch).
- Eine Konfiguration ohne `strom`, `gas` oder `wasser` (z. B. nur `analysis`) führt nicht mehr zu einer Fehlermeldung, die Karte wird angezeigt.
- `docs/sensoren.md` heißt jetzt [docs/SENSOR-MODUS.md](docs/SENSOR-MODUS.md).
- README auf den Marketplace von Home Assistant 2026.11 umgestellt, mit Bildern.

### Intern
- Quellen in `src/`, Build ohne Abhängigkeiten mit `node tools/build.mjs`. `tarif-cockpit.js` bleibt im Hauptverzeichnis, das Repo bleibt vom Typ Dashboard.
- Testseiten `test/overview.html`, `test/analyse.html` und `test/editor.html` mit Szenario-Umschalter.
- Automatische Screenshots mit `tools/make-screenshots.py` (Playwright).
- GitHub Actions: Prüfung durch den Marketplace/HACS, Build-Abgleich und Syntaxprüfung.

## 0.3.0 – 2026-11-12
- Abrechnungszeitraum aus einem Datums-Helfer (`period_start`), per Tipp änderbar. Eigener Beginn je Medium (`start`).

## 0.2.0 – 2026-11-12
- Auswertung `analysis`: Kennwert je Gradtag, Vergleich mit der Vorperiode, Gradtage, Kaminofen-Kacheln, Verlaufsdiagramme aus der Langzeitstatistik.

## 0.1.0 – 2026-11-12
- Erste Version: Karte für Kosten, Abschläge und Jahresprognose von Strom, Gas und Wasser mit Urteil (passt, Nachzahlung, Rückzahlung).
