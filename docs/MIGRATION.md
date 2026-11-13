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
