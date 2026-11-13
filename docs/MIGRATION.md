# Migration

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

## 0.4 → 0.5 (Vorschau)

Mit 0.5 wird das Repo zu einer Integration, die beide Karten mitliefert. Wie der Umstieg im Marketplace geht, steht dann hier.
