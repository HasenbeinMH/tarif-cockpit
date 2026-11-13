# Datenmodell

Wie das Tarif-Cockpit seine Daten hält. Stand 0.5. Grundlage ist das Arbeitspaket ([ARBEITSPAKET.md](ARBEITSPAKET.md), Abschnitt 2).

## Wo was gespeichert wird

| Daten | Speicher | Änderbar über |
|---|---|---|
| Haushalt (Außentemperatur, Heizgrenze, Innenbezug, Toleranz, Räume) | Config Entry | Einrichtung (0.7: Optionen) |
| Zähler (Medium, Sensor, Einheit, Brennwert/Zustandszahl) | Subentry „Zähler“ | Einrichtung |
| Verträge, Abrechnungsperioden, Preise, Abschlagspläne, Zahlungen, Rechnungen, Prognose-Schnappschüsse | eigener Store `.storage/tarif_cockpit.<id>` | Aktionen, ab 0.6 mehr |
| Ablesungen (mit Qualität) | Store | `add_ablesung`, `ablesung_ungueltig` |
| Tageswerte je Zähler | Store, eigene Tagesaggregation | täglich 00:05, `recalculate` |
| Langzeitstatistik von Home Assistant | Recorder | nur gelesen, ergänzende Quelle |

Der erste Vertrag und der Startstand stehen nur einmal in der Einrichtung. Beim ersten Start übernimmt sie der Store; danach gilt der Store.

**Schutz vor Datenverlust**
- Ablesungen werden nur angehängt. Eine Korrektur (`add_ablesung` mit `ersetzt`) markiert die alte Ablesung als ersetzt, eine ungültige Ablesung behält ihren Wert. Ersetzt werden kann nur die jeweils gültige Ablesung.
- Ein verwendbarer Tageswert wird nicht durch „fehlend“ ersetzt, wenn die Langzeitstatistik später fehlt (z. B. nach dem Aufräumen des Recorders).
- Ein Anbieterwechsel ändert am alten Vertrag nur das Ende.
- Fehlt der Store, nachdem er schon einmal gespeichert wurde, oder ist er beschädigt, startet die Integration **nicht** mit leeren Daten. Unter Reparaturen steht, was zu tun ist (Sicherung zurückspielen). Home Assistant benennt eine beschädigte Datei in `….corrupt.<Zeit>` um, der Inhalt bleibt also erhalten.
- Ist der Inhalt ungültig (z. B. Text statt Zahl), wird nichts gespeichert, bis das Problem behoben ist.
- Der Store hat eine Versionsnummer (aktuell 1.2) und Migrationen; Daten werden dabei nur ergänzt. Stammt die Datei von einer neueren Version, bleibt sie unverändert und die Integration meldet sich unter Reparaturen.
- Wird der Eintrag „Tarif-Cockpit“ gelöscht, bleibt die Datei unter `.storage` erhalten.

## Objekte

| Objekt | Wichtige Felder |
|---|---|
| Zähler | `medium` (strom, gas, wasser, fernwaerme), `entity` (oder keiner: nur Ablesungen), `unit`, `conversion` (Brennwert, Zustandszahl), `replacements` (Zählertausch: alter Endstand, neuer Startstand), `interval` (vorbereitet für dynamische Tarife) |
| Ablesung | Zeitpunkt, Stand, `quality`, `source` (initial, manual, switch, import, entity), Notiz, `superseded_by` |
| Tageswert | Datum, Verbrauch (Zählereinheit), Gradtage, Außen- und Innentemperatur, `quality`, `quality_flags` |
| Vertrag | Lieferant, Tarif, Beginn, Ende, `billing_rule`, `fixed_day`, brutto/netto, MwSt. |
| Abrechnungsperiode | Beginn, Ende, `status` (open, closing, closed), `is_partial` (Rumpfjahr), `is_final` (Schlussrechnung), Archiv |
| Preisabschnitt, Abschlagsplan, Zahlung, Rechnung, Prognose-Schnappschuss | im Modell vorhanden, genutzt ab 0.6 |

Rechnung, Zahlung und Abschlag sind getrennte Dinge: Eine Rechnung ist keine Periode, ein Abschlag ist keine Rechnung, eine Rechnung ist keine Zahlung.

## Abrechnungsperioden

Die Periode ist die zentrale Einheit für Berechnung und Archiv, nicht der Vertrag. Ein Vertrag hat mehrere Perioden; eine Preisänderung beginnt keine neue Periode.

| Regel | Beispiel (Vertragsbeginn 15.03.2026) |
|---|---|
| Vertragsjahr (`contract_year`) | 15.03.2026–14.03.2027, 15.03.2027–14.03.2028, … |
| Kalenderjahr (`calendar_year`) | **15.03.2026–31.12.2026 (Rumpfjahr)**, 01.01.2027–31.12.2027, … |
| Fester Stichtag (`fixed_day`, z. B. 30.06.) | **15.03.2026–29.06.2026 (Rumpfjahr)**, 30.06.2026–29.06.2027, … |
| Von Hand (`manual`) | Beginn und Ende je Periode werden eingetragen |

- Der Stichtag ist der **erste Tag** einer Periode. Der 29.02. ist als Stichtag nicht erlaubt.
- Beginnt ein Vertrag am 29.02., endet sein Vertragsjahr am 28.02.
- Liest der Versorger ein paar Tage früher oder später ab (höchstens ±10 Tage), verschiebt sich nur das Ende dieser einen Periode; die Regel bleibt.
- **Anbieterwechsel** (`add_folgevertrag`): Der alte Vertrag endet am Vortag des Wechsels, seine letzte Periode wird zur Schlussperiode (oft ein Rumpfjahr). Der neue Vertrag beginnt mit eigenen Perioden nach seiner Regel. Die Vertragskette eines Zählers muss lückenlos sein.
- Status: `open` (läuft), `closing` (Ende vorbei, Endablesung fehlt), `closed` (abgeschlossen; Archiv ab 0.6/1.0).
- **Beendete Perioden werden eingefroren:** Sobald eine Periode vorbei ist, wird sie gespeichert und danach nicht mehr verändert. Ein Folgevertrag, der in einer beendeten Periode beginnen würde, wird abgelehnt.
- Abweichender Ablesetermin: Aktion `set_periodenende`, nur für die laufende oder die zuletzt beendete Periode.
- Abrechnung „von Hand“: die erste Periode in der Einrichtung, weitere mit der Aktion `add_periode`.

## Qualität

Jeder Wert trägt eine Qualität (Regel 5 im Arbeitspaket):

| Qualität | Bedeutung |
|---|---|
| `real` | gemessen oder abgelesen |
| `estimated` | geschätzt (z. B. Schätzablesung des Versorgers). Lücken bei der Temperatur stehen als Hinweis in `quality_flags` |
| `interpolated` | zwischen zwei Ablesungen linear verteilt |
| `missing` | keine Daten. Der Wert ist leer, **nie 0** |
| `invalid` | ungültig (z. B. Zählerstand rückwärts), wird nicht verwendet |
| `assumption` | Annahme ohne eigene Daten (Startwerte, ab 0.6) |

## Datenstufen je Zähler

| Stufe | Quelle | Tageswerte |
|---|---|---|
| 1 | Ablesungen von Hand | linear verteilt zwischen zwei Ablesungen (`interpolated`); Tage vor der ersten und nach der letzten Ablesung fehlen |
| 2 | Zählerstand-Sensor mit Langzeitstatistik | Summe am Tagesende minus Summe am Vortag (`real`) |
| 2+ | Impulszähler | ab 0.9 |
