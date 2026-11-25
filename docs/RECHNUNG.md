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
- Historie: geholt wird bis zum gleichen Tag des Vorjahres wie der Beginn der laufenden Periode (mindestens 400, höchstens 800 Tage), damit „Vorjahr bisher“ vollständig ist.
- Tageswerte kommen aus der Summe der HA-Statistik. Ist der Zählerstand an einem Tag weniger gestiegen als die Summe (Sensor kurz auf 0 und zurück), gilt der Zählerstand (Hinweis `statistik_sprung`).
- Rückfall 1: Durchschnitt seit Periodenbeginn × Resttage (ab 30 Tagen, „vorläufig“).
- Rückfall 2: Jahresverbrauch laut letzter Rechnung tagesanteilig („Annahme“). Eine Verteilung nach Standardlastprofil folgt später.
- **Wallbox**: Ein Unterzähler hinter dem Hausstromzähler, ohne eigenen Vertrag und ohne eigene Kosten. Kosten, Abschläge und Saldo bleiben beim Hauptzähler, denn bezahlt wird, was der Hauptzähler zählt. Getrennt wird nur die **Prognose**: Wallbox-Tageswerte werden vor der Grundlast-Prognose abgezogen, damit Ladetage den Vorjahresvergleich nicht verzerren. Die Grundlast folgt dem Vorjahr, die Wallbox ihrem Mittel der letzten 30 Tage (mindestens 14 Tage mit Werten, sonst wird nicht getrennt); beide Reste werden addiert (Attribut `wallbox_rest`). Abgezogen und fortgeschrieben wird je Tag höchstens, was der Hauptzähler bezogen hat: Lädt die Wallbox mit PV, zählt sie mehr als den Netzbezug; der Überschuss geht nicht ab (Hinweis `wallbox_mehr_als_bezug`). So erkennt die Prognose auch einen neuen Verbraucher, den es im Vorjahr noch nicht gab: Die Grundlast kommt aus dem Vorjahr, das Laden aus den letzten 30 Tagen der Wallbox. Tage ohne Wallbox-Wert zählen ganz zur Grundlast (Hinweis `wallbox_luecken`). Lädt die Wallbox überwiegend PV-Strom, ist das richtig so: Nur der Netzbezug am Hauptzähler kostet Geld. Ein eigener Wallbox-Tarif mit eigenem Zähler (z. B. § 14a mit separatem Zähler) wird stattdessen als eigener Hauptzähler mit Vertrag angelegt.
- **Gartenwasser**: geht weder bisher noch in der Prognose ins Abwasser; der Gartenzähler wird wie die Wallbox fortgeschrieben.

**Gas und Fernwärme**

`Rest = Kennwert × Rest-Gradtage (+ Warmwasser-Grundlast × Resttage)`

- Rest-Gradtage (ab 1.0): für die nächsten Tage aus der **Wettervorhersage** der Wetter-Entität (Tagesmittel aus Höchst- und Tiefstwert, mit Heizgrenze und Innenbezug des Haushalts), danach das **Mittel gleicher Kalendertage** der letzten bis zu drei Jahre; gibt es nur ein Jahr, das Vorjahr. Ein Jahr zählt, wenn mindestens 50 % seiner Tage vorhanden sind; Lücken werden hochgerechnet. Attribute `quelle` (`vorhersage+mittel`, `mittel`, `vorjahr` …) und `vorhersage_tage`.
- **Band:** Ab zwei Vorjahren zusätzlich die Restmenge wie im kältesten bzw. wärmsten dieser Jahre (`rest_kalt`, `rest_warm`, ohne Vorhersage), daraus Prognose-Kosten und Saldo für beide Fälle (gleiche Preise, gleiche Tagesverteilung).
- Kennwert und Warmwasser-Grundlast aus der Regression `V = WW × Tage + Kennwert × Gradtage` über die letzten 365 Tage (Tage bei Zählern mit Sensor, Ableseperioden bei Ablesungen). Warmwasser wird nur getrennt geschätzt, wenn es Tage ohne Heizbedarf gibt; sonst steckt es im Kennwert.
- Qualität: „unzureichend“ (unter 21 Tagen bzw. 4 Perioden oder unter 5 K Spanne oder R² < 0,6), „vorläufig“ (R² ≥ 0,6), „gut“ (R² ≥ 0,8 und mindestens 42 Tage bzw. 6 Perioden), „sehr gut“ (mindestens 90 Tage, 10 K Spanne, R² ≥ 0,85).
- **Unter „vorläufig“ gibt es keine Prognose**; eine Kennwert-Annahme wird nicht verwendet.

### Wärme mit Wärmeerzeugern (0.8)

