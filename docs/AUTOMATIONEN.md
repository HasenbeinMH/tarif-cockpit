# Automationen

Die Integration verschickt nichts selbst. Sie meldet Ereignisse als **Events**; was daraus wird (Telegram, Push, Sprachausgabe), entscheidest du in einer Automation. Die Beispiele sind in YAML, lassen sich aber genauso im Automations-Editor anlegen (Auslöser „Manuelles Event“).

## Urteil hat sich geändert

Event `tarif_cockpit_urteil_geaendert`: Das Urteil eines Zählers wechselt innerhalb derselben Periode, z. B. von „passt“ zu „nachzahlung“. Beim Start von Home Assistant und beim Periodenwechsel kommt kein Event.

```yaml
alias: Tarif-Cockpit – Urteil geändert
triggers:
  - trigger: event
    event_type: tarif_cockpit_urteil_geaendert
actions:
  - action: notify.mobile_app_mein_telefon      # dein Benachrichtigungsdienst
    data:
      title: "{{ trigger.event.data.name }}: {{ trigger.event.data.neu }}"
      message: >-
        Saldo {{ trigger.event.data.saldo }} € (vorher {{ trigger.event.data.alt }}).
        {% if trigger.event.data.abschlag_empfohlen %}Empfohlener Abschlag: {{ trigger.event.data.abschlag_empfohlen }} €.{% endif %}
mode: queued
```

Daten: `zaehler` (ID), `device_id`, `name`, `alt`, `neu` (`passt`, `rueckzahlung`, `nachzahlung`), `saldo`, `prognose_kosten`, `qualitaet`, `abschlag_empfohlen`.

Liegt der Saldo genau an der Toleranzgrenze, kann das Urteil hin und her wechseln (z. B. nach einer neuen Wettervorhersage). Wer nur einmal am Tag benachrichtigt werden will, ergänzt `mode: single` und am Ende `- delay: "12:00:00"`.

Nur für einen Zähler: im Auslöser `event_data: {name: Gas}` ergänzen.

## Kündigungsfrist

Event `tarif_cockpit_kuendigungsfrist`: 28 Tage vor dem letzten Kündigungstag und an diesem Tag (`tage` = 28 bzw. 0), je Frist nur einmal, auch über Neustarts. Voraussetzung: Mindestlaufzeit oder festes Vertragsende und Kündigungsfrist sind eingetragen (Zähler → Neu konfigurieren → Vertrag ändern). Ab 28 Tagen vorher steht außerdem ein Hinweis unter Reparaturen.

```yaml
alias: Tarif-Cockpit – Kündigungsfrist
triggers:
  - trigger: event
    event_type: tarif_cockpit_kuendigungsfrist
actions:
  - action: notify.mobile_app_mein_telefon
    data:
      title: "{{ trigger.event.data.name }}: Kündigungsfrist"
      message: >-
        Vertrag bei {{ trigger.event.data.lieferant }} endet am {{ trigger.event.data.vertragsende }}.
        Kündigen bis {{ trigger.event.data.kuendigen_bis }}
        {%- if trigger.event.data.tage == 0 %} – heute ist der letzte Tag!{% else %} (noch {{ trigger.event.data.tage }} Tage).{% endif %}
```

Ohne Event, jederzeit abfragbar: Attribute `kuendigung_bis` und `tage_bis_kuendigung` am Sensor „Periodenende“ des Zählers.

## Ablesung per Telegram

Zählerstand per Nachricht an den Telegram-Bot, z. B. `/gas 9812,4`:

```yaml
alias: Tarif-Cockpit – Ablesung Gas per Telegram
triggers:
  - trigger: event
    event_type: telegram_command
    event_data:
      command: /gas
actions:
  - action: tarif_cockpit.add_ablesung
    data:
      zaehler: 1a2b3c…                          # Gerät „Gas“ des Tarif-Cockpits
      stand: "{{ trigger.event.data.args[0] | replace(',', '.') | float }}"
  - action: telegram_bot.send_message
    data:
      target: "{{ trigger.event.data.chat_id }}"
      message: "Gas {{ trigger.event.data.args[0] }} gespeichert."
```

Die Geräte-ID steht unter Einstellungen → Geräte & Dienste → Tarif-Cockpit → Gerät „Gas“ in der Adresszeile; im Automations-Editor wählst du das Gerät einfach aus. Ein falscher Stand lässt sich mit `ersetzt` korrigieren oder mit `ablesung_ungueltig` verwerfen; gelöscht wird nichts.

## Erinnerung an die Ablesung

Monatlich am Ersten erinnern, wenn die letzte Ablesung älter als 25 Tage ist:

```yaml
alias: Tarif-Cockpit – Ablesung fällig
triggers:
  - trigger: time
    at: "09:00:00"
conditions:
  - condition: template
    value_template: "{{ now().day == 1 and (now() - as_datetime(states('sensor.gas_letzte_ablesung'))).days > 25 }}"
actions:
  - action: notify.mobile_app_mein_telefon
    data:
      message: Bitte den Gaszähler ablesen.
```

`sensor.gas_letzte_ablesung` ist der Sensor „Letzte Ablesung“ deines Zählers (die ID hängt vom Namen ab).
