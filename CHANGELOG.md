# Changelog

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