Die Regression ist ab 0.8 allgemein (kleinste Quadrate mit beliebig vielen Regressoren, ohne Achsenabschnitt):

`V = WW × Tage + Kennwert × Gradtage − Ofen-Effekt × Ofenstunden − Entlastung × Klima-Strom`

- **Warmwasser:** Der WW-Term wird nur geschätzt, wenn Warmwasser über diese Heizung läuft (Antwort „über die Heizung“ oder „Solarthermie (unterstützend)“, oder ein Wärmeerzeuger mit „macht zentrales Warmwasser“ an diesem Zähler) und es Sommertage gibt. Sonst ist er 0 (Hinweis `ww_aus`). Ohne Antwort (Haushalt aus 0.6) bleibt es wie bisher.
- **Vergleichstage (Entscheidung C):** Ein eigener Ofen- oder Klima-Term wird erst geschätzt, wenn es je mindestens 10 Heiztage mit und ohne Betrieb gibt, zu denen ein Tag der anderen Gruppe mit ähnlichen Gradtagen (± 2 Kd) existiert. Vorher:
  - Kaminofen: Annahme `Ofenstunden × Nennleistung × wirksamer Anteil ÷ 0,9 × Hs/Hi` wird zum Gasverbrauch addiert, damit der Kennwert den Bedarf ohne Ofen beschreibt. Qualität des Ofen-Effekts: „Annahme“.
  - Split-Klima/Wärmepumpe: Klimatage werden aus der Schätzung herausgenommen, wenn danach noch mindestens 21 Tage mit 5 K Temperaturspanne übrig bleiben; eine Entlastung gibt es nicht.
  - Gibt es genug Vergleichstage, aber der gelernte Ofen-Effekt ist nicht positiv, gilt: kein messbarer Effekt. Der Ofen-Effekt ist dann 0 (Hinweis `ofen_kein_effekt`), eine Annahme wird nicht mehr angesetzt. Beim Klima entsprechend `klima_kein_effekt`.
  - **Fehlend ist nicht 0 (Regel 5):** Ofenstunden gibt es erst ab der Einrichtung (und für die wenigen Tage, die der Recorder im Verlauf hält). Heiztage ohne bekannte Ofenstunden (bzw. Klima-Energie) werden aus der Schätzung herausgenommen, wenn genug Tage übrig bleiben (Hinweis `ofen_unbekannte_tage_ausgeschlossen`); sonst zählen sie als „ohne Ofen“ und das wird gekennzeichnet (`ofen_stunden_unvollstaendig`). Die Rate für die Restprognose zählt nur Tage mit bekanntem Wert.
  - Außerhalb der Heizperiode zählt Klima-Strom nicht (das Gerät kühlt dann).
