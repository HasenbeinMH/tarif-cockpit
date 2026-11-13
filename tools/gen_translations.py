"""Erzeugt translations/de.json und en.json für tarif_cockpit. Aufruf: python gen_translations.py <ziel-ordner>"""
import json
import sys


def T(de, en):
    return (de, en)


S = {
    "config": {
        "step": {"user": {
            "title": T("Haushalt anlegen", "Set up household"),
            "description": T("Grunddaten für alle Zähler. Zähler mit Vertrag fügst du danach über „Zähler hinzufügen“ hinzu.",
                             "Basic data for all meters. Add meters with their contract afterwards via “Add meter”."),
            "data": {
                "name": T("Name", "Name"),
                "outdoor_temp_entity": T("Außentemperatur-Sensor", "Outdoor temperature sensor"),
                "weather_entity": T("Wetter-Entität", "Weather entity"),
                "rooms": T("Raumtemperaturen", "Room temperatures"),
                "heating_limit": T("Heizgrenze", "Heating limit"),
                "indoor_ref": T("Innentemperatur für Gradtage", "Indoor reference for degree days"),
                "tolerance_pct": T("Toleranz für „Passt“", "Tolerance for “on track”"),
            },
            "data_description": {
                "outdoor_temp_entity": T("Für Gradtage und Tageswerte. Optional.", "For degree days and daily values. Optional."),
                "heating_limit": T("Tage mit einem Tagesmittel darunter zählen als Heiztage (üblich 15 °C).",
                                   "Days with a mean below this count as heating days (usually 15 °C)."),
                "indoor_ref": T("Üblich 20 °C (Gradtagzahl G20/15).", "Usually 20 °C (degree days G20/15)."),
                "tolerance_pct": T("Abweichung, bis zu der das Urteil „Passt“ lautet.", "Deviation up to which the verdict is “on track”."),
            },
        }},
        "abort": {"single_instance_allowed": T(
            "Es gibt schon einen Haushalt. Weitere Zähler fügst du dort über „Zähler hinzufügen“ hinzu.",
            "A household already exists. Add more meters there via “Add meter”.")},
    },
    "config_subentries": {"zaehler": {
        "initiate_flow": {"user": T("Zähler hinzufügen", "Add meter")},
        "entry_type": T("Zähler", "Meter"),
        "step": {
            "user": {"title": T("Zähler hinzufügen", "Add meter"), "description": T("Was misst der Zähler?", "What does the meter measure?"),
                     "data": {"medium": T("Medium", "Utility")}},
            "quelle": {
                "title": T("Woher kommt der Zählerstand?", "Where does the meter reading come from?"),
                "description": T("Wähle den Zählerstand-Sensor (laufende Summe). Ohne Sensor gibst du Ablesungen von Hand ein (Aktion „Ablesung hinzufügen“).",
                                 "Choose the meter reading sensor (running total). Without a sensor you enter readings by hand (action “Add meter reading”)."),
                "data": {"name": T("Name", "Name"), "entity": T("Zählerstand-Sensor (leer = nur Ablesungen)", "Meter reading sensor (empty = readings only)"),
                         "history_entity": T("Ersatzquelle für fehlende Historie", "Fallback source for missing history"),
                         "role": T("Art des Zählers", "Kind of meter")},
                "data_description": {"history_entity": T("Optional. Füllt Tage, für die der Zähler-Sensor noch keine Statistik hat, z. B. mit dem Bezugszähler des Wechselrichters. Solche Tage gelten als geschätzt.",
                                                         "Optional. Fills days the meter sensor has no statistics for yet, e.g. with the inverter's grid import meter. Such days count as estimated."),
                                     "role": T("Wallbox bzw. Gartenzähler sind Unterzähler eines Hauptzählers ohne eigenen Vertrag.",
                                               "A wallbox or garden meter is a sub-meter of a main meter without its own contract.")},
            },
            "unterzaehler": {"title": T("Hauptzähler", "Main meter"), "description": T("Zu welchem Hauptzähler gehört dieser Unterzähler?", "Which main meter does this sub-meter belong to?"),
                             "data": {"parent": T("Hauptzähler", "Main meter")}},
            "einheit": {
                "title": T("Einheit", "Unit"),
                "description": T("Brennwert und Zustandszahl stehen auf der Gasrechnung. Sie sind optional.",
                                 "Calorific value and conversion factor are on your gas bill. They are optional."),
                "data": {"unit": T("Einheit des Zählers", "Meter unit"), "calorific": T("Brennwert", "Calorific value"),
                         "z_factor": T("Zustandszahl", "Conversion factor (Z)"),
                         "annual_consumption": T("Jahresverbrauch laut letzter Rechnung", "Annual consumption according to the last bill")},
                "data_description": {"annual_consumption": T("Optional. Rückfallebene für die Prognose, solange es kein Vorjahr und keine 30 Tage eigene Daten gibt.",
                                                             "Optional. Fallback for the forecast as long as there is no previous year and no 30 days of own data.")},
            },
            "preis": {"title": T("Preise", "Prices"), "description": T("Preise zu Vertragsbeginn, wie im Vertrag (brutto oder netto, wie zuvor gewählt). Spätere Preisänderungen mit der Aktion „Preis ändern“.",
                                                                    "Prices at the start of the contract, as in the contract (gross or net as chosen before). Later price changes with the action “Set price”."),
                      "data": {"work_price": T("Arbeitspreis", "Unit price"), "base_price": T("Grundpreis je Monat", "Standing charge per month"),
                               "metering_price": T("Messpreis je Monat", "Metering charge per month"), "wastewater_price": T("Abwasser je m³", "Wastewater per m³"),
                               "fixed_yearly": T("Feste Beträge je Jahr (z. B. Niederschlagswasser)", "Fixed amounts per year (e.g. rainwater)")}},
            "abschlag": {"title": T("Abschläge", "Advance payments"), "description": T("Ohne Betrag gibt es keine Abschläge (z. B. bei Abrechnung über den Vermieter). Änderungen später mit der Aktion „Abschlag ändern“.",
                                                                                     "Without an amount there are no advance payments. Later changes with the action “Set advance payment”."),
                         "data": {"amount": T("Abschlag", "Advance payment"), "pay_day": T("Zahltag im Monat", "Day of month"),
                                  "rhythm": T("Rhythmus", "Interval"), "max_per_period": T("Abschläge je Abrechnungsjahr (z. B. 11)", "Payments per billing year (e.g. 11)")}},
            "reconfigure": {"title": T("Zähler ändern", "Change meter"), "description": T("Verträge, Preise und Abschläge änderst du mit den Aktionen des Tarif-Cockpits.",
                                                                                         "Change contracts, prices and advance payments with the Tarif-Cockpit actions."),
                            "data": {"name": T("Name", "Name"), "history_entity": T("Ersatzquelle für fehlende Historie", "Fallback source for missing history"),
                                     "annual_consumption": T("Jahresverbrauch laut letzter Rechnung", "Annual consumption according to the last bill"),
                                     "calorific": T("Brennwert", "Calorific value"), "z_factor": T("Zustandszahl", "Conversion factor (Z)")}},
            "vertrag": {
                "title": T("Vertrag", "Contract"),
                "description": T("Wann rechnet dein Versorger ab? Bei „fester Stichtag“ den ersten Tag der neuen Abrechnungsperiode als TT.MM angeben, z. B. 30.06. (dann endet jede Periode am 29.06.). Bei „von Hand“ das Ende der ersten Periode, weitere Perioden mit der Aktion „Periode anhängen“.",
                                 "When does your supplier bill? For “fixed day” enter the first day of the new billing period as DD.MM, e.g. 30.06. (each period then ends on 29.06.). For “manual” enter the end of the first period; add further periods with the action “Append period”."),
                "data": {"supplier": T("Lieferant", "Supplier"), "tariff": T("Tarif", "Tariff"), "start_date": T("Vertragsbeginn", "Contract start"),
                         "billing_rule": T("Abrechnung", "Billing"), "fixed_day": T("Stichtag (TT.MM)", "Fixed day (DD.MM)"),
                         "first_period_end": T("Ende der ersten Periode", "End of the first period"), "vat_mode": T("Preise", "Prices"),
                         "vat_rate": T("Mehrwertsteuer", "VAT")},
            },
            "startstand": {
                "title": T("Startstand", "Initial reading"),
                "description": T("Erste Abrechnungsperioden: {preview} (* = Rumpfjahr). Den Zählerstand zu Vertragsbeginn eintragen; bei einem Zähler mit Sensor ist er optional.",
                                 "First billing periods: {preview} (* = short year). Enter the meter reading at the start of the contract; optional for a meter with a sensor."),
                "data": {"value": T("Zählerstand", "Meter reading"), "timestamp": T("Zeitpunkt", "Time"), "quality": T("Qualität", "Quality")},
            },
        },
        "error": {
            "already_configured": T("Dieser Sensor ist schon einem Zähler zugeordnet.", "This sensor is already assigned to a meter."),
            "invalid_billing": T("Die Abrechnungsregel passt nicht (z. B. Stichtag kein gültiges TT.MM, 29.02. nicht erlaubt).",
                                 "The billing rule is invalid (e.g. fixed day is not a valid DD.MM; 29.02. is not allowed)."),
            "required_for_manual": T("Bei „von Hand“ wird das Ende der ersten Periode gebraucht.", "“Manual” needs the end of the first period."),
            "required_without_entity": T("Ohne Zählerstand-Sensor wird ein Startstand gebraucht.", "Without a meter sensor an initial reading is required."),
            "no_main_meter": T("Es gibt noch keinen Hauptzähler dieses Mediums.", "There is no main meter of this utility yet."),
            "required_for_m3": T("Bei einem Gaszähler in m³ werden Brennwert und Zustandszahl gebraucht (stehen auf der Gasrechnung).", "A gas meter in m³ needs the calorific value and conversion factor (on your gas bill)."),
        },
        "abort": {"reconfigure_successful": T("Der Zähler wurde geändert.", "The meter was changed.")},
    }},
    "selector": {
        "medium": {"options": {"strom": T("Strom", "Electricity"), "gas": T("Gas", "Gas"), "wasser": T("Wasser", "Water"), "fernwaerme": T("Fernwärme", "District heating")}},
        "billing_rule": {"options": {"contract_year": T("Vertragsjahr (12 Monate ab Beginn)", "Contract year (12 months from start)"),
                                     "calendar_year": T("Kalenderjahr (erstes Jahr als Rumpfjahr)", "Calendar year (first year shortened)"),
                                     "fixed_day": T("Fester Stichtag", "Fixed day"), "manual": T("Von Hand", "Manual")}},
        "vat_mode": {"options": {"gross": T("Brutto (mit MwSt.)", "Gross (incl. VAT)"), "net": T("Netto (ohne MwSt.)", "Net (excl. VAT)")}},
        "quality": {"options": {"real": T("Abgelesen", "Read"), "estimated": T("Geschätzt", "Estimated")}},
        "role": {"options": {"main": T("Hauptzähler", "Main meter"), "wallbox": T("Wallbox (Unterzähler)", "Wallbox (sub-meter)"), "garden": T("Gartenwasser (Unterzähler, ohne Abwasser)", "Garden water (sub-meter, no wastewater)")}},
        "rhythm": {"options": {"1": T("monatlich", "monthly"), "2": T("alle zwei Monate", "every two months"), "3": T("vierteljährlich", "quarterly")}},
        "payment_type": {"options": {"advance": T("Abschlag", "Advance payment"), "one_off": T("Einmalzahlung", "One-off payment"), "credit": T("Gutschrift", "Credit"), "final": T("Schlusszahlung", "Final payment"), "refund": T("Erstattung", "Refund")}},
        "payment_status": {"options": {"paid": T("bezahlt", "paid"), "planned": T("geplant", "planned"), "cancelled": T("storniert", "cancelled")}},
    },
    "entity": {"sensor": {
        "periode_ende": {"name": T("Periodenende", "Billing period end")},
        "letzte_ablesung": {"name": T("Letzte Ablesung", "Last reading")},
        "zaehlerstand": {"name": T("Zählerstand (abgelesen)", "Meter reading (read)")},
        "tageswerte_qualitaet": {"name": T("Tageswerte vollständig", "Daily values complete")},
        "kosten_bisher": {"name": T("Kosten bisher", "Costs so far")},
        "abschlaege_bisher": {"name": T("Abschläge bisher", "Advances paid so far")},
        "abschlaege_periode": {"name": T("Abschläge Periode", "Advances for the period")},
        "abschlag": {"name": T("Abschlag", "Advance payment")},
        "prognose_verbrauch": {"name": T("Prognose Verbrauch", "Forecast consumption")},
        "prognose_kosten": {"name": T("Prognose Kosten", "Forecast costs")},
        "saldo": {"name": T("Saldo", "Balance")},
        "urteil": {"name": T("Urteil", "Verdict"), "state": {"passt": T("Passt", "On track"), "rueckzahlung": T("Rückzahlung", "Refund"), "nachzahlung": T("Nachzahlung", "Back payment")}},
        "abschlag_empfohlen": {"name": T("Abschlag empfohlen", "Recommended advance")},
        "prognose_qualitaet": {"name": T("Prognose-Qualität", "Forecast quality"), "state": {
            "annahme": T("Annahme", "Assumption"), "unzureichend": T("Unzureichend", "Insufficient"), "vorlaeufig": T("Vorläufig", "Preliminary"),
            "gut": T("Gut", "Good"), "sehr_gut": T("Sehr gut", "Very good")}},
        "kennwert": {"name": T("Kennwert", "Heat coefficient")},
        "ww_grundlast": {"name": T("Warmwasser-Grundlast", "Hot water base load")},
        "saldo_gesamt": {"name": T("Saldo gesamt", "Total balance")},
    }},
    "services": {
        "add_ablesung": {
            "name": T("Ablesung hinzufügen", "Add meter reading"),
            "description": T("Trägt einen Zählerstand ein. Mit „Ersetzt“ wird eine frühere Ablesung korrigiert, ohne sie zu löschen.",
                             "Adds a meter reading. With “Replaces” an earlier reading is corrected without deleting it."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "stand": {"name": T("Stand", "Reading"), "description": T("Zählerstand in der Einheit des Zählers.", "Meter reading in the meter unit.")},
                "zeitpunkt": {"name": T("Zeitpunkt", "Time"), "description": T("Standard: jetzt.", "Default: now.")},
                "qualitaet": {"name": T("Qualität", "Quality"), "description": T("Abgelesen oder geschätzt.", "Read or estimated.")},
                "notiz": {"name": T("Notiz", "Note"), "description": T("Freier Text.", "Free text.")},
                "ersetzt": {"name": T("Ersetzt", "Replaces"), "description": T("ID der Ablesung, die korrigiert wird (Attribut ablesung_id).", "ID of the reading being corrected (attribute ablesung_id).")},
            },
        },
        "ablesung_ungueltig": {
            "name": T("Ablesung ungültig", "Mark reading invalid"),
            "description": T("Markiert eine Ablesung als ungültig. Sie bleibt gespeichert, geht aber nicht mehr in Rechnungen ein.",
                             "Marks a reading as invalid. It is kept but no longer used in calculations."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "ablesung_id": {"name": T("Ablesung", "Reading"), "description": T("ID der Ablesung.", "ID of the reading.")},
                "grund": {"name": T("Grund", "Reason"), "description": T("Wird als Notiz gespeichert.", "Stored as a note.")},
            },
        },
        "add_folgevertrag": {
            "name": T("Folgevertrag (Anbieterwechsel)", "Follow-up contract (supplier change)"),
            "description": T("Der laufende Vertrag endet am Vortag des Beginns (Schlussrechnung), der neue Vertrag beginnt.",
                             "The current contract ends the day before the start (final bill); the new contract begins."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "lieferant": {"name": T("Lieferant", "Supplier"), "description": T("Neuer Lieferant.", "New supplier.")},
                "tarif": {"name": T("Tarif", "Tariff"), "description": T("Name des Tarifs.", "Tariff name.")},
                "beginn": {"name": T("Beginn", "Start"), "description": T("Erster Liefertag.", "First day of supply.")},
                "abrechnungsregel": {"name": T("Abrechnung", "Billing"), "description": T("Wann rechnet der neue Versorger ab?", "When does the new supplier bill?")},
                "stichtag": {"name": T("Stichtag", "Fixed day"), "description": T("Bei „fester Stichtag“: erster Tag der Periode als TT.MM.", "For “fixed day”: first day of the period as DD.MM.")},
                "erste_periode_ende": {"name": T("Ende der ersten Periode", "End of the first period"), "description": T("Nur bei „von Hand“.", "Only for “manual”.")},
                "vat_mode": {"name": T("Preise", "Prices"), "description": T("Brutto oder netto.", "Gross or net.")},
                "vat_rate": {"name": T("Mehrwertsteuer", "VAT"), "description": T("In Prozent. Standard: 19 %, Wasser 7 %.", "In percent. Default: 19 %, water 7 %.")},
                "wechselstand": {"name": T("Wechselstand", "Switch reading"), "description": T("Zählerstand zum Wechsel. Fehlt er, kann er später als Ablesung nachgetragen werden.", "Meter reading at the switch. If missing, add it later as a reading.")},
            },
        },
        "set_periodenende": {
            "name": T("Periodenende (Ablesetermin)", "Billing period end (reading date)"),
            "description": T("Der Versorger hat ein paar Tage früher oder später abgelesen: Ende der laufenden oder der zuletzt beendeten Periode verschieben (höchstens ±10 Tage). Die Regel bleibt.",
                             "The supplier read the meter a few days earlier or later: shift the end of the current or the last ended period (at most ±10 days). The rule stays."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "ende": {"name": T("Ende", "End"), "description": T("Letzter Tag der Periode laut Rechnung.", "Last day of the period according to the bill.")},
            },
        },
        "add_periode": {
            "name": T("Periode anhängen (von Hand)", "Append period (manual)"),
            "description": T("Nur bei der Abrechnung „von Hand“: nächste Periode anhängen. Sie beginnt am Tag nach dem Ende der letzten.",
                             "Only for “manual” billing: append the next period. It starts the day after the last one ends."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "ende": {"name": T("Ende", "End"), "description": T("Letzter Tag der neuen Periode.", "Last day of the new period.")},
            },
        },
        "set_preis": {
            "name": T("Preis ändern", "Set price"),
            "description": T("Neuer Preisabschnitt ab einem Datum (Preisänderung oder Korrektur bei gleichem Datum). Der bisherige Abschnitt endet am Vortag. Die Verbrauchsprognose bleibt unverändert.",
                             "New price segment from a date (price change, or correction with the same date). The previous segment ends the day before. The consumption forecast stays unchanged."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "ab": {"name": T("Gültig ab", "Valid from"), "description": T("Erster Tag des neuen Preises.", "First day of the new price.")},
                "arbeitspreis": {"name": T("Arbeitspreis", "Unit price"), "description": T("Je kWh (Wasser je m³).", "Per kWh (water per m³).")},
                "grundpreis": {"name": T("Grundpreis", "Standing charge"), "description": T("Je Monat.", "Per month.")},
                "messpreis": {"name": T("Messpreis", "Metering charge"), "description": T("Je Monat.", "Per month.")},
                "brennwert": {"name": T("Brennwert", "Calorific value"), "description": T("Gas, kWh/m³, ab diesem Datum.", "Gas, kWh/m³, from this date.")},
                "zustandszahl": {"name": T("Zustandszahl", "Conversion factor (Z)"), "description": T("Gas, ab diesem Datum.", "Gas, from this date.")},
                "abwasserpreis": {"name": T("Abwasserpreis", "Wastewater price"), "description": T("Je m³.", "Per m³.")},
                "fest_jahr": {"name": T("Feste Beträge je Jahr", "Fixed amounts per year"), "description": T("Z. B. Niederschlagswasser.", "E.g. rainwater.")},
                "leistungspreis": {"name": T("Leistungspreis", "Demand charge"), "description": T("Fernwärme, je kW und Jahr.", "District heating, per kW and year.")},
                "anschlussleistung": {"name": T("Anschlussleistung", "Connected load"), "description": T("Fernwärme, kW.", "District heating, kW.")},
            },
        },
        "set_abschlag": {
            "name": T("Abschlag ändern", "Set advance payment"),
            "description": T("Neue Abschlagsstufe ab einem Datum; Zahltag, Rhythmus und Anzahl optional mitändern.", "New advance payment step from a date; optionally change day, interval and count."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "ab": {"name": T("Gültig ab", "Valid from"), "description": T("Erster Zahltag mit dem neuen Betrag.", "First payment day with the new amount.")},
                "betrag": {"name": T("Betrag", "Amount"), "description": T("Abschlag je Zahltag.", "Amount per payment day.")},
                "zahltag": {"name": T("Zahltag", "Payment day"), "description": T("Tag im Monat.", "Day of month.")},
                "rhythmus": {"name": T("Rhythmus", "Interval"), "description": T("Alle 1, 2 oder 3 Monate.", "Every 1, 2 or 3 months.")},
                "anzahl_je_periode": {"name": T("Anzahl je Periode", "Count per period"), "description": T("Z. B. 11 Abschläge je Abrechnungsjahr.", "E.g. 11 payments per billing year.")},
            },
        },
        "add_zahlung": {
            "name": T("Zahlung erfassen", "Add payment"),
            "description": T("Tatsächliche Zahlung, Einmalzahlung, Gutschrift oder Erstattung. Ein erfasster Abschlag ersetzt den geplanten im selben Monat.",
                             "Actual payment, one-off payment, credit or refund. A recorded advance replaces the planned one in the same month."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "datum": {"name": T("Datum", "Date"), "description": T("Tag der Zahlung.", "Day of payment.")},
                "betrag": {"name": T("Betrag", "Amount"), "description": T("Immer positiv; Gutschrift und Erstattung mindern die Zahlungen.", "Always positive; credits and refunds reduce payments.")},
                "art": {"name": T("Art", "Kind"), "description": T("Abschlag, Einmalzahlung, Gutschrift, Schlusszahlung, Erstattung.", "Advance, one-off, credit, final, refund.")},
                "status": {"name": T("Status", "Status"), "description": T("Bezahlt, geplant oder storniert.", "Paid, planned or cancelled.")},
            },
        },
        "add_rechnung": {
            "name": T("Rechnung erfassen", "Add invoice"),
            "description": T("Rechnung des Versorgers (getrennt von Zahlungen). Mit „korrigiert“ als Korrekturrechnung.", "Supplier invoice (separate from payments). With “corrects” as a correction invoice."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
                "datum": {"name": T("Rechnungsdatum", "Invoice date"), "description": T("Datum der Rechnung.", "Invoice date.")},
                "von": {"name": T("Von", "From"), "description": T("Abrechnungszeitraum Beginn.", "Billing period start.")},
                "bis": {"name": T("Bis", "To"), "description": T("Abrechnungszeitraum Ende.", "Billing period end.")},
                "betrag": {"name": T("Betrag", "Amount"), "description": T("Rechnungsbetrag.", "Invoice amount.")},
                "korrigiert": {"name": T("Korrigiert", "Corrects"), "description": T("ID der korrigierten Rechnung.", "ID of the corrected invoice.")},
            },
        },
        "recalculate": {
            "name": T("Tageswerte neu berechnen", "Recalculate daily values"),
            "description": T("Berechnet Tageswerte aus Statistik und Ablesungen neu. Ablesungen und Verträge bleiben unverändert.",
                             "Recalculates daily values from statistics and readings. Readings and contracts stay unchanged."),
            "fields": {
                "zaehler": {"name": T("Zähler", "Meter"), "description": T("Leer = alle Zähler.", "Empty = all meters.")},
                "von": {"name": T("Von", "From"), "description": T("Erster Tag.", "First day.")},
                "bis": {"name": T("Bis", "To"), "description": T("Letzter Tag.", "Last day.")},
            },
        },
    },
    "issues": {
        "store_verloren": {
            "title": T("Tarif-Cockpit: gespeicherte Daten fehlen", "Tarif-Cockpit: stored data missing"),
            "description": T("Die Datei `.storage/{key}` fehlt oder war beschädigt (Home Assistant benennt sie dann in `{key}.corrupt.…` um). Damit nichts verloren geht, startet das Tarif-Cockpit nicht mit leeren Daten. Bitte die Datei aus einer Sicherung wiederherstellen und Home Assistant neu starten.",
                             "The file `.storage/{key}` is missing or was corrupt (Home Assistant then renames it to `{key}.corrupt.…`). To avoid data loss, Tarif-Cockpit does not start with empty data. Please restore the file from a backup and restart Home Assistant."),
        },
        "store_ungueltig": {
            "title": T("Tarif-Cockpit: gespeicherte Daten ungültig", "Tarif-Cockpit: stored data invalid"),
            "description": T("In `.storage/{key}` wurden {count} Fehler gefunden, z. B.: {errors}. Die Datei wurde nicht verändert. Bitte die Diagnose herunterladen und ein Issue melden oder eine Sicherung wiederherstellen.",
                             "{count} errors were found in `.storage/{key}`, e.g.: {errors}. The file was not changed. Please download the diagnostics and open an issue, or restore a backup."),
        },
        "alte_dashboard_installation": {
            "title": T("Tarif-Cockpit: alte Dashboard-Installation", "Tarif-Cockpit: old dashboard installation"),
            "description": T("Die Karten werden jetzt von der Integration geladen. Die frühere Dashboard-Installation lädt sie ein zweites Mal (`/hacsfiles/tarif-cockpit/`). Bitte im Marketplace die Dashboard-Installation entfernen, siehe MIGRATION.md.",
                             "The cards are now loaded by the integration. The earlier dashboard installation loads them a second time (`/hacsfiles/tarif-cockpit/`). Please remove the dashboard installation in the Marketplace, see MIGRATION.md."),
        },
        "store_zu_neu": {
            "title": T("Tarif-Cockpit: Daten aus einer neueren Version", "Tarif-Cockpit: data from a newer version"),
            "description": T("`.storage/{key}` wurde von einer neueren Version des Tarif-Cockpits geschrieben. Die Datei bleibt unverändert. Bitte die neuere Version wieder installieren.",
                             "`.storage/{key}` was written by a newer version of Tarif-Cockpit. The file stays unchanged. Please install the newer version again."),
        },
        "zaehler_ohne_statistik": {
            "title": T("Tarif-Cockpit: keine Statistik für {meter}", "Tarif-Cockpit: no statistics for {meter}"),
            "description": T("Für `{entity}` gibt es keine Langzeitstatistik mit laufender Summe. Der Sensor braucht `state_class: total_increasing` (oder `total`). Bis dahin fehlen die Tageswerte dieses Zählers; sie werden nicht als 0 gezählt.",
                             "There are no long-term statistics with a running sum for `{entity}`. The sensor needs `state_class: total_increasing` (or `total`). Until then the daily values of this meter are missing; they are not counted as 0."),
        },
    },
    "exceptions": {
        "unknown_meter": {"message": T("Unbekannter Zähler: {id}", "Unknown meter: {id}")},
        "unknown_reading": {"message": T("Unbekannte Ablesung: {id}", "Unknown reading: {id}")},
        "reading_in_future": {"message": T("Der Zeitpunkt der Ablesung liegt in der Zukunft.", "The reading time is in the future.")},
        "contract_invalid": {"message": T("Folgevertrag nicht möglich: {error}", "Follow-up contract not possible: {error}")},
        "unknown_invoice": {"message": T("Unbekannte Rechnung: {id}", "Unknown invoice: {id}")},
        "period_invalid": {"message": T("Periode nicht änderbar: {error}", "Period cannot be changed: {error}")},
        "reading_already_replaced": {"message": T("Diese Ablesung ist schon ersetzt oder ungültig ({id}). Bitte die aktuell gültige Ablesung angeben.", "This reading is already replaced or invalid ({id}). Please refer to the currently valid reading.")},
    },
}


def pick(o, i):
    if isinstance(o, tuple):
        return o[i]
    if isinstance(o, dict):
        return {k: pick(v, i) for k, v in o.items()}
    return o


target = sys.argv[1]
for i, lang in ((0, "de"), (1, "en")):
    with open(f"{target}/{lang}.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(pick(S, i), f, ensure_ascii=False, indent=2)
        f.write("\n")
print("ok")
