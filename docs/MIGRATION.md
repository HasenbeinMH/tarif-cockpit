# Migration

## 0.9 → 1.0

Update einspielen, neu starten, Browser-Cache leeren. Umzustellen ist nichts.

- Bereits beendete Perioden werden beim ersten Start archiviert (endgültig, wenn eine Endablesung oder eine Rechnung vorliegt oder das Ende mehr als 60 Tage zurückliegt; fehlt der Endstand, mit den Kosten bis zum letzten bekannten Tag). Ältere Prognose-Schnappschüsse haben noch keinen Saldo.
- Mit Wetter-Entität im Haushalt holt die Integration alle 6 Stunden die Tagesvorhersage; die ersten Rest-Gradtage kommen dann aus ihr. Die Wärmeprognose kann sich dadurch leicht ändern.
- Mindestlaufzeit und Kündigungsfrist sind leer. Eintragen am Zähler: Neu konfigurieren → **Vertrag ändern**.

## Von 0.3 (Template-Sensoren) auf 1.0

Die Template-Version 0.3 rechnete mit Helfern (`input_number`, `input_datetime`), Template-Sensoren und einer täglichen Automation. 1.0 rechnet alles in der Integration. Die Werte aus den Helfern überträgt die Aktion `tarif_cockpit.uebernahme_v03`.