- **Ofen, der zusätzlich heizt (1.2.8):** Ist beim Kaminofen „Ofen entlastet die Heizung“ aus (der Raum wird bewusst überheizt), wird seine Wärme nie dem Gas zugerechnet: keine Annahme, kein gelernter Ofen-Term, keine Entlastung in der Restprognose. Der Kennwert beschreibt dann nur die Heizung. Ofenstunden, Holz und Holzkosten bleiben; die Entlastung des Ofens bleibt leer (Hinweis `entlastet_heizung_nicht`).
- **Temperaturbereinigter Kennwert ohne Ofentage (1.2.8):** Tage, an denen irgendein Ofen lief, zählen nicht für den Kennwert mit Gradtagen aus der Innentemperatur und nicht für die Aufteilung zum Vorjahr – der Ofen hebt die Raumtemperatur, ohne dass die Heizung diese Wärme liefert.
- **Restprognose:** `(Kennwert − Entlastung je Gradtag) × Rest-Gradtage + WW × Resttage`. Entlastung je Gradtag = Ofenstunden (bzw. Klima-Strom) je Gradtag der laufenden Periode (unter 50 Gradtagen: gleiches Fenster im Vorjahr) × Ofen-Effekt (bzw. gelernte Entlastung je kWh).
- **Heizen am Haushaltsstrom:** Mit eigener Messung zählt deren Tagesenergie als Unterzähler (wie die Wallbox) und wird über eine eigene Gradtag-Regression `E = a × Tage + b × Gradtage` fortgeschrieben. Ohne Messung wird der Hausstrom selbst regressiert (`V = Grundlast × Tage + b × Gradtage`); `b × Gradtage` wird vor der Grundlast-Prognose abgezogen und als `b × Rest-Gradtage` wieder addiert, nur mit einem Modell ab „vorläufig“ (sonst `heizstrom_nicht_getrennt`). Eine Wärmepumpe am eigenen Zähler (WP-Tarif) läuft ganz über diese Regression: Der Zähler gilt komplett als Heizstrom, die Prognose ist die Gradtag-Prognose mit deren Qualität (Methode `waermepumpe_waerme`), ohne Grundlast oder Jahresverbrauch.
- **Umrechnungswege (Typschild):** Nennwärmebelastung × Hs/Hi = Gaseinsatz nach Brennwert; Nennwärmeleistung ÷ Wirkungsgrad × Hs/Hi. Hs/Hi = 1,11, Wirkungsgrad Therme 0,9 (Annahmen).
- **Erzeuger-Tageswerte** (Entscheidung I): eingesetzte Energie (Energie-Entität, sonst eigener Zähler, sonst Leistung × 24 h, beim Ofen Stunden × Nennleistung ÷ Wirkungsgrad als Annahme), gemessene Wärme (nur Wärmemengenzähler), geschätzte Wärme (Strom × COP, Ofenstunden × Nennleistung × wirksamer Anteil, Gas ÷ Hs/Hi × Wirkungsgrad) und Entlastung (nur aus dem Modell, und nur wenn das Wärmemodell mindestens „vorläufig“ ist) bleiben getrennt.
- **Holz (Schätzung):** kg = eingesetzte Energie ÷ 4,2 kWh/kg; Kosten = kg × Preis je kg bzw. Preis je Raummeter ÷ kg je Raummeter (Annahme 400 kg).
- **Gewogenes Holz (1.2.2):** Mit der Aktion `holz_erfassen` trägst du die Holzmenge eines Tages ein (kg, oder Scheite × kg je Scheit).
  - An gewogenen Tagen: eingesetzte Energie = kg × 4,2 kWh/kg (Qualität „geschätzt“: die Menge ist gemessen, der Heizwert angenommen). Die geschätzte Wärme bleibt wie bisher die wirksame Wärme: Energie × Wirkungsgrad (Standard 0,75) × wirksamer Anteil. 0 kg heißt: an dem Tag kein Holz. „Tag ersetzen“ ohne Menge entfernt die Einträge des Tages, er gilt dann wieder als nicht gewogen.
  - **Gelernte Menge je Brennstunde:** Summe kg ÷ Summe Brennstunden über alle Tage mit Holz und mindestens 1 Brennstunde (Tage mit 0 kg zählen nicht). Ab 3 solchen Tagen „vorläufig“, ab 7 „gut“. Ofenleistung (Wärme je Brennstunde) = kg je Brennstunde × 4,2 kWh/kg × Wirkungsgrad.
  - An Tagen mit Brennstunden, aber ohne Eintrag, ersetzt die gelernte Menge die Annahme aus der Nennleistung: Energie = Stunden × kg je Brennstunde × 4,2, Wärme = Energie × Wirkungsgrad × wirksamer Anteil. Solange die Rate „vorläufig“ ist, bleiben diese Tage als Annahme gekennzeichnet, ab „gut“ als Schätzung. Eigene Messungen (Energie-Entität, Wärmemengenzähler) gehen immer vor.
  - Die Annahme für die Entlastung der Heizung (bis die Regression den Ofen-Effekt gelernt hat) nimmt dann die gelernte Ofenleistung statt der Nennleistung: Ofenleistung × wirksamer Anteil (bei Gas ÷ 0,9 × Hs/Hi). Sobald der Ofen-Effekt gelernt ist, zählt nur noch er (Regel 10).
  - Ein Eintrag für heute zählt ab morgen mit, weil die Brennstunden eines Tages erst nach Tagesende feststehen.
  - Beispiel: 45 kg an drei Tagen mit 15 Brennstunden → 3 kg je Brennstunde → 3 × 4,2 × 0,75 = 9,45 kW Ofenleistung; mit wirksamem Anteil 0,6 entlastet das die Heizung um 5,7 kWh Wärme je Brennstunde.
- **Innentemperatur:** (nur wenn auch das Modell mit Außentemperatur mindestens „vorläufig“ ist) zweiter Kennwert mit Gradtagen aus dem gemessenen Tagesmittel innen (innen − außen an Heiztagen). %/K = 100 ÷ mittlere Differenz innen–außen an Heiztagen, gelernt erst ab „vorläufig“ und 60 Tagen mit Innentemperatur, sonst 6 %/K als Annahme. Die Aufteilung gegenüber dem Vorjahr („+8 %: +3 % Raumtemperatur, +5 % Mehrverbrauch“) gibt es nur mit gelerntem %/K und je 60 Heiztagen mit Innentemperatur in beiden Fenstern.
- **Fernwärme:** wie Gas; Arbeitspreis wahlweise je MWh (intern je kWh), Leistungspreis × Anschlussleistung tagesgenau, Messpreis je Monat.

