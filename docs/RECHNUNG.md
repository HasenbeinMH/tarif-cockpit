# Rechnung

Formeln und Regeln des Rechenkerns (`custom_components/tarif_cockpit/engine/`). Stand 0.5: Tageswerte, Gradtage, Perioden. Kosten, Prognose und Urteil folgen in 0.6 und werden hier ergänzt.

## Tageswerte aus der Langzeitstatistik

Für einen Zähler mit Sensor liest die Integration die Stundenwerte der Langzeitstatistik (laufende Summe):

`Verbrauch(Tag) = Summe am Ende der letzten Stunde des Tages − Summe am Ende der letzten Stunde des Vortags`

- Tage werden in der Zeitzone von Home Assistant gebildet. Die Tage der Zeitumstellung haben 23 bzw. 25 Stunden und werden richtig gezählt.
- Lücken innerhalb des Tages schaden nicht, weil die Summe durchläuft. Fehlt einer der beiden Randwerte, ist der Tag `missing`.
- Läuft der Zählerstand rückwärts (ohne erfassten Zählertausch), ist der Tag `invalid`.
- Liefert der Sensor eine andere Einheit derselben Art (z. B. Wh statt kWh), rechnet die Statistik sie in die Einheit des Zählers um.
- In Zeitzonen, deren Mitternacht nicht auf einer vollen UTC-Stunde liegt (z. B. Indien, +5:30), gilt die letzte volle Stunde vor Mitternacht als Tagesgrenze; solche Tage sind `estimated`.
- Gerechnet wird in der Einheit des Zählers (kWh, m³). Die Umrechnung Gas m³ → kWh folgt in 0.6, weil sich Brennwert und Zustandszahl mit jeder Rechnung ändern können.

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