1. **Marketplace umstellen:** Ist Tarif-Cockpit noch als **Dashboard** eingetragen, entfernen und als **Integration** neu hinzufügen (siehe [0.4 → 0.5](#04--05-von-der-dashboard-karte-zur-integration)). Neu starten.
2. **Haushalt anlegen:** Einstellungen → Geräte & Dienste → Integration hinzufügen → Tarif-Cockpit. Außentemperatur und Wetter-Entität angeben, falls vorhanden.
3. **Zähler anlegen** (Strom, Gas, Wasser): Zählerstand-Sensor oder Impulszähler, Vertrag mit Abrechnungsbeginn und Regel. Preise und Abschlag kannst du grob eintragen; die Aktion überschreibt sie zum selben Datum. Hat der Sensor keine Jahreshistorie: **Ersatzquelle für fehlende Historie** (die Entität, aus der die alte Automation die Vorjahreswerte holte).
4. **Aktion aufrufen** je Zähler (Entwicklerwerkzeuge → Aktionen, YAML-Modus):
   ```yaml
   action: tarif_cockpit.uebernahme_v03
   data:
     zaehler: 1a2b3c…                                # Gerät „Gas“ des Tarif-Cockpits
     abschlag: input_number.abschlag_gas
     zahltag: input_number.zahltag_gas
     arbeitspreis: input_number.gas_arbeitspreis
     grundpreis: input_number.gas_grundpreis
     startstand: input_number.abrechnung_gas_startstand
     abrechnungsbeginn: input_datetime.abrechnung_gas_beginn
     brennwert: input_number.gas_brennwert
     zustandszahl: input_number.gas_zustandszahl
   ```
   Die Namen sind Beispiele; nimm deine Helfer. Alle Felder außer `zaehler` sind optional. Werte gelten ab `ab`, sonst ab dem Abrechnungsbeginn bzw. dem Beginn der laufenden Periode. Die Antwort listet, was übernommen und was übersprungen wurde (z. B. „kein Zahlenwert“, „schon vorhanden“, ein anderer Stand zum selben Zeitpunkt, Abrechnungsbeginn passt nicht zur Periode). Ein vorhandener Preisabschnitt wird ergänzt, nicht ersetzt: Fehlt der Grundpreis-Helfer, bleibt der Grundpreis aus der Einrichtung. Ein Startstand wird nie doppelt angelegt.
5. **Zwei Wochen Parallelbetrieb:** neue Sensoren (`sensor.<zähler>_kosten_bisher`, `_abschlage_bisher`, `_prognose_kosten`, `_saldo`) mit den Template-Sensoren vergleichen. Strom und Kosten sollten auf ±1 % passen. Gas zeigt erst eine Prognose, wenn ein eigener Kennwert gelernt ist (keine feste Annahme mehr).
6. **Abschalten**, wenn alles passt:
   - die tägliche Automation (Vorjahreswerte, Prognose),
   - die Template-Sensoren für Kosten, Abschläge, Prognose, Saldo und Kennwert,
   - die Helfer für Preise, Abschlag, Zahltag, Startstand, Abrechnungsbeginn, Brennwert und Zustandszahl,
   - eine Ablesung per Telegram o. Ä. auf `tarif_cockpit.add_ablesung` umstellen ([AUTOMATIONEN.md](AUTOMATIONEN.md#ablesung-per-telegram)).
7. **Karten:** `integration: true` in beiden Karten (siehe [0.6 → 0.7](#06--07-karte-auf-die-integration-umstellen)).

Preis- und Abschlagsänderungen laufen danach über „Neu konfigurieren“ am Zähler oder die Aktionen `set_preis` und `set_abschlag`.

## 0.8 → 0.9: Impulszähler und Abgleich

Update einspielen, neu starten, Browser-Cache leeren. Umzustellen ist nichts. Beim ersten Start gleicht die Integration alle Zähler mit Sensor mit den vorhandenen echten Ablesungen ab: Tageswerte (auch ältere) können sich dadurch ändern und als „geschätzt“ erscheinen, „Kosten bisher“ bezieht sich auf die letzte Ablesung. Beendete, eingefrorene Perioden bleiben unverändert.

Neu: Jeder Zähler mit Sensor wird mit deinen Ablesungen abgeglichen. Die Ablesung gilt; weicht der Sensor ab, werden die Tageswerte zwischen zwei Ablesungen angeglichen, und ab 2 % gibt es einen Hinweis unter Reparaturen. Wer bisher per Automation eine „Referenz“ bei jeder Ablesung setzt (z. B. Wechselrichter-Zähler gegen die Strom-Ablesung), braucht das für Tarif-Cockpit nicht mehr; abschalten erst nach einem Parallelbetrieb.

Impulszähler legst du beim Zähler über „Impulszähler“ an (bestehende Zähler: neu anlegen, weil die Quelle zum Zähler gehört).

## 0.7 → 0.8: Wärmeerzeuger (optional)

Update einspielen, neu starten, Browser-Cache leeren. Es ist nichts umzustellen: Einträge, Zähler und Karten laufen unverändert weiter.

Neu und optional: Beim Eintrag „Tarif-Cockpit“ → **Wärmeerzeuger hinzufügen** (Gastherme, Wärmepumpe, Split-Klima, Kaminofen …). Wer einen Kaminofen hat und dessen Betrieb schon über eine Entität erkennt (z. B. `binary_sensor.kaminofen_lauft`), wählt diese als Betriebszustand; die Integration zählt dann Ofenstunden und Ofentage selbst. Helfer und Automationen dafür werden später überflüssig; abschalten erst nach einem Parallelbetrieb. Ofenstunden gibt es ab der Einrichtung (plus die wenigen Tage, die der Recorder noch im Verlauf hat).

Geändert hat sich: Hast du beim Haushalt angegeben, dass Warmwasser nicht über die Heizung läuft (Durchlauferhitzer/Boiler oder Wärmepumpe; Solarthermie zählt als unterstützend, dort bleibt es wie bisher), schätzt die Gasregression keine Warmwasser-Grundlast mehr. Der Kennwert kann sich dadurch leicht ändern.

## 0.6 → 0.7: Karte auf die Integration umstellen

Update einspielen, Home Assistant neu starten, Browser-Cache leeren (Strg+F5). Der Eintrag wird automatisch auf 1.4 migriert; die Antworten zum Haushalt (Heizung, Warmwasser, PV/Speicher/Wallbox, Eigentümer/Mieter, Rhythmus) sind danach leer und lassen sich unter **Konfigurieren** am Eintrag nachtragen. Gespeicherte Zähler, Verträge, Ablesungen, Preise und Abschläge bleiben unverändert.

Die Karte stellst du am einfachsten im Editor um: Karte bearbeiten → Reiter **Integration** → Zähler wählen → Speichern. In YAML wird aus der langen Sensorliste:

```yaml
# vorher (0.6, Sensor-Modus mit den Sensoren der Integration)
type: custom:tarif-cockpit-card
strom:
  cost: sensor.strom_kosten_bisher
  advance_paid: sensor.strom_abschlage_bisher
  forecast_cost: sensor.strom_prognose_kosten
  advance: sensor.strom_abschlag
  months: 12
```

```yaml
# nachher
type: custom:tarif-cockpit-card
integration: true
```

Darstellungsoptionen (`title`, `theme`, `colors`, `advance_color`) bleiben. Neu: Urteil, Saldo und Prognose kommen direkt aus der Integration (auch bei Abschlagsstufen richtig), der empfohlene Abschlag und die Prognose-Qualität stehen in der Karte, und ein Tipp auf den Abschlag ändert ihn. Die Auswertungskarte entsprechend: `type: custom:tarif-cockpit-analyse-card` mit `integration: true`.

Ohne `integration: true` funktionieren beide Karten weiter im Sensor-Modus; dein bisheriges YAML bleibt gültig.

**Rechte:** Die Aktionen (`add_ablesung`, `set_abschlag` …) dürfen ab 0.7 nur Administratoren aufrufen. Automationen und Skripte laufen ohne Benutzer und sind nicht betroffen; ein Dashboard-Knopf, der eine Aktion direkt aufruft, funktioniert nur noch für Administratoren.

## 0.3 → 0.4

Für die Tarifübersicht ist nichts zu tun. Bestehendes YAML läuft unverändert, die Abschlagsbalken sind jetzt grün. Wer lieber eine graue Farbe möchte, setzt zum Beispiel `advance_color: '#8b97b3'`. Das ähnelt dem früheren Grau, das je nach Farbschema leicht durchscheinend war.

### Auswertung in die eigene Karte umziehen

Der Block `analysis` in `tarif-cockpit-card` ist veraltet. Er wird weiter angezeigt, fällt aber in einer späteren Version weg. Umzug in zwei Schritten:

1. Im Dashboard eine neue Karte **Tarif-Cockpit Auswertung** hinzufügen. In YAML werden die Felder von `analysis` eine Ebene nach links gerückt:

   ```yaml
   # vorher, in tarif-cockpit-card
   analysis:
     title: Gas witterungsbereinigt
     kennwert: sensor.gas_kennwert_je_gradtag
     consumption: sensor.gas_verbrauch_letzte_periode
     temperature: sensor.gas_aussentemperatur_letzte_periode
   ```

   ```yaml
   # nachher, eigene Karte
   type: custom:tarif-cockpit-analyse-card
   title: Gas witterungsbereinigt
   kennwert: sensor.gas_kennwert_je_gradtag
   consumption: sensor.gas_verbrauch_letzte_periode
   temperature: sensor.gas_aussentemperatur_letzte_periode
   theme: dunkel   # wie in der Tarifübersicht
   ```

2. Den Block `analysis` aus `tarif-cockpit-card` löschen.

Alle Felder bleiben gleich: `title`, `kennwert`, `kennwert_previous`, `consumption`, `temperature`, `degree_days`, `extras`, `explain`, `pending_text`, `months`, `history`, `color`. Neu sind `theme`, `subtitle`, `icon` und `label`.

## 0.5 → 0.6: von den Template-Sensoren zur Integration

Ab 0.6 rechnet die Integration Kosten, Abschläge, Prognose und Urteil selbst. Die Template-Sensoren, die Helfer für die Prognose und die tägliche Automation werden nicht mehr gebraucht. Empfohlen ist ein **Parallelbetrieb von zwei Wochen**:

1. Update auf 0.6 einspielen, Home Assistant neu starten.
2. Für jeden Zähler (Strom, Gas, Wasser) „Zähler hinzufügen“: Zählerstand-Sensor, Vertrag mit Abrechnungsbeginn und Regel (z. B. fester Stichtag), Preise wie in den Tarif-Helfern, Abschlag und Zahltag, Startstand zu Abrechnungsbeginn (wie `abrechnung_*_startstand`).
3. Hat der Zählerstand-Sensor noch keine Jahreshistorie, unter „Neu konfigurieren“ die **Ersatzquelle für fehlende Historie** setzen (die Entität, aus der die Automation bisher die Vorjahreswerte holte). Die fehlenden Tage werden danach automatisch nachgeholt.
4. Zwei Wochen lang die neuen Sensoren (`sensor.<zähler>_kosten_bisher`, `_abschlage_bisher`, `_prognose_kosten`, `_saldo` …) mit den Template-Sensoren vergleichen. Strom und Kosten sollten auf ±1 % übereinstimmen. Gas weicht ab, sobald die Integration einen eigenen Kennwert gelernt hat, statt mit der Annahme 6,5 zu rechnen; bis dahin zeigt sie für Gas keine Prognose.
5. Karte auf die neuen Sensoren umstellen (YAML im README), danach Automation, Template-Sensoren und Prognose-Helfer abschalten.

Preis- und Abschlagsänderungen laufen ab jetzt über die Aktionen `set_preis` und `set_abschlag`, Ablesungen über `add_ablesung` (z. B. aus der Telegram-Automation).

## 0.4 → 0.5: von der Dashboard-Karte zur Integration

Ab 0.5 ist Tarif-Cockpit eine **Integration**, die beide Karten mitliefert. Im Marketplace gehört ein Repository immer zu genau einer Kategorie; die bisherige Installation als **Dashboard** bekommt deshalb keine Updates mehr.

> **Wichtig:** Das 0.5-Update **nicht** in der Dashboard-Installation einspielen. Erst umstellen, wie unten beschrieben.

1. **Dashboard-Installation entfernen:** Einstellungen → Marketplace → „Tarif-Cockpit“ (Dashboard) → Menü → **Entfernen**. Damit verschwindet auch die Dashboard-Ressource `/hacsfiles/tarif-cockpit/tarif-cockpit.js`. Danach im Marketplace-Menü unter **Benutzerdefinierte Repositories** den Eintrag `HasenbeinMH/tarif-cockpit` löschen.
2. **Als Integration hinzufügen:** Benutzerdefinierte Repositories → `https://github.com/HasenbeinMH/tarif-cockpit`, Kategorie **Integration** → „Tarif-Cockpit“ herunterladen.
3. Home Assistant **neu starten**.
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Tarif-Cockpit**: Haushalt anlegen. Das genügt, damit die Karten wieder geladen werden. Zähler kannst du sofort oder später hinzufügen.
5. Browser-Cache leeren (Strg+F5).

Deine Dashboards und das YAML der Karten bleiben unverändert gültig. Bis 0.6 zeigen die Karten weiterhin die Werte deiner Template-Sensoren (Sensor-Modus); die Automation und die Template-Helfer also noch nicht abschalten.

Findet die Integration noch die alte Ressource, steht unter Einstellungen → Reparaturen der Hinweis „alte Dashboard-Installation“. Er verschwindet nach dem nächsten Neustart, sobald die Ressource entfernt ist.
