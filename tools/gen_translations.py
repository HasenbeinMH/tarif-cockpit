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
                "description": T("Wann rechnet dein Versorger ab? Bei „fester Stichtag“ den **ersten Tag** des neuen Abrechnungszeitraums als TT.MM angeben: Endet deine Abrechnung am 30.06., ist das der 01.07. Bei „von Hand“ das Ende der ersten Periode, weitere Perioden mit der Aktion „Periode anhängen“.",
                                 "When does your supplier bill? For “fixed day” enter the **first day** of the new billing period as DD.MM: if your bill ends on 30.06., that is 01.07. For “manual” enter the end of the first period; add further periods with the action “Append period”."),
                "data": {"supplier": T("Lieferant", "Supplier"), "tariff": T("Tarif", "Tariff"), "start_date": T("Vertragsbeginn", "Contract start"),
                         "billing_rule": T("Abrechnung", "Billing"), "fixed_day": T("Beginn des Abrechnungszeitraums (TT.MM)", "Start of the billing period (DD.MM)"),
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
                "stichtag": {"name": T("Stichtag", "Fixed day"), "description": T("Bei „fester Stichtag“: erster Tag der Periode als TT.MM (Abrechnung zum 30.06. → 01.07.).", "For “fixed day”: first day of the period as DD.MM (bill ends 30.06. → 01.07.).")},
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
SUB["step"]["reconfigure"]["menu_options"]["vertrag_aendern"] = T("Vertrag ändern (Tarif, Abrechnung, Laufzeit, Kündigungsfrist)",
                                                                  "Change contract (tariff, billing, term, notice period)")
SUB["step"]["vertrag_aendern"] = {"title": T("Vertrag ändern", "Change contract"),
                                  "description": T("Laufender Vertrag bei {lieferant} seit {beginn}, laufender Abrechnungszeitraum {periode}. Preise und Abschläge bleiben unverändert. Die Abrechnung lässt sich nur ändern, solange noch kein Zeitraum dieses Vertrags beendet ist.",
                                                   "Current contract with {lieferant} since {beginn}, current billing period {periode}. Prices and advances stay unchanged. Billing can only be changed while no period of this contract has ended."),
                                  "data": {"tariff": T("Tarif", "Tariff"), **TERMS, "billing_rule": T("Abrechnung", "Billing"),
                                           "fixed_day": T("Beginn des Abrechnungszeitraums (TT.MM)", "Start of the billing period (DD.MM)")},
                                  "data_description": {**TERMS_DESC, "fixed_day": T("Nur bei „fester Stichtag“: erster Tag des neuen Zeitraums, z. B. 01.07. bei Abrechnung zum 30.06.",
                                                                                    "Only for “fixed day”: first day of the new period, e.g. 01.07. if the bill ends on 30.06.")}}
SUB["error"]["periods_locked"] = T("Von diesem Vertrag ist schon ein Abrechnungszeitraum beendet; die Abrechnung bleibt deshalb, wie sie ist.",
                                   "A billing period of this contract has already ended, so billing stays as it is.")
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


# ---------------------------------------------------------------- 1.0.1: Arbeitspreis in Cent je kWh
WORK_DESC = T("In Cent je kWh wie auf Vertrag und Rechnung, z. B. 31,54. Wasser in Euro je m³, Fernwärme je MWh in Euro.",
              "In cents per kWh as on contract and bill, e.g. 31.54. Water in euros per m³, district heating per MWh in euros.")
for step in ("preis", "preis_aendern", "wechsel_preis"):
    S["config_subentries"]["zaehler"]["step"][step].setdefault("data_description", {})["work_price"] = WORK_DESC
S["config_subentries"]["zaehler"]["error"]["work_price_cents"] = T(
    "Der Arbeitspreis wird in Cent je kWh eingegeben: 31,54 statt 0,3154.", "The unit price is entered in cents per kWh: 31.54 instead of 0.3154.")
S["selector"]["price_unit"] = {"options": {"kwh": T("Cent je kWh", "cents per kWh"), "mwh": T("Euro je MWh", "euros per MWh")}}
S["services"]["set_preis"]["fields"]["arbeitspreis"]["description"] = T(
    "In Euro je kWh (Wasser je m³), z. B. 0,3154. Die Dialoge fragen in Cent je kWh.",
    "In euros per kWh (water per m³), e.g. 0.3154. The dialogs ask in cents per kWh.")


# ---------------------------------------------------------------- 1.0.2: eigener Knopf „Unterzähler hinzufügen“
S["config_subentries"]["unterzaehler"] = {
    "initiate_flow": {"user": T("Unterzähler hinzufügen", "Add sub-meter")},
    "entry_type": T("Unterzähler", "Sub-meter"),
    "step": {
        "user": {"title": T("Unterzähler hinzufügen", "Add sub-meter"),
                 "description": T("Ein Unterzähler misst einen Teil des Hauptzählers, z. B. die Wallbox hinter dem Stromzähler oder den Gartenwasserzähler. "
                                  "Er hat keinen eigenen Vertrag: Kosten und Abschläge bleiben beim Hauptzähler, getrennt wird die Prognose.",
                                  "A sub-meter measures part of a main meter, e.g. the wallbox behind the electricity meter or the garden water meter. "
                                  "It has no contract of its own: costs and advances stay with the main meter, only the forecast is split."),
                 "data": {"role": T("Art", "Kind")}},
        "details": {"title": T("Unterzähler", "Sub-meter"),
                    "description": T("Sensor mit der laufenden Summe (z. B. Lademenge gesamt der Wallbox) und der Hauptzähler, hinter dem er hängt.",
                                     "Sensor with the running total (e.g. total energy charged by the wallbox) and the main meter it sits behind."),
                    "data": {"name": T("Name", "Name"), "entity": T("Zählerstand-Sensor", "Meter reading sensor"), "unit": T("Einheit", "Unit"),
                             "parent": T("Hauptzähler", "Main meter")}},
        "reconfigure": {"title": T("Unterzähler ändern", "Change sub-meter"),
                        "description": T("Für einen anderen Sensor den Unterzähler löschen und neu anlegen.", "For a different sensor, delete the sub-meter and add it again."),
                        "data": {"name": T("Name", "Name"), "parent": T("Hauptzähler", "Main meter")}},
    },
    "error": {"already_configured": T("Dieser Sensor ist schon als Zähler eingerichtet.", "This sensor is already set up as a meter.")},
    "abort": {"no_main_meter": T("Lege zuerst den Hauptzähler an (Strom für eine Wallbox, Wasser für einen Gartenzähler).",
                                 "Add the main meter first (electricity for a wallbox, water for a garden meter)."),
              "reconfigure_successful": T("Gespeichert.", "Saved.")},
}
S["config_subentries"]["zaehler"]["step"]["quelle"]["data"].pop("role", None)
S["config_subentries"]["zaehler"]["step"]["quelle"].get("data_description", {}).pop("role", None)


# ---------------------------------------------------------------- 1.1: Jahresabrechnung, Staffel/Rundung, Heizlast
DESIGN = T("Normaußentemperatur", "Design outdoor temperature")
DESIGN_DESC = T("Für die Heizlast: kälteste Auslegungstemperatur deiner Region (Deutschland etwa −10 bis −16 °C, oft −12 °C).",
                "For the heat load: the coldest design temperature of your region (Germany about −10 to −16 °C, often −12 °C).")
for step in (S["config"]["step"]["klima"], S["options"]["step"]["init"]):
    step["data"]["design_temp"] = DESIGN
    step.setdefault("data_description", {})["design_temp"] = DESIGN_DESC

ZS = S["config_subentries"]["zaehler"]
ZS["step"]["reconfigure"]["menu_options"]["rechnung_erfassen"] = T("Rechnung erfassen (Jahresabrechnung)", "Enter invoice (annual bill)")
ZS["step"]["rechnung_erfassen"] = {
    "title": T("Rechnung erfassen", "Enter invoice"),
    "description": T("Werte von der Jahresabrechnung. Pflicht sind Zeitraum und Betrag (Gesamtkosten brutto); alles andere hilft beim Vergleich. "
                     "Anfangs- und Endstand werden Ablesungen. Auch ältere Rechnungen vor dem Vertragsbeginn sind willkommen: Sie dienen als Lerndaten "
                     "und prüfen die Ersatzquelle. Weicht die Rechnung ab, steht unter Reparaturen ein Vorschlag zum Übernehmen.",
                     "Values from the annual bill. Period and amount (total gross costs) are required; everything else helps the comparison. "
                     "Start and end readings become readings. Older bills from before the contract start are welcome: they serve as learning data "
                     "and check the fallback source. If the bill differs, a suggestion to apply appears under Repairs."),
    "data": {
        "invoice_date": T("Rechnungsdatum", "Invoice date"), "period_from": T("Zeitraum von", "Period from"),
        "period_to": T("Zeitraum bis", "Period to"), "amount": T("Gesamtkosten (brutto)", "Total costs (gross)"),
        "start_reading": T("Anfangsstand", "Start reading"), "end_reading": T("Endstand", "End reading"),
        "readings_estimated": T("Stände laut Rechnung geschätzt", "Readings estimated by the supplier"),
        "quantity": T("Verbrauch (Zählereinheit)", "Consumption (meter unit)"), "quantity_kwh": T("Verbrauch in kWh", "Consumption in kWh"),
        "calorific": T("Brennwert", "Calorific value"), "z_factor": T("Zustandszahl", "Conversion factor"),
        "work_cost": T("Kosten Arbeitspreis (brutto)", "Unit price costs (gross)"),
        "base_cost": T("Kosten Grund- und Messpreis (brutto)", "Standing and metering charge (gross)"),
        "advances_paid": T("Gezahlte Abschläge", "Advances paid"),
    },
    "data_description": {
        "amount": T("Gesamtkosten des Zeitraums, nicht die Nachzahlung.", "Total costs of the period, not the balance due."),
        "quantity": T("Nur nötig, wenn keine Stände auf der Rechnung stehen.", "Only needed if the bill shows no readings."),
    },
}
ZS["error"]["period_order"] = T("„Zeitraum bis“ liegt vor „Zeitraum von“.", "“Period to” is before “Period from”.")
ZS["error"]["tiers_order"] = T("Die Stufen müssen aufsteigen (Stufe 2 bis über Stufe 1 bis).", "Tiers must ascend (tier 2 limit above tier 1 limit).")
ZS["abort"]["invoice_saved"] = T("Rechnung gespeichert. Abweichung der Menge: {abweichung}, neue Ablesungen: {ablesungen}, Vorschläge: {vorschlaege} "
                                 "(stehen unter Einstellungen → Reparaturen).",
                                 "Invoice saved. Quantity deviation: {abweichung}, new readings: {ablesungen}, suggestions: {vorschlaege} "
                                 "(see Settings → Repairs).")
ZS["abort"]["price_not_saved"] = T("Preis nicht gespeichert: {error}", "Price not saved: {error}")
ZS["abort"]["invoice_not_saved"] = T("Rechnung nicht gespeichert: {error}", "Invoice not saved: {error}")
ZS["error"]["tier_incomplete"] = T("Je Stufe Menge und Preis angeben; „darüber“ nur mit mindestens einer Stufe.",
                                   "Give quantity and price per tier; “above” only with at least one tier.")
ZS["step"]["preis_aendern"]["data"]["tiers_rounding"] = T("Staffel oder Rundung festlegen", "Set tiers or rounding")
ZS["step"]["preis_aendern"].setdefault("data_description", {})["tiers_rounding"] = T(
    "Nur nötig, wenn der Versorger nach Mengenstufen abrechnet oder anders rundet. Ohne Haken bleibt die Rundung des laufenden Preises; hat er eine Staffel, folgt der Schritt immer.",
    "Only needed if the supplier bills by quantity tiers or rounds differently. Unticked, the rounding of the current price is kept; with tiers the step always follows.")
ZS["step"]["staffel_rundung"] = {
    "title": T("Staffel und Rundung", "Tiers and rounding"),
    "description": T("Staffel: Arbeitspreis bis zu einer Menge je Jahr (ein Rumpfjahr anteilig), darüber der nächste Preis (ohne „darüber“ der Arbeitspreis von vorher). Leer lassen für einen einheitlichen Preis. "
                     "Rundung: wie auf der Rechnung, damit der Vergleich aufgeht.",
                     "Tiers: unit price up to a quantity per year (a short year pro rata), above that the next price. Leave empty for a single price. "
                     "Rounding: as on the bill so the comparison adds up. Without “above”, the unit price from before applies above the last tier."),
    "data": {
        "tier1_upto": T("Stufe 1 bis", "Tier 1 up to"), "tier1_price": T("Stufe 1 Arbeitspreis", "Tier 1 unit price"),
        "tier2_upto": T("Stufe 2 bis", "Tier 2 up to"), "tier2_price": T("Stufe 2 Arbeitspreis", "Tier 2 unit price"),
        "tier3_price": T("darüber Arbeitspreis", "Above that unit price"), "tier_mode": T("Abrechnung der Staffel", "Tier billing"),
        "days_per_year": T("Tage je Jahr für den Grundpreis", "Days per year for the standing charge"),
        "base_by": T("Grundpreis", "Standing charge"),
        "quantity_decimals": T("Menge runden auf Stellen", "Round quantity to decimals"),
        "money_decimals": T("Beträge runden auf Stellen", "Round amounts to decimals"),
    },
    "data_description": {
        "quantity_decimals": T("0 = ganze kWh bzw. m³. Leer = nicht runden.", "0 = whole kWh or m³. Empty = no rounding."),
        "money_decimals": T("2 = je Position auf Cent. Leer = nicht runden.", "2 = each item to the cent. Empty = no rounding."),
    },
}
S["selector"].update({
    "tier_mode": {"options": {"block": T("Je Stufe zum eigenen Preis", "Each tier at its own price"),
                              "total": T("Ganze Menge zum Preis der erreichten Stufe", "Whole quantity at the price of the tier reached")}},
    "days_per_year": {"options": {"average": T("365,25 (Mittel)", "365.25 (average)"), "365": T("365", "365"),
                                  "actual": T("Tatsächliche Tage (365 oder 366)", "Actual days (365 or 366)")}},
    "base_by": {"options": {"day": T("Je Tag (Monatspreis × 12 ÷ Tage je Jahr)", "Per day (monthly price × 12 ÷ days per year)"),
                            "month": T("Je Monat anteilig nach Tagen des Monats", "Per month, pro rata by days of the month")}},
})
S["entity"]["sensor"]["heizlast"] = {"name": T("Heizlast", "Heat load")}
S["issues"]["rechnung_abweichung"] = {
    "title": T("{meter}: Rechnung {von}–{bis} weicht ab", "{meter}: invoice {von}–{bis} differs"),
    "fix_flow": {
        "step": {"confirm": {
            "title": T("Vorschlag aus der Rechnung übernehmen", "Apply suggestion from the invoice"),
            "description": T("Rechnung {von}–{bis}: {menge_rechnung} {einheit}, eigene Daten: {menge_eigen} {einheit} (Abweichung {abweichung} %).\n\n"
                             "Vorschlag: {vorschlaege}\n\nHinweise: {hinweise}\n\n„OK“ übernimmt den Vorschlag (Brennwert gilt für den Rechnungszeitraum, "
                             "der Faktor für die Ersatzquelle). Abgeschlossene Perioden bleiben unverändert.",
                             "Invoice {von}–{bis}: {menge_rechnung} {einheit}, own data: {menge_eigen} {einheit} (deviation {abweichung} %).\n\n"
                             "Suggestion: {vorschlaege}\n\nNotes: {hinweise}\n\n“OK” applies the suggestion (calorific value for the invoice period, "
                             "the factor for the fallback source). Closed periods stay unchanged."),
        }},
        "abort": {"invoice_gone": T("Die Rechnung passt inzwischen oder wurde entfernt.", "The invoice now matches or was removed.")},
    },
}
S["issues"]["rechnung_abweichung_hinweis"] = {
    "title": T("{meter}: Rechnung {von}–{bis} prüfen", "{meter}: check invoice {von}–{bis}"),
    "description": T("Rechnung {von}–{bis}: {menge_rechnung} {einheit}, eigene Daten: {menge_eigen} {einheit} (Abweichung {abweichung} %). "
                     "Hinweise: {hinweise}. Preise änderst du unter „Preis ändern“ (auch Staffel und Rundung), Ablesungen mit „Ablesung hinzufügen“.",
                     "Invoice {von}–{bis}: {menge_rechnung} {einheit}, own data: {menge_eigen} {einheit} (deviation {abweichung} %). "
                     "Notes: {hinweise}. Change prices under “Change price” (also tiers and rounding), readings with “Add reading”."),
}
SV = S["services"]
SV["add_rechnung"]["fields"].update({
    "menge": {"name": T("Verbrauch", "Consumption"), "description": T("Menge in der Zählereinheit (m³, kWh).", "Quantity in the meter unit (m³, kWh).")},
    "menge_kwh": {"name": T("Verbrauch in kWh", "Consumption in kWh"), "description": T("Abgerechnete kWh (Gas nach Brennwert und Zustandszahl).", "Billed kWh (gas after calorific value and conversion factor).")},
    "stand_anfang": {"name": T("Anfangsstand", "Start reading"), "description": T("Wird eine Ablesung zum Beginn des Zeitraums.", "Becomes a reading at the start of the period.")},
    "stand_ende": {"name": T("Endstand", "End reading"), "description": T("Wird eine Ablesung zum Ende des Zeitraums.", "Becomes a reading at the end of the period.")},
    "staende_geschaetzt": {"name": T("Stände geschätzt", "Readings estimated"), "description": T("Die Stände der Rechnung sind geschätzt.", "The readings on the bill are estimated.")},
    "brennwert": {"name": T("Brennwert", "Calorific value"), "description": T("Laut Rechnung, kWh/m³.", "As on the bill, kWh/m³.")},
    "zustandszahl": {"name": T("Zustandszahl", "Conversion factor"), "description": T("Laut Rechnung.", "As on the bill.")},
    "arbeitspreis_kosten": {"name": T("Kosten Arbeitspreis", "Unit price costs"), "description": T("Brutto, in Euro.", "Gross, in euros.")},
    "grundpreis_kosten": {"name": T("Kosten Grund- und Messpreis", "Standing charge costs"), "description": T("Brutto, in Euro.", "Gross, in euros.")},
    "abschlaege_bezahlt": {"name": T("Gezahlte Abschläge", "Advances paid"), "description": T("Summe laut Rechnung.", "Total as on the bill.")},
    "notiz": {"name": T("Notiz", "Note"), "description": T("Freitext.", "Free text.")},
})
SV["add_rechnung"]["fields"]["betrag"]["description"] = T("Gesamtkosten des Zeitraums (brutto), nicht die Nachzahlung.", "Total costs of the period (gross), not the balance due.")
SV["set_preis"]["fields"].update({
    "staffel": {"name": T("Staffel", "Tiers"), "description": T("Liste von Stufen mit „bis“ (Menge je Jahr) und „preis“ (Euro je kWh bzw. m³); die letzte Stufe ohne „bis“. Beispiel in YAML: - bis: 1000 / preis: 0.32, dann - preis: 0.29.",
                                                                "List of tiers with “bis” (quantity per year) and “preis” (euros per kWh or m³); the last tier without “bis”. YAML example: - bis: 1000 / preis: 0.32, then - preis: 0.29.")},
    "staffel_art": {"name": T("Abrechnung der Staffel", "Tier billing"), "description": T("block: je Stufe; total: ganze Menge zum Preis der erreichten Stufe.", "block: per tier; total: whole quantity at the tier reached.")},
    "rundung_tage": {"name": T("Tage je Jahr", "Days per year"), "description": T("Für Grundpreis und Jahresbeträge.", "For standing charge and yearly amounts.")},
    "rundung_grundpreis": {"name": T("Grundpreis je", "Standing charge per"), "description": T("day oder month (anteilig nach Tagen des Monats).", "day or month (pro rata by days of the month).")},
    "rundung_menge_stellen": {"name": T("Menge runden", "Round quantity"), "description": T("Nachkommastellen der Menge je Preisstufe.", "Decimals of the quantity per tier.")},
    "rundung_betrag_stellen": {"name": T("Beträge runden", "Round amounts"), "description": T("Nachkommastellen je Position (2 = Cent).", "Decimals per item (2 = cents).")},
})


# ---------------------------------------------------------------- 1.2: Zeitfenster, § 14a, dynamisch, Vergleich, Kühlen, Leckage
COOL = T("Kühlgrenze", "Cooling limit")
COOL_DESC = T("Kühlgradtage für Klimageräte: Tage mit einem Tagesmittel darüber zählen als Kühltage (Standard 22 °C).",
              "Cooling degree days for air conditioners: days with a mean above this count as cooling days (default 22 °C).")
for step in (S["config"]["step"]["klima"], S["options"]["step"]["init"]):
    step["data"]["cooling_limit"] = COOL
    step.setdefault("data_description", {})["cooling_limit"] = COOL_DESC
ZS = S["config_subentries"]["zaehler"]
ZS["step"]["preis_aendern"]["data"]["windows_14a"] = T("Zeitfenster, § 14a oder dynamischer Preis", "Time windows, § 14a or dynamic price")
ZS["step"]["preis_aendern"]["data_description"]["windows_14a"] = T(
    "HT/NT, dynamischer Tarif (Börsenpreis je Viertelstunde) oder § 14a (Pauschale, zeitvariable Netzentgelte). Hat der laufende Preis schon so etwas, folgt der Schritt immer.",
    "HT/NT, dynamic tariff (exchange price per quarter hour) or § 14a (flat rate, time-variable grid fees). If the current price already has one, the step always follows.")
ZS["step"]["zeitfenster"] = {
    "title": T("Zeitfenster, § 14a, dynamisch", "Time windows, § 14a, dynamic"),
    "description": T("HT/NT: Der Arbeitspreis von vorher gilt als NT, hier der HT-Preis und seine Zeit. Dynamisch: Preis-Entität (z. B. EPEX Spot) und Aufschlag "
                     "(Netzentgelt, Steuern, Marge). § 14a Modul 1: Pauschale je Jahr. Modul 3: Zu- bzw. Abschlag in bestimmten Zeiten und Quartalen. "
                     "Modul 2 (eigener Zähler) legst du als eigenen Zähler mit eigenem Vertrag an.",
                     "HT/NT: the unit price from before counts as NT, here the HT price and its time. Dynamic: price entity (e.g. EPEX Spot) and markup "
                     "(grid fee, taxes, margin). § 14a module 1: flat rate per year. Module 3: surcharge or discount at certain times and quarters. "
                     "Module 2 (own meter) is added as a separate meter with its own contract."),
    "data": {
        "mode": T("Arbeitspreis", "Unit price"), "ht_price": T("HT-Preis", "Peak price"), "ht_start": T("HT von (HH:MM)", "Peak from (HH:MM)"),
        "ht_end": T("HT bis (HH:MM)", "Peak until (HH:MM)"), "ht_days": T("HT an", "Peak on"),
        "dyn_entity": T("Preis-Entität", "Price entity"), "dyn_markup": T("Aufschlag", "Markup"),
        "rebate_14a": T("§ 14a Modul 1: Pauschale", "§ 14a module 1: flat rate"),
        "m3_nt_start": T("Modul 3 Niedertarif von", "Module 3 low tariff from"), "m3_nt_end": T("Modul 3 Niedertarif bis", "Module 3 low tariff until"),
        "m3_nt_delta": T("Modul 3 Niedertarif Abschlag (negativ)", "Module 3 low tariff discount (negative)"),
        "m3_ht_start": T("Modul 3 Hochtarif von", "Module 3 high tariff from"), "m3_ht_end": T("Modul 3 Hochtarif bis", "Module 3 high tariff until"),
        "m3_ht_delta": T("Modul 3 Hochtarif Zuschlag", "Module 3 high tariff surcharge"), "m3_quarters": T("Modul 3 in den Quartalen", "Module 3 in quarters"),
    },
    "data_description": {
        "dyn_markup": T("Was zum Börsenpreis dazukommt, brutto in ct/kWh. Enthält die Entität schon alles, 0.", "What is added to the exchange price, gross in ct/kWh. If the entity already includes everything, 0."),
        "rebate_14a": T("Jährliche Reduzierung des Netzentgelts, wird anteilig abgezogen.", "Yearly grid fee reduction, deducted pro rata."),
    },
}
ZS["error"]["time_format"] = T("Uhrzeit als HH:MM von 00:00 bis 23:59 (als Ende auch 24:00).", "Time as HH:MM from 00:00 to 23:59 (as end also 24:00).")
ZS["error"]["m3_times_missing"] = T("Für den Zu- bzw. Abschlag bitte von und bis angeben.", "Please give from and until for the surcharge or discount.")
ZS["step"]["zeitfenster"]["data"]["dyn_net"] = T("Preis der Entität ohne MwSt.", "Entity price excludes VAT")
ZS["step"]["zeitfenster"]["data_description"]["dyn_net"] = T("An bei Börsenpreisen wie EPEX Market Price (netto); dann kommt die MwSt. dazu. Aus bei Endpreisen inkl. MwSt.",
                                                             "On for exchange prices such as EPEX market price (net); VAT is then added. Off for final prices incl. VAT.")
ZS["step"]["stammdaten"]["data"]["comparison_net"] = T("Vergleich dynamisch: Preis ohne MwSt.", "Dynamic comparison: price excludes VAT")
ZS["step"]["stammdaten"]["data_description"]["comparison_net"] = T("An bei EPEX Market Price (netto). Der Aufschlag gilt brutto.", "On for EPEX market price (net). The markup is gross.")
ZS["error"]["required_for_htnt"] = T("Für HT/NT bitte den HT-Preis angeben.", "For HT/NT please enter the peak price.")
ZS["error"]["required_for_dynamic"] = T("Für den dynamischen Tarif bitte die Preis-Entität wählen.", "For the dynamic tariff please choose the price entity.")
ZS["step"]["stammdaten"]["data"].update({
    "comparison_entity": T("Vergleich dynamisch: Preis-Entität", "Dynamic comparison: price entity"),
    "comparison_markup": T("Vergleich dynamisch: Aufschlag", "Dynamic comparison: markup"),
    "comparison_base": T("Vergleich dynamisch: Grundpreis", "Dynamic comparison: base price"),
    "leak_threshold": T("Leckage-Schwelle", "Leak threshold"),
})
ZS["step"]["stammdaten"].setdefault("data_description", {}).update({
    "comparison_entity": T("Börsenpreis je Viertelstunde (z. B. EPEX Spot Market Price). Die Integration rechnet mit, was dein Verbrauch damit gekostet hätte.",
                           "Exchange price per quarter hour (e.g. EPEX Spot market price). The integration calculates what your consumption would have cost with it."),
    "comparison_markup": T("Netzentgelt, Steuern und Marge des Angebots, brutto in ct/kWh.", "Grid fee, taxes and margin of the offer, gross in ct/kWh."),
    "leak_threshold": T("Kleinster Verbrauch nachts (1–5 Uhr), ab dem drei Nächte hintereinander als Leckage gelten. Standard 5 L/h.",
                        "Smallest night-time flow (1–5 am) above which three nights in a row count as a leak. Default 5 L/h."),
})
S["selector"].update({
    "price_mode": {"options": {"keine": T("Einheitlich (nur § 14a, falls angegeben)", "Single price (only § 14a, if given)"),
                               "htnt": T("HT/NT", "Peak/off-peak"), "dynamisch": T("Dynamisch (Börsenpreis)", "Dynamic (exchange price)")}},
    "weekday": {"options": {"0": T("Montag", "Monday"), "1": T("Dienstag", "Tuesday"), "2": T("Mittwoch", "Wednesday"), "3": T("Donnerstag", "Thursday"),
                            "4": T("Freitag", "Friday"), "5": T("Samstag", "Saturday"), "6": T("Sonntag", "Sunday")}},
    "quarter": {"options": {"1": T("1. Quartal", "Q1"), "2": T("2. Quartal", "Q2"), "3": T("3. Quartal", "Q3"), "4": T("4. Quartal", "Q4")}},
})
S["entity"]["sensor"].update({
    "zeitfenster": {"name": T("Zeitfenster", "Time windows")},
    "mittelpreis": {"name": T("Mittlerer Strompreis", "Average electricity price")},
    "vergleich_dynamisch": {"name": T("Vergleich dynamischer Tarif", "Dynamic tariff comparison")},
})
S["entity"]["binary_sensor"] = {"leckage": {"name": T("Leckage-Verdacht", "Leak suspected")}}
S["issues"]["leckage"] = {
    "title": T("{meter}: Leckage-Verdacht", "{meter}: leak suspected"),
    "description": T("Seit {seit} fließt Wasser auch nachts bzw. ohne Pause (Art: {art}, kleinster Nachtverbrauch {liter} L/h). Bitte Hähne, Spülkästen und Leitungen prüfen. "
                     "Der Hinweis verschwindet, sobald es wieder Stunden ohne Verbrauch gibt.",
                     "Since {seit} water has been flowing at night or without a break (kind: {art}, smallest night flow {liter} L/h). Please check taps, cisterns and pipes. "
                     "The notice disappears once there are hours without consumption again."),
}
SV = S["services"]
SV["set_preis"]["fields"].update({
    "fenster": {"name": T("Zeitfenster", "Time windows"), "description": T("Liste mit name, von, bis (HH:MM), tage (0 = Montag), monate, preis (absolut, €/kWh) oder aufschlag (€/kWh).",
                                                                           "List with name, von, bis (HH:MM), tage (0 = Monday), monate, preis (absolute, €/kWh) or aufschlag (€/kWh).")},
    "pauschale_14a": {"name": T("§ 14a Pauschale", "§ 14a flat rate"), "description": T("Modul 1: Reduzierung je Jahr in Euro.", "Module 1: reduction per year in euros.")},
    "dynamisch_entitaet": {"name": T("Dynamisch: Preis-Entität", "Dynamic: price entity"), "description": T("Sensor mit dem Preis je Viertelstunde.", "Sensor with the price per quarter hour.")},
    "dynamisch_aufschlag": {"name": T("Dynamisch: Aufschlag", "Dynamic: markup"), "description": T("In Euro je kWh, brutto.", "In euros per kWh, gross.")},
})


# ---------------------------------------------------------------- 1.2.1: Grundpreis je Monat oder Jahr
S["selector"]["base_period"] = {"options": {"month": T("je Monat", "per month"), "year": T("je Jahr", "per year")}}
for step in ("preis", "preis_aendern", "wechsel_preis"):
    st_ = S["config_subentries"]["zaehler"]["step"][step]
    st_["data"]["base_price"] = T("Grundpreis", "Standing charge")
    st_["data"]["base_price_period"] = T("Grundpreis gilt", "Standing charge applies")
    st_.setdefault("data_description", {})["base_price_period"] = T(
        "Wie auf Vertrag oder Rechnung: je Monat oder je Jahr. Gerechnet wird je Monat (Jahresbetrag ÷ 12).",
        "As on contract or bill: per month or per year. Calculated per month (yearly amount ÷ 12).")
_sd = S["config_subentries"]["zaehler"]["step"]["stammdaten"]
_sd["data"]["comparison_base"] = T("Vergleich dynamisch: Grundpreis", "Dynamic comparison: standing charge")
_sd["data"]["comparison_base_period"] = T("Vergleich dynamisch: Grundpreis gilt", "Dynamic comparison: standing charge applies")



# ---------------------------------------------------------------- 1.2.2: gewogenes Holz am Kaminofen
S["services"]["holz_erfassen"] = {
    "name": T("Holz erfassen", "Log firewood"),
    "description": T("Trägt gewogenes Holz am Kaminofen ein: kg direkt oder Scheite × kg je Scheit. Mehrere Einträge eines Tages werden addiert. "
                     "Aus den Tagen mit Holz und Brennstunden lernt die Integration die Menge und Wärme je Brennstunde (ab 3 Tagen).",
                     "Logs weighed firewood for the stove: kg directly or logs × kg per log. Several entries of a day are added up. "
                     "From days with wood and burning hours the integration learns the amount and heat per burning hour (from 3 days)."),
    "fields": {
        "erzeuger": {"name": T("Kaminofen", "Stove"), "description": T("Kaminofen-Gerät des Tarif-Cockpits.", "Tarif-Cockpit stove device.")},
        "datum": {"name": T("Datum", "Date"), "description": T("Standard: heute.", "Default: today.")},
        "kg": {"name": T("Menge", "Amount"), "description": T("Gewogenes Holz in kg. 0 = an diesem Tag kein Holz.", "Weighed wood in kg. 0 = no wood on this day.")},
        "scheite": {"name": T("Scheite", "Logs"), "description": T("Anzahl Scheite. Ohne Menge: Scheite × kg je Scheit. Mit Menge: das Gewicht je Scheit wird gemerkt.",
                                                                "Number of logs. Without amount: logs × kg per log. With amount: the weight per log is remembered.")},
        "kg_je_scheit": {"name": T("kg je Scheit", "kg per log"), "description": T("Standard: das zuletzt angegebene Gewicht je Scheit.", "Default: the weight per log given last.")},
        "ersetzen": {"name": T("Tag ersetzen", "Replace day"),
                     "description": T("Ersetzt die bisherigen Einträge dieses Tages (zum Korrigieren). Ohne Menge und Scheite: Einträge des Tages entfernen.",
                                      "Replaces the previous entries of this day (to correct them). Without amount and logs: remove the day's entries.")},
        "notiz": {"name": T("Notiz", "Note"), "description": T("Freitext.", "Free text.")},
    },
}
S["exceptions"].update({
    "unknown_generator": {"message": T("Unbekannter Wärmeerzeuger: {id}", "Unknown heat generator: {id}")},
    "not_a_stove": {"message": T("Holz lässt sich nur an einem Kaminofen erfassen.", "Wood can only be logged for a stove.")},
    "wood_date_invalid": {"message": T("Das Datum muss zwischen heute und vor {days} Tagen liegen.", "The date must lie between today and {days} days ago.")},
    "wood_amount_missing": {"message": T("Bitte die Menge in kg oder die Anzahl Scheite angeben.", "Please give the amount in kg or the number of logs.")},
    "wood_kg_per_log_missing": {"message": T("Für Scheite ohne Menge wird das Gewicht je Scheit gebraucht (einmal angeben, danach wird es gemerkt).",
                                             "For logs without an amount the weight per log is needed (give it once, it is remembered afterwards).")},
})
S["entity"]["sensor"]["ofenleistung"] = {"name": T("Ofenleistung (gelernt)", "Stove output (learned)")}


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