### Impulszähler und Abgleich (0.9)

- **Impulse → Zählereinheit:** Menge je Impuls = 1 ÷ (Impulse je Einheit) bzw. die Einheit je Impuls. Startet der Zähler neu (Stand fällt auf 0), merkt sich die Integration den Stand davor dauerhaft und zählt ab dort weiter, für Tageswerte, aktuellen Stand und gemerkte Sensorstände gleich. Erkannt wird ein Neustart live, in der Statistik und zwischen zwei Läufen (erster Stand unter dem Stand am Ende des Vortags). Ohne Langzeitstatistik (z. B. Zähler-Helfer) kommen die Stundenwerte aus dem Verlauf; den hält der Recorder nur einige Tage.
- **Abgleich** je Intervall zwischen zwei gültigen, echten Ablesungen (geschätzte Ablesungen, z. B. Schätzungen des Versorgers, gleichen nichts an): abgelesene Menge ΔA, gemessene Menge ΔS (Sensorstand zu beiden Ablesezeitpunkten: gemerkter Stand der Ablesung, sonst Stand am Ende des Vortags + Anteil des Tages). Faktor = ΔA ÷ ΔS, Abweichung = (ΔS ÷ ΔA − 1) × 100 %, fehlende Menge = ΔA − ΔS.
  - Angleichen: Tageswerte, deren Tagesmitte im Intervall liegt, werden mit dem Faktor multipliziert (Qualität „geschätzt“, Rohwert bleibt gespeichert, bei jeder neuen Ablesung neu gerechnet). Fehlende Tage bleiben fehlend; decken die vorhandenen Tage weniger als 80 % ab, wird nicht angeglichen.
  - Über 30 % Abweichung gilt als Fehler (falsche Ablesung, Zählertausch, falsche Konstante): nicht angleichen, nur melden.
  - Hinweis unter Reparaturen ab 2 % im letzten Intervall.
  - Offset nach der letzten plausiblen Ablesung (nicht nach einem Ausreißer) = Ablesung − Sensorstand, beide über einen Zählertausch durchlaufend; kommt der Startwert der Periode aus einer Ablesung, ist der aktuelle Stand = Sensor + Offset. Kommt er aus der Statistik, gelten die angeglichenen Tageswerte bis gestern plus der Sensor seit gestern.
  - Angeglichen werden alle Intervalle, auch ältere (Vorjahr): Nach dem Update können sich historische Tageswerte und „Kosten bisher“ ändern. Beendete, eingefrorene Perioden bleiben unberührt.
- **Gasleistung:** Δm³ ÷ Δt zwischen den letzten beiden Impulsen × Brennwert × Zustandszahl; kommt `max_gap` lang kein Impuls, ist sie 0.
- **Brennerlaufzeit und Starts:** Abschnitte zwischen Impulsen mit höchstens `max_gap` Abstand zählen als Betrieb (`max_gap` = 1,5 × Impulsabstand bei kleinster Leistung, mindestens 6 Minuten; ohne Gastherme mit kleinster Leistung 3 kW angenommen). Der erste Impuls nach einer Pause ist ein Start; ein Lauf aus nur einem Impuls zählt mit der Laufzeit eines Impulses bei kleinster Leistung. Läufe über Mitternacht werden geteilt, der Start zählt am Tag, an dem er begann. Nur für Tage, die der Recorder-Verlauf noch hat; ohne Impulse an einem Tag mit Verbrauch bleiben die Werte leer.
- **Takten:** mittlere Leistung im Betrieb höchstens 120 % der kleinsten Modulationsleistung der Gastherme (als Gaseinsatz nach Brennwert: Belastung × Hs/Hi bzw. Leistung ÷ Wirkungsgrad × Hs/Hi) und mehr als 3 Starts je Betriebsstunde, bei mindestens 30 Minuten Betrieb.

## Ergebnis

- `Prognose Kosten = Kosten bisher + Kosten der Restmenge + Grundpreis bis Periodenende`
- `Saldo = Abschläge der Periode − Prognose Kosten` (positiv: Rückzahlung)
- Urteil „passt“, wenn |Saldo| unter der Toleranz liegt (Feld „Genauigkeit der Prognose“, Standard 5 % der Abschläge der Periode; bei 1.200 € Abschlägen also bis 60 €).
- `Abschlag empfohlen = (Prognose Kosten − schon gezahlt − geplante Einmalzahlungen) / offene Abschläge`, aufgerundet, ab dem nächsten Zahltag.
- `Abschlag passend = Prognose Kosten / Anzahl Abschläge der Periode` (wie bisher in den Template-Sensoren).
- Prognose-Schnappschüsse werden am 1. jedes Monats und beim Wechsel in die nächste Periode (letzter Stand der beendeten Periode) eingefroren.
- Ist der Zählerstand-Sensor gerade nicht verfügbar, gilt der Stand vom Ende des Vortags aus der Statistik; fehlt auch der, gibt es keine Kosten (nie still der Startstand).

