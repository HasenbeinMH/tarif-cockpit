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
                "description": T("In welcher Einheit zählt der Zähler? Zählt ein Gaszähler in m³, braucht es Brennwert und Zustandszahl von der Gasrechnung.",
                                 "Which unit does the meter count in? A gas meter counting in m³ needs the calorific value and conversion factor from your gas bill."),
                "data": {"unit": T("Einheit des Zählers", "Meter unit"), "calorific": T("Brennwert", "Calorific value"),
                         "z_factor": T("Zustandszahl", "Conversion factor (Z)"),
                         "annual_consumption": T("Jahresverbrauch laut letzter Rechnung", "Annual consumption according to the last bill")},
                "data_description": {"annual_consumption": T("Optional. Rückfallebene für die Prognose, solange es kein Vorjahr und keine 30 Tage eigene Daten gibt.",
                                                             "Optional. Fallback for the forecast as long as there is no previous year and no 30 days of own data.")},
            },
            "preis": {"title": T("Preise", "Prices"), "description": T("Preise zu Vertragsbeginn, wie im Vertrag (brutto oder netto, wie zuvor gewählt). Spätere Preisänderungen über „Neu konfigurieren“ am Zähler (oder die Aktion „Preis ändern“).",
                                                                    "Prices at the start of the contract, as in the contract (gross or net as chosen before). Later price changes via “Reconfigure” on the meter (or the action “Set price”)."),
                      "data": {"work_price": T("Arbeitspreis", "Unit price"), "base_price": T("Grundpreis je Monat", "Standing charge per month"),
                               "metering_price": T("Messpreis je Monat", "Metering charge per month"), "wastewater_price": T("Abwasser je m³", "Wastewater per m³"),
                               "fixed_yearly": T("Feste Beträge je Jahr (z. B. Niederschlagswasser)", "Fixed amounts per year (e.g. rainwater)")}},
            "abschlag": {"title": T("Abschläge", "Advance payments"), "description": T("Ohne Betrag gibt es keine Abschläge (z. B. bei Abrechnung über den Vermieter). Änderungen später über „Neu konfigurieren“ am Zähler, in der Karte oder mit der Aktion „Abschlag ändern“.",
                                                                                     "Without an amount there are no advance payments. Later changes via “Reconfigure” on the meter, in the card or with the action “Set advance payment”."),
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
                "description": T("Erste Abrechnungsperioden: {preview} (¹ = Rumpfjahr). Den Zählerstand zu Vertragsbeginn eintragen; bei einem Zähler mit Sensor ist er optional.",
                                 "First billing periods: {preview} (¹ = short year). Enter the meter reading at the start of the contract; optional for a meter with a sensor."),
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


# ---------------------------------------------------------------- 0.7: Fragen-Assistent, Optionen, Menü am Zähler

SITUATION_DATA = {
    "heating": T("Womit heizt du?", "How do you heat?"),
    "hot_water": T("Wie wird Warmwasser erzeugt?", "How is hot water produced?"),
    "extras": T("Was hast du noch?", "What else do you have?"),
    "tenure": T("Wohnst du als …", "You live as …"),
    "rhythm": T("Wie oft zahlst du Abschläge?", "How often do you pay advances?"),
}
CLIMATE_DATA = {
    "outdoor_temp_entity": T("Außentemperatur-Sensor", "Outdoor temperature sensor"),
    "weather_entity": T("Wetter-Entität", "Weather entity"),
    "rooms": T("Raumtemperaturen", "Room temperatures"),
    "heating_limit": T("Heizgrenze", "Heating limit"),
    "indoor_ref": T("Innentemperatur für Gradtage", "Indoor reference for degree days"),
}
CLIMATE_DESC = {
    "outdoor_temp_entity": T("Für Gradtage und den gelernten Kennwert. Ohne Außentemperatur gibt es keine Heizprognose.", "For degree days and the learned coefficient. Without an outdoor temperature there is no heating forecast."),
    "heating_limit": T("Tage mit einem Tagesmittel darunter zählen als Heiztage (üblich 15 °C).", "Days with a mean below this count as heating days (usually 15 °C)."),
    "indoor_ref": T("Üblich 20 °C (Gradtagzahl G20/15).", "Usually 20 °C (degree days G20/15)."),
}
S["config"]["step"] = {
    "user": {
        "title": T("Haushalt anlegen", "Set up household"),
        "description": T("Ein paar Fragen zu deinem Haushalt. Danach fragt die Einrichtung nur noch, was dazu passt.",
                         "A few questions about your household. Afterwards the setup only asks what fits."),
        "data": {"name": T("Name", "Name"), **SITUATION_DATA},
    },
    "klima": {
        "title": T("Heizung und Temperatur", "Heating and temperature"),
        "description": T("Für die Heizprognose: Tagesmittel der Außentemperatur und Gradtage.", "For the heating forecast: daily mean outdoor temperature and degree days."),
        "data": CLIMATE_DATA, "data_description": CLIMATE_DESC,
    },
    "abschluss": {
        "title": T("Fast fertig", "Almost done"),
        "description": T("Danach legst du beim Eintrag „Tarif-Cockpit“ über „Zähler hinzufügen“ deine Zähler an. Passend zu deinen Antworten: {zaehler}.",
                         "Afterwards add your meters via “Add meter” on the “Tarif-Cockpit” entry. Matching your answers: {zaehler}."),
        "data": {"tolerance_pct": T("Toleranz für „Passt“", "Tolerance for “on track”")},
        "data_description": {"tolerance_pct": T("Abweichung, bis zu der das Urteil „Passt“ lautet.", "Deviation up to which the verdict is “on track”.")},
    },
}
S["options"] = {"step": {"init": {
    "title": T("Haushalt ändern", "Change household"),
    "description": T("Änderungen laden das Tarif-Cockpit neu. Zähler, Verträge und Daten bleiben erhalten.", "Changes reload Tarif-Cockpit. Meters, contracts and data are kept."),
    "data": {**SITUATION_DATA, **CLIMATE_DATA, "tolerance_pct": T("Toleranz für „Passt“", "Tolerance for “on track”")},
    "data_description": CLIMATE_DESC,
}}}
S["selector"].update({
    "heating": {"options": {"gas": T("Gas", "Gas"), "fernwaerme": T("Fernwärme", "District heating"), "waermepumpe": T("Wärmepumpe", "Heat pump"),
                            "strom": T("Strom (Elektro, Split-Klima)", "Electricity (direct, split AC)"), "kaminofen": T("Kaminofen", "Wood stove"),
                            "oel_pellets": T("Öl oder Pellets (folgt nach 1.0)", "Oil or pellets (after 1.0)"), "keine": T("Keine eigene Heizung", "No own heating")}},
    "hot_water": {"options": {"heizung": T("Über die Heizung", "Via the heating"), "strom": T("Durchlauferhitzer oder Boiler (Strom)", "Instantaneous or boiler (electric)"),
                              "waermepumpe": T("Wärmepumpe", "Heat pump"), "solarthermie": T("Solarthermie (unterstützend)", "Solar thermal (supporting)")}},
    "extras": {"options": {"pv": T("PV-Anlage", "PV system"), "speicher": T("Batteriespeicher", "Battery storage"), "wallbox": T("Wallbox", "Wallbox")}},
    "tenure": {"options": {"eigentuemer": T("Eigentümer", "Owner"), "mieter": T("Mieter", "Tenant")}},
})
SUB = S["config_subentries"]["zaehler"]
SUB["step"]["user"]["description"] = T("Was misst der Zähler? Passend zu deinem Haushalt fehlen noch: {fehlen}.", "What does the meter measure? Still missing for your household: {fehlen}.")
SUB["step"]["stammdaten"] = SUB["step"].pop("reconfigure")
SUB["step"]["reconfigure"] = {"title": T("Zähler ändern", "Change meter"), "description": T("Was möchtest du ändern?", "What do you want to change?"),
                              "menu_options": {"stammdaten": T("Name, Ersatzquelle, Brennwert", "Name, fallback source, calorific value"),
                                               "anbieterwechsel": T("Anbieter wechseln", "Change supplier"),
                                               "preis_aendern": T("Preis ändern", "Change price"),
                                               "abschlag_aendern": T("Abschlag ändern", "Change advance payment")}}
PRICE_DATA = {"valid_from": T("Gültig ab", "Valid from"), "work_price": T("Arbeitspreis", "Unit price"), "base_price": T("Grundpreis je Monat", "Standing charge per month"),
              "metering_price": T("Messpreis je Monat", "Metering charge per month"), "calorific": T("Brennwert", "Calorific value"), "z_factor": T("Zustandszahl", "Conversion factor (Z)"),
              "wastewater_price": T("Abwasser je m³", "Wastewater per m³"), "fixed_yearly": T("Feste Beträge je Jahr (z. B. Niederschlagswasser)", "Fixed amounts per year (e.g. rainwater)"),
              "demand_price": T("Leistungspreis", "Demand charge"), "demand_kw": T("Anschlussleistung", "Connected load")}
ADV_DATA = {"valid_from": T("Gültig ab", "Valid from"), "amount": T("Abschlag", "Advance payment"), "pay_day": T("Zahltag im Monat", "Day of month"),
            "rhythm": T("Rhythmus", "Interval"), "max_per_period": T("Abschläge je Abrechnungsjahr (z. B. 11)", "Payments per billing year (e.g. 11)")}
SUB["step"]["preis"]["data"] = PRICE_DATA
SUB["step"]["abschlag"]["data"] = ADV_DATA
SUB["step"]["zusammenfassung"] = {
    "title": T("Zusammenfassung", "Summary"),
    "description": T("**Perioden:** {perioden} (¹ = Rumpfjahr)\n\n**Preise:** {preis}\n\n**Abschläge:** {abschlag}\n\n**Erste Prognose:** {prognose}\n\nMit „OK“ wird der Zähler angelegt.",
                     "**Periods:** {perioden} (¹ = short year)\n\n**Prices:** {preis}\n\n**Advances:** {abschlag}\n\n**First forecast:** {prognose}\n\n“OK” creates the meter."),
}
SUB["step"]["preis_aendern"] = {"title": T("Preis ändern", "Change price"),
                                "description": T("Neuer Preis ab einem Datum; der bisherige endet am Vortag. Beendete Perioden bleiben unverändert. {error}", "New price from a date; the previous one ends the day before. Ended periods stay unchanged. {error}"),
                                "data": PRICE_DATA}
SUB["step"]["abschlag_aendern"] = {"title": T("Abschlag ändern", "Change advance payment"),
                                   "description": T("Neuer Abschlag ab einem Zahltag; frühere Termine bleiben unverändert. {error}", "New advance from a payment day; earlier dates stay unchanged. {error}"),
                                   "data": ADV_DATA}
SUB["step"]["anbieterwechsel"] = {"title": T("Anbieter wechseln", "Change supplier"),
                                  "description": T("Der bisherige Vertrag endet am Vortag des Wechsels (Schlussrechnung). Die Wechselablesung ist optional; liegt der Wechsel in der Zukunft, trägst du sie danach mit der Aktion „Ablesung hinzufügen“ nach. {error}",
                                                   "The current contract ends the day before the switch (final bill). The switch reading is optional; if the switch is in the future, add it afterwards with the action “Add reading”. {error}"),
                                  "data": {"switch_date": T("Erster Liefertag beim neuen Anbieter", "First day with the new supplier"),
                                           "value": T("Zählerstand zum Wechsel", "Meter reading at the switch"), "quality": T("Qualität", "Quality")}}
SUB["step"]["wechsel_vertrag"] = {"title": T("Neuer Vertrag", "New contract"),
                                  "description": T("Neuer Vertrag ab {datum}. Wann rechnet der neue Versorger ab? Stichtag als TT.MM (erster Tag der Periode).",
                                                   "New contract from {datum}. When does the new supplier bill? Fixed day as DD.MM (first day of the period)."),
                                  "data": dict(SUB["step"]["vertrag"]["data"])}
SUB["step"]["wechsel_preis"] = {"title": T("Preise und Abschlag des neuen Vertrags", "Prices and advance of the new contract"),
                                "description": T("Erste Perioden: {preview} (¹ = Rumpfjahr). {error}", "First periods: {preview} (¹ = short year). {error}"),
                                "data": {**PRICE_DATA, **ADV_DATA}}
SUB["error"]["billing_error"] = T("Nicht möglich, siehe Hinweis oben.", "Not possible, see the note above.")
SUB["error"]["switch_invalid"] = T("Wechsel an diesem Datum nicht möglich, siehe Hinweis oben.", "A switch on this date is not possible, see the note above.")
SUB["error"]["switch_reading_future"] = T("Der Wechsel liegt in der Zukunft: den Zählerstand bitte erst nach dem Wechsel eintragen (Aktion „Ablesung hinzufügen“).",
                                          "The switch is in the future: please enter the meter reading after the switch (action “Add reading”).")
SUB["step"]["stammdaten"].setdefault("data", {})
SUB["abort"].update({"price_saved": T("Der Preis wurde gespeichert.", "The price was saved."),
                     "advance_saved": T("Der Abschlag wurde gespeichert.", "The advance payment was saved."),
                     "switch_saved": T("Der Anbieterwechsel wurde gespeichert.", "The supplier change was saved."),
                     "not_loaded": T("Die Integration ist gerade nicht geladen. Bitte unter Einstellungen → Geräte & Dienste prüfen und neu laden.",
                                     "The integration is not loaded right now. Please check and reload it under Settings → Devices & services.")})


# ---------------------------------------------------------------- 0.8: Wärmeerzeuger, Fernwärme je MWh, neue Sensoren

S["config"]["step"]["abschluss"]["description"] = T(
    "Danach legst du beim Eintrag „Tarif-Cockpit“ über „Zähler hinzufügen“ deine Zähler an. Passend zu deinen Antworten: {zaehler}.\n\n"
    "Optional über „Wärmeerzeuger hinzufügen“: {erzeuger}.",
    "Afterwards add your meters via “Add meter” on the “Tarif-Cockpit” entry. Matching your answers: {zaehler}.\n\n"
    "Optional via “Add heat generator”: {erzeuger}.")
EXTRA_PRICE = {"price_unit": T("Arbeitspreis je", "Unit price per"), "demand_price": T("Leistungspreis je kW und Jahr", "Demand charge per kW and year"),
               "demand_kw": T("Anschlussleistung", "Connected load"), "calorific": T("Brennwert", "Calorific value"), "z_factor": T("Zustandszahl", "Conversion factor (Z)")}
for step in ("preis", "preis_aendern", "wechsel_preis"):
    S["config_subentries"]["zaehler"]["step"][step]["data"].update(EXTRA_PRICE)
S["config_subentries"]["zaehler"]["step"]["preis"].setdefault("data_description", {})["price_unit"] = T(
    "Fernwärme wird oft je MWh abgerechnet; gerechnet wird intern je kWh.", "District heating is often billed per MWh; internally it is calculated per kWh.")

GEN_LEISTUNG = {
    "nominal_kw": T("Nennleistung Heizbetrieb", "Rated power (heating)"),
    "min_kw": T("Kleinste Modulationsleistung", "Minimum modulation power"),
    "power_basis": T("Die Angabe ist die …", "The rating is the …"),
    "efficiency": T("Wirkungsgrad", "Efficiency"),
    "cop": T("COP/SCOP (Jahresarbeitszahl)", "COP/SCOP (seasonal)"),
    "central_dhw": T("Macht zentrales Warmwasser", "Produces central hot water"),
    "max_dhw_kw": T("Maximalleistung Warmwasser", "Maximum power hot water"),
}
GEN_LEISTUNG_DESC = {
    "nominal_kw": T("Steht auf dem Typschild oder im Datenblatt. Werte für den Heizbetrieb verwenden, z. B. 16 bei „5–16 kW“.",
                    "On the rating plate or data sheet. Use the values for heating, e.g. 16 for “5–16 kW”."),
    "min_kw": T("Optional, z. B. 5 bei „5–16 kW“.", "Optional, e.g. 5 for “5–16 kW”."),
    "efficiency": T("Annahme, bis Messwerte da sind. Gastherme bezogen auf den Heizwert (≈ 0,9), Kaminofen ≈ 0,75.",
                    "Assumption until measurements exist. Gas boiler based on net calorific value (≈ 0.9), wood stove ≈ 0.75."),
    "cop": T("Annahme, bis ein Wärmemengenzähler da ist.", "Assumption until a heat meter exists."),
    "max_dhw_kw": T("Optional: Spitzen beim Warmwasser gelten dann nicht als Fehler.", "Optional: hot water peaks are then not flagged."),
}
GEN_ENT = {
    "energy": T("Eingesetzte Energie (kWh, z. B. Steckdose oder Zähler der Wärmepumpe)", "Energy input (kWh, e.g. smart plug or heat pump meter)"),
    "power": T("Leistung", "Power"),
    "heat": T("Erzeugte Wärme (Wärmemengenzähler)", "Heat produced (heat meter)"),
    "state": T("Betriebszustand (an/aus)", "Operating state (on/off)"),
    "room": T("Raumtemperatur am Aufstellort", "Room temperature where installed"),
    "modulation": T("Modulation (%)", "Modulation (%)"),
}
GEN_ENT_DESC = {
    "state": T("Z. B. ein Binärsensor „läuft“. Daraus kommen die Betriebsstunden.", "E.g. a binary sensor “running”. Operating hours come from it."),
    "room": T("Beim Kaminofen ohne Betriebszustand: Erkennung über den Temperaturanstieg.", "For a wood stove without operating state: detection by the temperature rise."),
}
GEN_OFEN = {
    "stove_detection": T("Ofenbetrieb erkennen über", "Detect stove operation by"),
    "stove_threshold_k": T("Anstieg in 30 Minuten", "Rise within 30 minutes"),
    "effective_share": T("Wirksamer Anteil", "Effective share"),
    "wood_price": T("Holzpreis", "Wood price"),
    "wood_price_unit": T("Preis je", "Price per"),
    "kg_per_rm": T("Gewicht je Raummeter", "Weight per stacked cubic metre"),
}
GEN_OFEN_DESC = {
    "stove_threshold_k": T("Nur in der Heizperiode. Üblich 1,5 K.", "Only in the heating season. Usually 1.5 K."),
    "effective_share": T("Welcher Teil der Ofenwärme die Heizung wirklich entlastet (Annahme, z. B. 0,6), bis es genug Vergleichstage gibt.",
                         "Which part of the stove heat really relieves the heating (assumption, e.g. 0.6) until there are enough comparison days."),
    "wood_price": T("Optional, für die geschätzten Holzkosten.", "Optional, for the estimated wood costs."),
    "kg_per_rm": T("Annahme: Buche/Hartholz ca. 400 kg je Raummeter.", "Assumption: beech/hardwood about 400 kg per stacked cubic metre."),
}
S["config_subentries"]["waermeerzeuger"] = {
    "initiate_flow": {"user": T("Wärmeerzeuger hinzufügen", "Add heat generator")},
    "entry_type": T("Wärmeerzeuger", "Heat generator"),
    "step": {
        "user": {"title": T("Wärmeerzeuger hinzufügen", "Add heat generator"),
                 "description": T("Optional: Heizung, Wärmepumpe, Split-Klima oder Kaminofen. Passend zu deinem Haushalt: {vorschlag}.",
                                  "Optional: boiler, heat pump, split air conditioner or wood stove. Matching your household: {vorschlag}."),
                 "data": {"kind": T("Art", "Type"), "name": T("Name", "Name")},
                 "data_description": {"name": T("Optional, sonst der Name der Art.", "Optional, otherwise the name of the type.")}},
        "zuordnung": {"title": T("Energie", "Energy"),
                      "description": T("Woher bekommt der Erzeuger seine Energie? Ein Split-Klima hängt meist am Haushaltsstrom.",
                                       "Where does the generator get its energy from? A split air conditioner usually runs on household electricity."),
                      "data": {"source": T("Energie aus", "Energy from")}},
        "leistung": {"title": T("Leistung", "Power"),
                     "description": T("Leistungsbereich im Heizbetrieb laut Typschild oder Datenblatt.", "Power range for heating according to the rating plate or data sheet."),
                     "data": GEN_LEISTUNG, "data_description": GEN_LEISTUNG_DESC},
        "entitaeten": {"title": T("Messwerte (optional)", "Measurements (optional)"),
                       "description": T("Je mehr gemessen wird, desto weniger Annahmen. Alles ist optional.", "The more is measured, the fewer assumptions. Everything is optional."),
                       "data": GEN_ENT, "data_description": GEN_ENT_DESC},
        "ofen": {"title": T("Kaminofen", "Wood stove"),
                 "description": T("Die Entlastung der Heizung wird gelernt, sobald es je 10 Tage mit und ohne Ofen bei ähnlichem Wetter gibt; bis dahin gilt eine Annahme aus der Nennleistung.",
                                  "The relief of the heating is learned once there are 10 days with and without the stove at similar weather; until then an assumption from the rated power applies."),
                 "data": GEN_OFEN, "data_description": GEN_OFEN_DESC},
        "zusammenfassung": {"title": T("Zusammenfassung", "Summary"),
                            "description": T("{annahmen}\n\nMit „OK“ wird der Wärmeerzeuger angelegt.", "{annahmen}\n\n“OK” creates the heat generator.")},
        "reconfigure": {"title": T("Wärmeerzeuger ändern", "Change heat generator"),
                        "data": {"name": T("Name", "Name"), **GEN_LEISTUNG, **GEN_ENT, **GEN_OFEN},
                        "data_description": {**GEN_LEISTUNG_DESC, **GEN_ENT_DESC, **GEN_OFEN_DESC}},
    },
    "error": {
        "min_above_nominal": T("Die kleinste Leistung ist größer als die Nennleistung.", "The minimum power is above the rated power."),
        "state_entity_missing": T("Dafür fehlt die Entität „Betriebszustand“ im Schritt davor.", "The “operating state” entity is missing in the previous step."),
        "room_entity_missing": T("Dafür fehlt die Entität „Raumtemperatur am Aufstellort“.", "The “room temperature where installed” entity is missing."),
        "stove_entity_required": T("Für den Kaminofen wird der Betriebszustand oder die Raumtemperatur am Aufstellort gebraucht, sonst lassen sich keine Ofenstunden erkennen.",
                                   "The wood stove needs the operating state or the room temperature where installed, otherwise no stove hours can be detected."),
    },
    "abort": {"reconfigure_successful": T("Der Wärmeerzeuger wurde geändert.", "The heat generator was changed.")},
}
S["selector"].update({
    "generator_kind": {"options": {
        "gas_boiler": T("Gastherme", "Gas boiler"), "air_air_hp": T("Split-Klima / Luft-Luft-Wärmepumpe", "Split air conditioner / air-to-air heat pump"),
        "water_hp": T("Wärmepumpe (Wasser)", "Heat pump (hydronic)"), "district_heating": T("Fernwärme", "District heating"),
        "fireplace": T("Kaminofen", "Wood stove"), "electric": T("Elektroheizung", "Electric heating")}},
    "power_basis": {"options": {"output": T("Nennwärmeleistung (Wärmeabgabe)", "Rated heat output"),
                                "input": T("Nennwärmebelastung (Gaseinsatz, Heizwert)", "Rated heat input (gas, net calorific value)")}},
    "stove_detection": {"options": {"entity": T("Betriebszustand-Entität", "Operating state entity"),
                                    "room": T("Temperaturanstieg im Raum", "Room temperature rise")}},
    "wood_price_unit": {"options": {"kg": T("kg", "kg"), "rm": T("Raummeter", "Stacked cubic metre")}},
    "price_unit": {"options": {"kwh": T("kWh", "kWh"), "mwh": T("MWh", "MWh")}},
})
S["entity"]["sensor"].update({
    "kennwert_temperaturbereinigt": {"name": T("Kennwert temperaturbereinigt", "Heat coefficient (indoor-adjusted)")},
    "energie_eingang": {"name": T("Eingesetzte Energie", "Energy input")},
    "waerme": {"name": T("Wärme", "Heat")},
    "entlastung": {"name": T("Entlastung", "Relief")},
    "betriebsstunden": {"name": T("Betriebsstunden", "Operating hours")},
    "betriebstage": {"name": T("Betriebstage", "Operating days")},
    "holz_geschaetzt": {"name": T("Holz (geschätzt)", "Wood (estimated)")},
    "holzkosten_geschaetzt": {"name": T("Holzkosten (geschätzt)", "Wood costs (estimated)")},
})


# ---------------------------------------------------------------- 0.9: Impulszähler, Abgleich, Brenner

ZS = S["config_subentries"]["zaehler"]
ZS["step"]["quelle"]["data"]["pulse_entity"] = T("Impulszähler (statt Zählerstand-Sensor)", "Pulse counter (instead of a meter sensor)")
ZS["step"]["quelle"].setdefault("data_description", {})["pulse_entity"] = T(
    "Z. B. ESPHome-Impulszähler oder Zähler-Helfer, der die Impulse des Zählers zählt. Die Impulskonstante folgt im nächsten Schritt.",
    "E.g. an ESPHome pulse counter or counter helper counting the meter's pulses. The pulse constant follows in the next step.")
PULSE = {"pulse_constant": T("Impulskonstante", "Pulse constant"), "pulse_mode": T("Angabe als", "Given as")}
PULSE_DESC = {"pulse_constant": T("Steht auf dem Zähler, z. B. „1 Imp = 0,01 m³“ (dann 0,01 und „Einheit je Impuls“) oder „100 Imp/m³“.",
                                  "On the meter, e.g. “1 imp = 0.01 m³” (then 0.01 and “unit per pulse”) or “100 imp/m³”.")}
for step in ("einheit", "stammdaten"):
    ZS["step"][step]["data"].update(PULSE)
    ZS["step"][step].setdefault("data_description", {}).update(PULSE_DESC)
ZS["error"]["entity_or_pulses"] = T("Bitte entweder einen Zählerstand-Sensor oder einen Impulszähler wählen, nicht beides.",
                                    "Please choose either a meter sensor or a pulse counter, not both.")
S["selector"]["pulse_mode"] = {"options": {"per_unit": T("Impulse je Einheit (z. B. 100 Imp/m³)", "Pulses per unit (e.g. 100 imp/m³)"),
                                           "per_pulse": T("Einheit je Impuls (z. B. 0,01 m³/Imp)", "Unit per pulse (e.g. 0.01 m³/imp)")}}
S["issues"]["abgleich_abweichung"] = {
    "title": T("{meter}: Sensor weicht von der Ablesung ab", "{meter}: sensor differs from the reading"),
    "description": T("Zwischen den Ablesungen vom {von} bis {bis} hat der Sensor {pct} % gegenüber der abgelesenen Menge gezählt "
                     "(fehlend: {fehlt} {unit}). Angeglichen: {angeglichen}. Ursachen: verlorene Impulse, falsche Impulskonstante, "
                     "Zählertausch oder eine falsch eingetragene Ablesung. Der Hinweis verschwindet, wenn die nächste Ablesung wieder "
                     "unter 2 % liegt.",
                     "Between the readings from {von} to {bis} the sensor counted {pct} % relative to the read quantity "
                     "(missing: {fehlt} {unit}). Adjusted: {angeglichen}. Causes: lost pulses, wrong pulse constant, meter replacement or "
                     "a wrongly entered reading. The notice disappears once the next reading is below 2 % again."),
}
S["entity"]["sensor"].update({
    "abgleich": {"name": T("Abgleich mit Ablesung", "Reconciliation with reading")},
    "gasleistung": {"name": T("Gasleistung", "Gas power")},
    "brennerlaufzeit": {"name": T("Brennerlaufzeit", "Burner run time")},
    "brennerstarts": {"name": T("Brennerstarts", "Burner starts")},
})

# ---------------------------------------------------------------- 1.0: Kündigungsfrist, Archiv, Übernahme aus 0.3
TERMS = {"min_term_months": T("Mindestlaufzeit (Monate)", "Minimum term (months)"), "notice_period_weeks": T("Kündigungsfrist (Wochen)", "Notice period (weeks)")}
TERMS_DESC = {"min_term_months": T("Leer lassen, wenn unbekannt. Ohne Angaben gibt es keine Erinnerung an die Kündigungsfrist.",
                                   "Leave empty if unknown. Without it there is no notice-period reminder."),
              "notice_period_weeks": T("Wie viele Wochen vor Vertragsende muss gekündigt werden? (6 Wochen ≈ 1,5 Monate)",
                                       "How many weeks before the contract end must you cancel? (6 weeks ≈ 1.5 months)")}
for step in ("vertrag", "wechsel_vertrag"):
    SUB["step"][step]["data"].update(TERMS)
    SUB["step"][step].setdefault("data_description", {}).update(TERMS_DESC)
SUB["step"]["reconfigure"]["menu_options"]["vertrag_aendern"] = T("Vertrag ändern (Tarif, Laufzeit, Kündigungsfrist)", "Change contract (tariff, term, notice period)")
SUB["step"]["vertrag_aendern"] = {"title": T("Vertrag ändern", "Change contract"),
                                  "description": T("Laufender Vertrag bei {lieferant} seit {beginn}. Perioden, Preise und Abschläge bleiben unverändert.",
                                                   "Current contract with {lieferant} since {beginn}. Periods, prices and advances stay unchanged."),
                                  "data": {"tariff": T("Tarif", "Tariff"), **TERMS}, "data_description": TERMS_DESC}
SUB["abort"]["contract_saved"] = T("Der Vertrag wurde gespeichert.", "The contract was saved.")
SUB["abort"]["no_contract"] = T("Für diesen Zähler gibt es noch keinen Vertrag.", "This meter has no contract yet.")
SV = S["services"]
SV["add_folgevertrag"]["fields"].update({
    "mindestlaufzeit": {"name": T("Mindestlaufzeit", "Minimum term"), "description": T("In Monaten.", "In months.")},
    "kuendigungsfrist": {"name": T("Kündigungsfrist", "Notice period"), "description": T("In Wochen vor Vertragsende.", "In weeks before the contract end.")},
})
ENT = lambda de, en: {"name": T(de, en), "description": T(f"Helfer aus 0.3: {de}.", f"Helper from 0.3: {en}.")}
SV["uebernahme_v03"] = {
    "name": T("Übernahme aus Version 0.3", "Take over from version 0.3"),
    "description": T("Liest die Helfer der Template-Version 0.3 (Abschlag, Preise, Startstand …) und übernimmt sie in einen Zähler. Antwort: übernommene und übersprungene Werte.",
                     "Reads the helpers of the template version 0.3 (advance, prices, starting reading …) and takes them over into a meter. Response: values taken over and skipped."),
    "fields": {
        "zaehler": {"name": T("Zähler", "Meter"), "description": T("Zähler-Gerät des Tarif-Cockpits.", "Tarif-Cockpit meter device.")},
        "ab": {"name": T("Gültig ab", "Valid from"), "description": T("Standard: Abrechnungsbeginn bzw. Beginn der laufenden Periode.", "Default: billing start or start of the current period.")},
        "abschlag": ENT("Abschlag", "Advance payment"), "zahltag": ENT("Zahltag", "Payment day"),
        "arbeitspreis": ENT("Arbeitspreis", "Unit price"), "grundpreis": ENT("Grundpreis je Monat", "Standing charge per month"),
        "startstand": ENT("Zählerstand zu Abrechnungsbeginn", "Meter reading at billing start"),
        "abrechnungsbeginn": ENT("Abrechnungsbeginn", "Billing start"),
        "brennwert": ENT("Brennwert", "Calorific value"), "zustandszahl": ENT("Zustandszahl", "Conversion factor"),
    },
}
S["issues"]["kuendigungsfrist"] = {
    "title": T("{meter}: Kündigungsfrist endet bald", "{meter}: notice period ends soon"),
    "description": T("Der Vertrag bei {lieferant} endet am {ende}. Wer wechseln möchte, muss bis {bis} kündigen (noch {tage} Tage). "
                     "Der Hinweis verschwindet nach Ablauf der Frist oder wenn du Laufzeit bzw. Frist unter „Vertrag ändern“ anpasst.",
                     "The contract with {lieferant} ends on {ende}. To switch, cancel by {bis} ({tage} days left). "
                     "The notice disappears after the deadline or when you adjust term or notice period under “Change contract”."),
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
