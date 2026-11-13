# Tarif-Cockpit – Hinweise für Claude Code

Plan und Regeln stehen in [`docs/ARBEITSPAKET.md`](docs/ARBEITSPAKET.md). Vor jeder Arbeit lesen:

- **Abschnitt 13 – Verbindliche Entwicklungsregeln**: gelten immer, ohne Ausnahme außer den dort genannten.
- **Abschnitt 12 – Grundsatzentscheidungen [A]–[M]**: nicht eigenmächtig ändern, bei Bedarf zuerst nachfragen.
- **Abschnitt 11 – Phasen**: nur an der aktuellen Phase arbeiten; sie endet mit Tests, Doku, Screenshots, Changelog, Version und GitHub-Release.

## Zu Beginn jeder Sitzung
1. Aktuelle Phase bestimmen (letzter Eintrag in `CHANGELOG.md` bzw. Version in `manifest.json`/`VERSION`).
2. Nach Regel 13 das empfohlene Modell und den Aufwand für diese Phase nennen (Spalte „Modell · Aufwand“ in Abschnitt 11). Passt die Sitzung nicht dazu, auf Bestätigung warten.
3. Neue Phasen im Planmodus beginnen und den Plan freigeben lassen, bevor Code entsteht.

## Kurz gefasst
- Sprache in Code-Kommentaren, Doku und UI: Deutsch (Englisch als zweite Übersetzung).
- Rechenkern `custom_components/tarif_cockpit/engine/` ohne Home-Assistant-Imports.
- Keine festen Entitätsnamen; Daniels Setup nur als Beispiel in der Doku.
- Installation wird über den Home-Assistant-Marketplace beschrieben (HACS nur als Hinweis für HA ≤ 2026.10); `hacs.json` bleibt.
- Unklare fachliche Punkte nicht raten, sondern nachfragen.