## Archiv und Prognose gegen Realität (1.0)

- **Schnappschüsse:** am 1. jedes Monats und beim Periodenwechsel (erster Lauf der neuen Periode, mit dem letzten Ergebnis der alten): Prognose Menge und Kosten, Qualität, empfohlener Abschlag, Saldo und Urteil.
- **Vorläufiges Archiv** beim Periodenwechsel bzw. beim nächsten täglichen Lauf: Kosten (gesamt, Arbeit, Grund, fest, Leistung, Abwasser), Menge, Zahlungen (Summe, Einzelposten), Saldo, Urteil, Preise des Vertrags und alle Schnappschüsse der Periode. Gerechnet wird zum Periodenende.
- **Endgültig** (Status `closed`), wenn eine echte, gültige Ablesung am Periodenende oder bis 11 Tage danach liegt (die früheste wird `end_reading`) oder eine Rechnung des Vertrags die Periode abdeckt, frühestens aber 11 Tage nach dem Ende: Bis dahin darf das Ende mit `set_periodenende` noch verschoben werden, das Archiv bleibt vorläufig und wird täglich neu gerechnet. Spätestens 60 Tage nach dem Ende wird immer abgeschlossen; fehlt der Endstand, mit den Kosten bis zum letzten bekannten Tag (`tageswerte_bis`). Danach wird nichts mehr neu gerechnet; `set_periodenende` lehnt die Periode ab.
- Eine Ablesung vor dem Periodenende schließt nicht ab (der Verbrauch bis zum Ende fehlt). Liest der Versorger früher ab, zuerst `set_periodenende` auf den Ablesetag setzen.
- Mit unvollständigen Ist-Kosten bleibt die Abweichung leer; die Karte kennzeichnet die Ist-Kosten als unvollständig.
- **Prognose gegen Realität:** je Schnappschuss `Abweichung = Prognose Kosten − tatsächliche Kosten` in € und %. Positiv = zu teuer geschätzt.

## Jahresabrechnung und Kalibrieren (1.1)

Eine Rechnung erfasst du am Zähler unter **Neu konfigurieren → Rechnung erfassen** oder mit `tarif_cockpit.add_rechnung`. Pflicht sind Zeitraum und Betrag (Gesamtkosten brutto). Alles Weitere ist optional und hilft beim Vergleich: Anfangs- und Endstand, Menge (Zählereinheit oder kWh), Brennwert, Zustandszahl, Kosten von Arbeits- und Grundpreis, gezahlte Abschläge.

- **Stände werden Ablesungen** mit der Quelle „Rechnung“: Anfangsstand zum Beginn, Endstand zum Ende des Zeitraums (24 Uhr), echt oder geschätzt. Ein gleicher Stand am selben Tag wird nicht doppelt angelegt.
- **Alte Rechnungen vor dem Vertragsbeginn** hängen nur am Zähler. Sie haben keine Kosten im Vergleich, dienen aber als Lerndaten und prüfen die Ersatzquelle.
- **Vergleich:** Menge der eigenen Tageswerte im Rechnungszeitraum, getrennt nach Quelle (Zählersensor, Ersatzquelle, Ablesungen). Verglichen wird ab 90 % Abdeckung; fehlende Tage werden hochgerechnet (nie als 0), ein Vorschlag für die Ersatzquelle kommt erst ab 98 %. Die Kosten werden mit der Menge der Rechnung und den eigenen Preisen gerechnet (bei einer Gesamtstaffel mit der Menge der Rechnung), damit Preisfehler und Mengenfehler getrennt sichtbar werden.
- **Stände prüfen:** Endstand unter Anfangsstand und ein Endstand zu einem Rechnungsende in der Zukunft werden abgelehnt. Liegt am selben Tag schon eine echte Ablesung, wird ein geschätzter Rechnungsstand nicht angelegt.
- **Startwert bei Zählern mit Sensor:** Eine Ablesung am Periodenbeginn (oder zwischen Ablesungen, die höchstens zwei Tage auseinander liegen) gilt. Liegen die Ablesungen weiter auseinander (z. B. Endstand einer alten Rechnung und eine Ablesung Monate später), kommt der Startwert aus der Statistik statt aus einer Geraden.
- **Vorschläge**, die du unter **Einstellungen → Reparaturen** mit „OK“ übernimmst:

