# Rechnung

Formeln und Regeln des Rechenkerns (`custom_components/tarif_cockpit/engine/`). Stand 0.6.

Vier Bereiche, strikt getrennt: **Verbrauch** (Tageswerte, Verbrauch seit Periodenbeginn) → **Prognose** (nur Mengen) → **Abrechnung** (Kosten, Zahlungen) → **Ergebnis** (Saldo, Urteil, Abschlag). Eine Preisänderung ändert deshalb nie die Verbrauchsprognose, ein neuer Abschlagsplan nie den Verbrauch.

## Verbrauch seit Periodenbeginn

`Verbrauch = Zählerstand jetzt − Zählerstand zu Periodenbeginn`

- Startwert: Ablesung zum Periodenbeginn (zwischen zwei Ablesungen linear), sonst der Zählerstand am Ende des Vortags aus der Statistik.
- Zähler mit Sensor: Stand jetzt (Einheit wird umgerechnet, z. B. Wh → kWh). Zähler nur mit Ablesungen: Stand der letzten Ablesung; die Prognose rechnet ab deren Zeitpunkt.
- Gas in m³ wird mit Brennwert × Zustandszahl in kWh umgerechnet; beide Werte können je Preisabschnitt gelten.

## Kosten

`Kosten = Σ Tag (Menge × Arbeitspreis) + Grund- und Messpreis × 12 / 365,25 je Tag + feste Jahresbeträge / 365,25 je Tag (+ Abwasser, + Leistungspreis)`

- Preise gelten ab ihrem Datum tagesgenau; eine Preisänderung beginnt keine neue Periode.
- Wasser: Abwasser = Frischwasser ohne Gartenzähler.
- Netto-Preise bekommen die Mehrwertsteuer des Vertrags; ausgegeben wird immer brutto.
- Fehlt für einen Tag ein Preis (oder bei Gas der Brennwert), gibt es keine Prognose-Kosten; die Kosten werden nicht mit 0 gerechnet. Ohne Brennwert gibt es bei einem m³-Gaszähler auch keine kWh und keinen Kennwert.
- Der Grundpreis zählt je Kalendertag; die Tage der Zeitumstellung (23/25 Stunden) zählen als ein Tag.

## Abschläge und Zahlungen

- Abschläge laut Plan: Zahltag im Monat, Rhythmus 1/2/3 Monate, Stufen mit Gültigkeit, optional Höchstzahl je Periode (z. B. 11). Der erste Termin einer Stufe ist der erste Zahltag ab ihrem Beginn; Zahltag und Rhythmus können je Stufe wechseln, frühere Termine ändern sich dadurch nicht. Ein Rumpfjahr hat entsprechend weniger Abschläge.
- Ohne Abschlagsplan und ohne erfasste Zahlungen gibt es keinen Saldo und kein Urteil (nie „0 € gezahlt“).
- Fällig (Datum erreicht) zählt als gezahlt. Eine erfasste Abschlagszahlung ersetzt den geplanten Abschlag desselben Monats; storniert streicht ihn.
- Einmalzahlungen und Schlusszahlungen erhöhen, Gutschriften und Erstattungen mindern die Zahlungen. Rechnungen sind keine Zahlungen.

## Prognose (Mengen)

**Strom und Wasser (Grundlast)**

`Rest = Vorjahr_Rest × (1 + (q − 1) / 2)`, `q = Verbrauch bisher / Vorjahr_bisher`, begrenzt auf 0,7 … 1,5

- Vorjahr = gleiches Kalenderfenster ein Jahr früher (nicht die Vorperiode). Mindestens 80 % der Tage müssen vorhanden sein; Lücken werden hochgerechnet. Qualität „gut“ ab 95 % Abdeckung, sonst „vorläufig“.
- Ersatzquelle: Tage ohne Statistik des Zählers kommen aus der eingetragenen Ersatzquelle (Qualität „geschätzt“).
- Rückfall 1: Durchschnitt seit Periodenbeginn × Resttage (ab 30 Tagen, „vorläufig“).
- Rückfall 2: Jahresverbrauch laut letzter Rechnung tagesanteilig („Annahme“). Eine Verteilung nach Standardlastprofil folgt später.
- **Wallbox**: Als Unterzähler wird sie vom Hauptzähler abgezogen; die Grundlast folgt dem Vorjahr, die Wallbox ihrem Mittel der letzten 30 Tage (mindestens 14 Tage mit Werten). Tage ohne Wallbox-Wert zählen ganz zur Grundlast (Hinweis `wallbox_luecken`).
- **Gartenwasser**: geht weder bisher noch in der Prognose ins Abwasser; der Gartenzähler wird wie die Wallbox fortgeschrieben.

**Gas und Fernwärme**

`Rest = Kennwert × Rest-Gradtage (+ Warmwasser-Grundlast × Resttage)`

- Rest-Gradtage aus dem Vorjahresfenster (mindestens 50 % der Tage, Lücken hochgerechnet).
- Kennwert und Warmwasser-Grundlast aus der Regression `V = WW × Tage + Kennwert × Gradtage` über die letzten 365 Tage (Tage bei Zählern mit Sensor, Ableseperioden bei Ablesungen). Warmwasser wird nur getrennt geschätzt, wenn es Tage ohne Heizbedarf gibt; sonst steckt es im Kennwert.
- Qualität: „unzureichend“ (unter 21 Tagen bzw. 4 Perioden oder unter 5 K Spanne oder R² < 0,6), „vorläufig“ (R² ≥ 0,6), „gut“ (R² ≥ 0,8 und mindestens 42 Tage bzw. 6 Perioden), „sehr gut“ (mindestens 90 Tage, 10 K Spanne, R² ≥ 0,85).
- **Unter „vorläufig“ gibt es keine Prognose**; eine Kennwert-Annahme wird nicht verwendet.