| Vorschlag | Wann | Wirkung nach dem Übernehmen |
|---|---|---|
| Brennwert, Zustandszahl | Gas in m³, Wert der Rechnung weicht um mehr als 0,5 % ab | gilt für genau den Rechnungszeitraum, vor dem Preisabschnitt und dem Zähler |
| Faktor Ersatzquelle | die Ersatzquelle trägt mindestens die Hälfte der Menge und die Menge weicht mehr als die Toleranz ab | `Faktor = (Rechnung − Zähler − Ablesungen) / Ersatzquelle` gegen die unveränderten Werte, begrenzt auf 0,8 … 1,25; gilt für Tageswerte der Ersatzquelle ab dem Rechnungsbeginn bis zum Beginn der nächsten übernommenen Rechnung (Ist-Menge, Vorjahr, Prognose) |

- Weicht nur der Preis ab (Arbeitspreis, Grundpreis oder Gesamtbetrag über 1 € und über der Toleranz), erscheint ein **Hinweis ohne Knopf**. Preise änderst du selbst unter „Preis ändern“, auch Staffel und Rundung. Weicht die Menge bei Zählersensor oder Ablesungen ab, lautet der Hinweis „Ablesungen prüfen“ (der Abgleich aus 0.9 gleicht den Sensor an echte Ablesungen an).
- **Abgeschlossene Perioden** bleiben unverändert (Regel 4); Kalibrierungen wirken auf laufende und vorläufig archivierte Perioden. Eine Korrektur-Rechnung (`korrigiert`) nimmt die Kalibrierungen der korrigierten Rechnung zurück.
- Brennwert-Vorschläge gibt es nur für Rechnungen mit Vertrag (vorher gibt es keinen Preis, den der Brennwert ändern würde).
- Event `tarif_cockpit_rechnung_abweichung` je Rechnung einmal, mit `vorschlaege` und `hinweise`.

**Lerndaten:** Bei Zählern ohne Sensor ist jede Ableseperiode der letzten **3 Jahre** eine Stichprobe des Wärmemodells, auch vor dem Vertragsbeginn. Rechnungen mit Menge, aber ohne Stände, zählen als eigener Zeitraum (bei Gas in m³ mit dem Brennwert der Rechnung umgerechnet). Ein Zeitraum, der sich mit Ableseperioden überschneidet, zählt nicht doppelt. Die Gradtage dafür holt die Aggregation bis zum frühesten Rechnungs- bzw. Ablesebeginn, höchstens 3 Jahre und soweit die Statistik der Außentemperatur reicht.

## Staffel und Rundung (1.1)

- **Staffel:** bis zu drei Stufen je Jahr (im Dialog), beliebig viele über `set_preis` (`staffel: [{bis: 1000, preis: 0.32}, {preis: 0.29}]`). Ein Rumpfjahr bekommt die Grenzen anteilig (Tage ÷ 365). Bezug ist die Menge der Periode.
  - `block`: jede Stufe zum eigenen Preis. Die Menge vor dem Rest der Periode zählt mit, die Prognose setzt also dort fort, wo der bisherige Verbrauch steht.
  - `total`: die ganze Menge zum Preis der erreichten Stufe, gemessen an der Prognose der ganzen Periode.
- **Rundung** je Preisabschnitt:
  - Tage je Jahr 365,25 (wie bisher), 365 oder die echten Tage (365/366),
  - Grundpreis je Tag (`Monatspreis × 12 ÷ Tage je Jahr`) oder je Monat (`Monatspreis ÷ Tage des Monats` je Tag, ein voller Monat ist genau ein Monatspreis),
  - Menge je Preisstufe auf n Stellen,
  - Beträge je Position auf n Stellen (2 = Cent).
- Beispiel (Test): 3.342 kWh zu 31,54 ct, Grundpreis 13,09 € je Monat, Menge auf ganze kWh, Beträge auf Cent, Grundpreis je Monat → 1.054,07 € + 157,08 € = 1.211,15 €.
- Über der letzten Stufe ohne „darüber“ gilt der Arbeitspreis des Abschnitts. Eine Gesamtstaffel braucht die Menge der ganzen Periode; ohne Prognose gelten die Kosten als unvollständig (`staffel_ohne_gesamtmenge`).
- „Preis ändern“ ohne Haken übernimmt die Rundung des laufenden Preises; hat er eine Staffel, folgt der Staffel-Schritt immer (vorbelegt), weil die Stufenpreise den Arbeitspreis bestimmen. Die Aktion `set_preis` legt den Abschnitt so an, wie sie aufgerufen wird (ohne `staffel` keine Staffel).

## Prognosegüte (1.1)

Aus den abgeschlossenen Archiven: je Vorlauf (Monate vor dem Periodenende) die **mittlere absolute Abweichung** der Prognose von den tatsächlichen Kosten und der tatsächlichen Menge, über alle abgeschlossenen Perioden. Mit einer Periode „vorläufig“, ab zwei „gut“. Attribut `prognoseguete` am Sensor Prognose-Qualität, Tabelle in der Auswertungskarte.

## Heizlast (1.1)

Aus dem gelernten Kennwert k (kWh je Gradtag, bei Gas Brennwert Hs) und dem Wirkungsgrad η des Kessels:

- `Heizlast = k × Hi/Hs × η × (Innenbezug − Normaußentemperatur) / 24 h` (Hi/Hs = 0,901 bei Gas, Fernwärme ohne Umrechnung). Warmwasser gehört nicht dazu.
- `Verhältnis = Nennleistung ÷ Heizlast`: bis 1,2 passend, bis 1,8 etwas groß, darüber überdimensioniert. Eine Nennleistung als „Belastung“ wird mit η auf Wärme umgerechnet.
- `Taktgrenze = Innenbezug − kleinste Leistung × 24 / (k × Hi/Hs × η)`: Über dieser Außentemperatur liegt der Bedarf unter der kleinsten Leistung, der Kessel muss takten. **Takttage** = Anteil der Heiztage (unter der Heizgrenze) im letzten Jahr, die wärmer waren.
- Mit Impulszähler zusätzlich die höchste gemessene Brennerleistung im Tagesmittel.
- Ohne Kennwert ab „vorläufig“ gibt es keine Aussage. Beispiel: k = 5 kWh/Kd, η 0,97, 20 °C, −12 °C → 5,8 kW Heizlast; ein Kessel mit 19,5 kW ist 3,3-fach überdimensioniert, mit 4,7 kW kleinster Leistung liegt die Taktgrenze bei −5,8 °C.

## Zeitfenster, § 14a, dynamischer Tarif (1.2)

**Zeitscheiben:** Der Tageswert wird verteilt.
1. Auf Viertelstunden aus der 5-Minuten-Statistik, nur für Zähler mit dynamischem Tarif oder Vergleich; der Recorder hält sie etwa 10 Tage, sie werden täglich gesichert.
2. Sonst auf die Stundenwerte des Tages, für alle Zähler mit Sensor, 400 Tage.
3. Sonst über das typische Tagesprofil der letzten 30 Tage, gekennzeichnet `fenster_geschaetzt`.
4. Sonst gleichmäßig.

Die Scheiben werden immer auf den Tageswert skaliert. Der Tageswert bleibt maßgeblich, auch nach dem Abgleich.
Viertelstunden gelten nur, wenn sie zu den sprungbereinigten Stundenwerten passen (je Stunde höchstens 5 % Abweichung), sonst gelten die Stunden.
`fenster_geschaetzt` steht nur an vergangenen Tagen. Heute und in der Zukunft gibt es noch keine Stundenwerte, das ist kein Mangel.

**Preis einer Scheibe** (Beginn in Ortszeit) = absoluter Fensterpreis (HT), sonst dynamischer Preis + Aufschlag, sonst Arbeitspreis (NT); dazu die Zu- und Abschläge aller passenden Fenster (§ 14a Modul 3).
Der Wochentag eines Fensters über Mitternacht ist der des Scheibenbeginns: Ein Fenster 22–6 Uhr „Mo–Fr“ gilt Freitagnacht ab 22 Uhr, aber nicht Samstag 0–6 Uhr. Für alle Nächte alle Wochentage wählen.
- **HT/NT:** Der Arbeitspreis des Abschnitts gilt als NT, das Fenster „HT“ (Zeit, Wochentage) mit eigenem Preis.
- **§ 14a Modul 1:** Pauschale je Jahr, läuft anteilig mit (`rebate`, mindert die Kosten).
- **Modul 2:** eigener Zähler mit eigenem Vertrag und reduziertem Preis.
- **Modul 3:** Fenster mit Zu- bzw. Abschlag in ct/kWh in bestimmten Quartalen.
- **Dynamisch:** Preis je Viertelstunde aus einer Entität.
  - Quelle: erst die Preisliste im Attribut (EPEX `data`, Tibber `today`/`prices`), sonst der Verlauf des Zustands (Wert in der Mitte der Viertelstunde), sonst das Stundenmittel der Statistik.
  - Einheit ct oder € automatisch, aus dem Schlüssel (`price_ct_per_kwh`) bzw. der Einheit des Zustands. Ein Mittel über 2 €/kWh gilt als Cent.
  - **MwSt.:** Ist der Preis der Entität netto (EPEX Market Price; Kästchen „ohne MwSt.“, Standard an), kommt bei Brutto-Verträgen die MwSt. dazu. Der Aufschlag gilt in der Preisart des Vertrags.
  - Für Stunden gilt das Mittel der vier Viertelstunden. Fehlt ein Preis, das Mittel des Tages (`preis_geschaetzt`).
  - Prognose-Rest: mit dem mengengewichteten Börsenpreis der letzten 30 Tage plus Aufschlag (`dynamisch_mittel`), höchstens „vorläufig“.