## Ergebnis

- `Prognose Kosten = Kosten bisher + Kosten der Restmenge + Grundpreis bis Periodenende`
- `Saldo = Abschläge der Periode − Prognose Kosten` (positiv: Rückzahlung)
- Urteil „passt“, wenn |Saldo| unter der Toleranz (Standard 5 % der Abschläge) liegt.
- `Abschlag empfohlen = (Prognose Kosten − schon gezahlt − geplante Einmalzahlungen) / offene Abschläge`, aufgerundet, ab dem nächsten Zahltag.
- `Abschlag passend = Prognose Kosten / Anzahl Abschläge der Periode` (wie bisher in den Template-Sensoren).
- Prognose-Schnappschüsse werden am 1. jedes Monats und beim Wechsel in die nächste Periode (letzter Stand der beendeten Periode) eingefroren.
- Ist der Zählerstand-Sensor gerade nicht verfügbar, gilt der Stand vom Ende des Vortags aus der Statistik; fehlt auch der, gibt es keine Kosten (nie still der Startstand).

## Abgleich mit 0.3

Mit Daniels Werten vom 13.11.2026 (Abrechnungsbeginn 30.06.2026) rechnet 0.6 wie die Template-Sensoren aus 0.3 (Test `tests/engine/test_v03_abgleich.py`):

| Größe | Strom 0.3 | Strom 0.6 | Gas 0.3 | Gas 0.6 (Kennwert 6,5) |
|---|---|---|---|---|
| Kosten bisher | 374,49 € | 374,51 € | 223,49 € | 223,49 € |
| Abschläge bisher | 825 € | 825 € | 830 € | 830 € |
| Prognose Verbrauch | 3532 kWh | 3531,9 kWh | 16206 kWh | 16205,6 kWh |
| Prognose Kosten | 1271,07 € | 1270,93 € | 1771,29 € | 1771,10 € |
| Differenz | 708,93 € | 709,07 € | 220,71 € | 220,90 € |
| passender Abschlag | 106 € | 106 € | 148 € | 148 € |

Live weicht Gas ab, sobald die Integration einen eigenen Kennwert gelernt hat; ohne gelernten Kennwert zeigt sie für Gas keine Prognose.

## Tageswerte aus der Langzeitstatistik

Für einen Zähler mit Sensor liest die Integration die Stundenwerte der Langzeitstatistik (laufende Summe):

`Verbrauch(Tag) = Summe am Ende der letzten Stunde des Tages − Summe am Ende der letzten Stunde des Vortags`

- Tage werden in der Zeitzone von Home Assistant gebildet. Die Tage der Zeitumstellung haben 23 bzw. 25 Stunden und werden richtig gezählt.
- Lücken innerhalb des Tages schaden nicht, weil die Summe durchläuft. Fehlt einer der beiden Randwerte, ist der Tag `missing`.
- Läuft der Zählerstand rückwärts (ohne erfassten Zählertausch), ist der Tag `invalid`.
- Liefert der Sensor eine andere Einheit derselben Art (z. B. Wh statt kWh), rechnet die Statistik sie in die Einheit des Zählers um.
- In Zeitzonen, deren Mitternacht nicht auf einer vollen UTC-Stunde liegt (z. B. Indien, +5:30), gilt die letzte volle Stunde vor Mitternacht als Tagesgrenze; solche Tage sind `estimated`.
- Gerechnet wird in der Einheit des Zählers (kWh, m³). Die Umrechnung Gas m³ → kWh geschieht erst bei Kosten und Prognose, mit dem Brennwert des jeweiligen Preisabschnitts.

## Tageswerte aus Ablesungen

Zwischen zwei gültigen Ablesungen wird der Verbrauch gleichmäßig über die Zeit verteilt (`interpolated`):

`Verbrauch(Tag) = (Stand₂ − Stand₁) / (Zeit₂ − Zeit₁) × Länge des Tages`

Ein Tag bekommt einen Wert, wenn er ganz zwischen der ersten und der letzten Ablesung liegt; fällt eine Ablesung in den Tag, setzt sich sein Wert aus beiden Abschnitten zusammen. Ungültige und ersetzte Ablesungen zählen nicht. Bei einem Zählertausch wird der Stand ab dem Tauschtag um „alter Endstand − neuer Startstand“ erhöht, der Verbrauch läuft durch.

## Gradtage

Gradtagzahl G20/15 (Werte im Haushalt einstellbar):

`Gradtage(Tag) = Innenbezug − Tagesmittel außen`, wenn das Tagesmittel unter der Heizgrenze liegt, sonst 0.

Mit den Standardwerten: Ein Tag mit 5 °C Mittel ergibt 20 − 5 = 15 Kd, ein Tag mit 16 °C ergibt 0 Kd.
Das Tagesmittel ist der Mittelwert der Stundenmittel. Fehlen mehr als 25 % der Stunden, gibt es kein Tagesmittel und keinen Gradtag (`missing`, nicht 0).

## Abrechnungsperioden

Siehe [DATENMODELL.md](DATENMODELL.md#abrechnungsperioden): Regeln, Rumpfjahr, Stichtag, Verschiebung durch den Ablesetermin, Anbieterwechsel.