- Staffel und Fenster werden nicht kombiniert; mit Fenstern gilt der Fensterpreis.

## Vergleich dynamischer Tarif (1.2)

Am Stromzähler unter Stammdaten: Preis-Entität (z. B. EPEX Spot Market Price), Aufschlag in ct/kWh (Netzentgelt, Steuern, Marge) und Grundpreis des Angebots. Verglichen wird nur über Tage mit Preisen je Viertelstunde:

`Differenz = (eigener Arbeitspreis × Menge + eigener Grund- und Messpreis) − (Σ Menge je Scheibe × (Preis + Aufschlag) + Grundpreis des Angebots)`

Messpreis und § 14a-Pauschale des eigenen Abschnitts gelten auf beiden Seiten (Messstelle und Netz bleiben gleich). Verglichen werden nur Tage mit mindestens 75 % Viertelstundenpreisen. Hat der eigene Vertrag selbst einen dynamischen Preis, rechnet die eigene Seite mit dessen Preisen.

Positiv heißt: Dynamisch wäre günstiger gewesen. Hochrechnung auf die Periode = Differenz je kWh × Prognose-Menge (`hochgerechnet`). Tage, die nur Stundenwerte haben, sind gekennzeichnet (`teils_stuendlich`).

## Kühlgradtage (1.2)

`Kühlgradtage = Tagesmittel − Kühlgrenze`, wenn das Tagesmittel darüber liegt (Standard 22 °C, im Haushalt änderbar), sonst 0.
- **Klimagerät am Hausstrom mit eigener Messung:** Kühlkennwert = Energie an Kühltagen über dem Median der Tage ohne Heizen und Kühlen, geteilt durch die Kühlgradtage der letzten 365 Tage. Nötig sind mindestens 20 Kd an 10 Tagen.
- Rest = Kennwert × erwartete Kühlgradtage (Mittel gleicher Kalendertage der Vorjahre). Er wird wie der Heizstrom vor der Grundlast getrennt (`kuehlen_rest`).
- Kühltage zählen nicht in die Heiz-Regression.
- Ohne Messung wird Kühlen nicht geschätzt (`kuehlen_nicht_getrennt`).

## Leckage (1.2)

Wasserzähler mit Sensor, aus den Stundenwerten von gestern und den Tagen davor (Gartenwasser abgezogen):
- **Nachtminimum:** kleinster Stundenverbrauch zwischen 1 und 5 Uhr in drei Nächten hintereinander über der Schwelle (Standard 5 L/h, unter Stammdaten änderbar).
- **Dauerfluss:** an zwei Tagen hintereinander in jeder Stunde mindestens 1 L (Rauschen und Rundung zählen nicht).
- Gibt es einen Gartenzähler, aber an einem Tag keine vollständigen Stundenwerte von ihm, ist der Tag nicht prüfbar (nächtliche Bewässerung).

Ein Tag ohne vollständige Stundenwerte unterbricht die Folge. Bei Verdacht gibt es einen Hinweis unter Reparaturen und den binären Sensor „Leckage-Verdacht“. Das Event `tarif_cockpit_leckage` kommt einmal, solange der Verdacht anhält.

## Kündigungsfrist (1.0)

- Mit festem Vertragsende: letzter Kündigungstag = Vertragsende − Kündigungsfrist (Wochen).
- Mit Mindestlaufzeit: Ende der Mindestlaufzeit = Vertragsbeginn + Monate − 1 Tag, davon die Frist abgezogen. Ist die Mindestlaufzeit vorbei, ist der Vertrag jederzeit mit der Frist kündbar (`nach_mindestlaufzeit`, kein Termin).
- Ohne Frist bzw. Laufzeit kein Termin (`keine_angaben`). Hinweis unter Reparaturen ab 28 Tagen vorher, Event 28 Tage vorher und am letzten Tag (je Frist nur einmal, auch über Neustarts). Die Karte zeigt den Hinweis ab sechs Wochen (Attribut `kuendigung_hinweis`).
- Mindestlaufzeit: Ende = Vertragsbeginn + Monate − 1 Tag; fehlt der Tag im Zielmonat (Beginn 31.01., 1 Monat), endet sie am Monatsletzten (§ 188 BGB).

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
