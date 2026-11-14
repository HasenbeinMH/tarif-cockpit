"""1.0: Archiv beendeter Perioden (vorläufig → abgeschlossen, unveränderlich), Urteils-Event, Kündigungsfrist, Übernahme aus 0.3,
Wettervorhersage, Diagnose geschwärzt, WebSocket archiv, Vertrag ändern."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from custom_components.tarif_cockpit.const import DOMAIN, EVENT_NOTICE, EVENT_VERDICT, ISSUE_NOTICE
from custom_components.tarif_cockpit.engine.model import PeriodStatus

from .conftest import HOUSEHOLD, make_entry, meter_device_id, meter_subentry, setup

TZ = ZoneInfo("Europe/Berlin")


def strom(start="2025-01-01", **contract):
    sub = meter_subentry("s1", "Strom", "strom", "kWh",
                         contract={"supplier": "Stadtwerke Muster", "start_date": start, "billing_rule": "calendar_year", **contract},
                         reading={"timestamp": f"{start}T00:00:00+01:00", "value": 1000.0, "quality": "real"})
    sub["data"]["initial_price"] = {"work_price": 0.30, "base_price": 10.0}
    return sub


async def _call(hass, service, data):
    return await hass.services.async_call(DOMAIN, service, data, blocking=True, return_response=True)


async def test_archive_provisional_then_final_and_frozen(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2025-12-20 12:00:00+01:00")
    entry = make_entry(strom())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "s1")
    await _call(hass, "set_abschlag", {"zaehler": dev, "ab": date(2025, 1, 1), "betrag": 80.0})
    await _call(hass, "add_ablesung", {"zaehler": dev, "stand": 3900.0, "zeitpunkt": datetime(2025, 12, 20, 10, tzinfo=TZ)})
    assert rt.coordinator.results["s1"].period.end_date == date(2025, 12, 31)
    # Periodenwechsel: vorläufiges Archiv mit Prognose-Schnappschuss
    freezer.move_to("2026-01-02 08:00:00+01:00")
    rt.coordinator.daily()
    await hass.async_block_till_done()
    p = next(p for p in rt.stored_periods("s1") if p.end_date == date(2025, 12, 31))
    assert p.status == PeriodStatus.CLOSING and p.archive["stand"] == "vorlaeufig" and p.archive["grund"] == "wartet_auf_endablesung"
    assert p.archive["kosten"]["gesamt"] > 0 and p.archive["prognosen"], p.archive
    assert p.archive["prognosen"][-1]["verdict"] is not None
    # Endablesung am 03.01.: im ±10-Tage-Fenster noch vorläufig, das Periodenende lässt sich noch verschieben
    freezer.move_to("2026-01-03 09:00:00+01:00")
    await _call(hass, "add_ablesung", {"zaehler": dev, "stand": 4000.0, "zeitpunkt": datetime(2026, 1, 3, 8, tzinfo=TZ)})
    rt.coordinator.daily()
    await hass.async_block_till_done()
    p = rt.stored_period(p.period_id)
    assert p.status == PeriodStatus.CLOSING and p.archive["grund"] == "endablesung"
    await _call(hass, "set_periodenende", {"zaehler": dev, "ende": date(2026, 1, 2)})
    rt.coordinator.daily()
    assert rt.stored_period(p.period_id).archive["ende"] == "2026-01-02"
    # nach dem Fenster endgültig
    freezer.move_to("2026-01-14 09:00:00+01:00")
    rt.coordinator.daily()
    await hass.async_block_till_done()
    p = rt.stored_period(p.period_id)
    assert p.status == PeriodStatus.CLOSED and p.archive["stand"] == "abgeschlossen" and p.archive["grund"] == "endablesung"
    assert p.end_reading is not None and p.archived_at is not None
    frozen = p.archive
    # danach unveränderlich: Preise, Ablesungen und Periodenende ändern nichts mehr
    await _call(hass, "add_ablesung", {"zaehler": dev, "stand": 4010.0, "zeitpunkt": datetime(2026, 1, 13, 8, 30, tzinfo=TZ)})
    rt.coordinator.daily()
    assert rt.stored_period(p.period_id).archive == frozen
    with pytest.raises(ServiceValidationError):
        await _call(hass, "set_periodenende", {"zaehler": dev, "ende": date(2026, 1, 3)})


async def test_early_reading_does_not_close(hass: HomeAssistant, freezer) -> None:
    """Eine Ablesung vor dem Periodenende schließt nicht ab, auch nicht nach dem Fenster."""
    freezer.move_to("2025-12-26 12:00:00+01:00")
    entry = make_entry(strom())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "s1")
    await _call(hass, "add_ablesung", {"zaehler": dev, "stand": 3900.0, "zeitpunkt": datetime(2025, 12, 25, 10, tzinfo=TZ)})
    freezer.move_to("2026-01-20 08:00:00+01:00")
    rt.coordinator.daily()
    p = next(p for p in rt.stored_periods("s1") if p.end_date == date(2025, 12, 31))
    assert p.status == PeriodStatus.CLOSING and p.archive["grund"] == "wartet_auf_endablesung"


async def test_websocket_archive(hass: HomeAssistant, freezer, hass_ws_client) -> None:
    freezer.move_to("2025-12-20 12:00:00+01:00")
    entry = make_entry(strom())
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "s1")
    await _call(hass, "set_abschlag", {"zaehler": dev, "ab": date(2025, 1, 1), "betrag": 80.0})
    freezer.move_to("2026-03-05 08:00:00+01:00")  # 60 Tage nach dem Ende → endgültig
    rt.coordinator.daily()
    await hass.async_block_till_done()
    freezer.move_to("2026-11-13 12:00:00+01:00")  # Zugangstoken des Test-Clients gilt nur ab „heute“
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": f"{DOMAIN}/archiv", "zaehler": dev})
    msg = await ws.receive_json()
    assert msg["success"], msg
    per = msg["result"]["perioden"]
    assert per[0]["status"] == "closed" and per[0]["archiv"]["grund"] == "frist_60_tage"
    assert "prognose_gegen_realitaet" in per[0]["archiv"]


async def test_verdict_event_only_on_change(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2026-06-15 12:00:00+02:00")
    events = []
    hass.bus.async_listen(EVENT_VERDICT, lambda e: events.append(e.data))
    entry = make_entry(strom(start="2026-01-01"))
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "s1")
    await _call(hass, "add_ablesung", {"zaehler": dev, "stand": 2500.0, "zeitpunkt": datetime(2026, 6, 15, 10, tzinfo=TZ)})
    await _call(hass, "set_abschlag", {"zaehler": dev, "ab": date(2026, 1, 1), "betrag": 120.0})
    first = rt.coordinator.results["s1"].balance.verdict
    assert first and not events or all(e["alt"] for e in events)
    events.clear()
    # deutlich teurer → Urteil kippt
    await _call(hass, "set_abschlag", {"zaehler": dev, "ab": date(2026, 1, 1), "betrag": 30.0})
    await hass.async_block_till_done()
    new = rt.coordinator.results["s1"].balance.verdict
    assert new != first
    assert events and events[-1]["alt"] == first and events[-1]["neu"] == new and events[-1]["device_id"] == dev


async def test_notice_period_attribute_issue_event(hass: HomeAssistant, freezer) -> None:
    freezer.move_to("2026-11-13 12:00:00+01:00")
    events = []
    hass.bus.async_listen(EVENT_NOTICE, lambda e: events.append(e.data))
    # Mindestlaufzeit 12 Monate ab 2026-01-01 → Ende 2026-12-31; 6 Wochen Frist → kündigen bis 2026-11-19
    entry = make_entry(strom(start="2026-01-01", min_term_months=12, notice_period_weeks=6))
    assert await setup(hass, entry)
    rt = entry.runtime_data
    assert rt.contracts("s1")[0].notice_period_weeks == 6
    st = next(s for s in hass.states.async_all("sensor") if "kuendigung_bis" in s.attributes)
    assert st.attributes["kuendigung_bis"] == "2026-11-19" and st.attributes["tage_bis_kuendigung"] == 6
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_NOTICE}_s1")
    assert issue is not None and issue.translation_placeholders["bis"] == "2026-11-19"
    assert not events  # Event nur 28 Tage vorher und am letzten Tag
    freezer.move_to("2026-11-19 00:10:00+01:00")
    rt.coordinator.daily()
    assert events and events[-1]["tage"] == 0 and events[-1]["kuendigen_bis"] == "2026-11-19"
    # je Frist nur einmal: weder ein zweiter Lauf noch ein Neuladen feuert erneut
    n = len(events)
    rt.coordinator.daily()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(events) == n
    rt = entry.runtime_data
    # Frist vorbei → Hinweis weg
    freezer.move_to("2026-11-21 00:10:00+01:00")
    rt.coordinator.daily()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{ISSUE_NOTICE}_s1") is None


async def test_contract_terms_menu(hass: HomeAssistant) -> None:
    entry = make_entry(strom(start="2026-01-01"))
    assert await setup(hass, entry)
    flow = hass.config_entries.subentries
    from homeassistant.config_entries import SOURCE_RECONFIGURE  # noqa: PLC0415

    r = await flow.async_init((entry.entry_id, "zaehler"), context={"source": SOURCE_RECONFIGURE, "subentry_id": "s1"})
    assert "vertrag_aendern" in r["menu_options"]
    r = await flow.async_configure(r["flow_id"], {"next_step_id": "vertrag_aendern"})
    assert r["step_id"] == "vertrag_aendern"
    r = await flow.async_configure(r["flow_id"], {"tariff": "Öko", "min_term_months": 24, "notice_period_weeks": 4})
    assert r["reason"] == "contract_saved"
    c = entry.runtime_data.contracts("s1")[0]
    assert (c.tariff, c.min_term_months, c.notice_period_weeks) == ("Öko", 24, 4)
    periods = [p.period_id for p in entry.runtime_data.stored_periods("s1")]
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    c = entry.runtime_data.contracts("s1")[0]
    assert c.min_term_months == 24 and [p.period_id for p in entry.runtime_data.stored_periods("s1")] == periods


async def test_follow_up_with_terms(hass: HomeAssistant) -> None:
    entry = make_entry(strom(start="2026-01-01"))
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "s1")
    await _call(hass, "add_folgevertrag", {"zaehler": dev, "lieferant": "Neu", "beginn": date(2027, 1, 1), "abrechnungsregel": "contract_year",
                                           "mindestlaufzeit": 24, "kuendigungsfrist": 6})
    c = entry.runtime_data.contracts("s1")[-1]
    assert c.supplier == "Neu" and c.min_term_months == 24 and c.notice_period_weeks == 6


async def test_takeover_from_v03(hass: HomeAssistant) -> None:
    entry = make_entry(strom(start="2026-01-01"))
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "s1")
    hass.states.async_set("input_number.abschlag_strom", "95")
    hass.states.async_set("input_number.zahltag_strom", "15")
    hass.states.async_set("input_number.arbeitspreis_strom", "0.3412")
    hass.states.async_set("input_number.grundpreis_strom", "12.5")
    hass.states.async_set("input_number.startstand_strom", "1000")  # gleicher Stand wie vorhanden → ok
    hass.states.async_set("input_datetime.abrechnungsbeginn_strom", "2026-01-01")
    hass.states.async_set("input_number.brennwert", "unknown")
    resp = await _call(hass, "uebernahme_v03", {
        "zaehler": dev, "abschlag": "input_number.abschlag_strom", "zahltag": "input_number.zahltag_strom",
        "arbeitspreis": "input_number.arbeitspreis_strom", "grundpreis": "input_number.grundpreis_strom",
        "startstand": "input_number.startstand_strom", "abrechnungsbeginn": "input_datetime.abrechnungsbeginn_strom",
        "brennwert": "input_number.brennwert",
    })
    assert resp["ab"] == "2026-01-01"
    assert {"abschlag", "zahltag", "arbeitspreis", "grundpreis"} <= set(resp["uebernommen"])
    assert "brennwert" not in resp["uebernommen"]
    # der Startstand aus der Einrichtung (gleicher Zeitpunkt, gleicher Wert) wird nicht doppelt angelegt
    assert {"feld": "startstand", "grund": "schon vorhanden"} in resp["uebersprungen"]
    assert sum(1 for x in rt.readings("s1") if x.timestamp == datetime(2026, 1, 1, tzinfo=TZ)) == 1
    price = next(p for p in rt.data.prices if p.valid_from == date(2026, 1, 1))
    assert price.work_price == 0.3412 and price.base_price == 12.5 and price.calorific is None
    plan = rt.data.advance_plans[0]
    assert plan.steps[-1].amount == 95.0 and plan.steps[-1].pay_day == 15
    # abweichender Stand zum selben Zeitpunkt: übersprungen mit Grund, nichts doppelt
    hass.states.async_set("input_number.startstand_strom", "1005")
    resp2 = await _call(hass, "uebernahme_v03", {"zaehler": dev, "startstand": "input_number.startstand_strom", "ab": date(2026, 1, 1)})
    assert resp2["uebernommen"] == [] and "schon den Stand 1000.0" in resp2["uebersprungen"][-1]["grund"]
    # fehlender Grundpreis-Helfer: der Grundpreis aus dem Preisabschnitt bleibt (nie 0)
    hass.states.async_set("input_number.grundpreis_strom", "unavailable")
    await _call(hass, "uebernahme_v03", {"zaehler": dev, "arbeitspreis": "input_number.arbeitspreis_strom",
                                         "grundpreis": "input_number.grundpreis_strom", "ab": date(2026, 1, 1)})
    price = next(p for p in rt.data.prices if p.valid_from == date(2026, 1, 1))
    assert price.base_price == 12.5


async def test_weather_forecast_degree_days(hass: HomeAssistant) -> None:
    calls = []

    async def forecasts(call: ServiceCall):
        calls.append(call)
        return {"weather.home": {"forecast": [
            {"datetime": "2026-11-13T12:00:00+01:00", "temperature": 6.0, "templow": 2.0},
            {"datetime": "2026-11-14T12:00:00+01:00", "temperature": 18.0, "templow": 14.0},
            {"datetime": "2026-11-15T12:00:00+01:00", "temperature": 3.0},
        ]}}

    hass.services.async_register("weather", "get_forecasts", forecasts, supports_response=SupportsResponse.ONLY)
    hass.states.async_set("weather.home", "cloudy")
    entry = make_entry(strom(start="2026-01-01"), household={**HOUSEHOLD, "weather_entity": "weather.home"})
    assert await setup(hass, entry)
    coord = entry.runtime_data.coordinator
    await coord.async_update_weather()
    assert calls and calls[0].data["type"] == "daily"
    # Mittel 4 °C → 20 − 4 = 16 Kd; 16 °C über der Heizgrenze → 0; nur Höchstwert 3 °C → 17 Kd
    assert coord.forecast_dd == {date(2026, 11, 13): 16.0, date(2026, 11, 14): 0.0, date(2026, 11, 15): 17.0}


async def test_diagnostics_redacted(hass: HomeAssistant) -> None:
    from custom_components.tarif_cockpit.diagnostics import async_get_config_entry_diagnostics  # noqa: PLC0415

    hass.states.async_set("sensor.strom_zaehler", "1500", {"unit_of_measurement": "kWh"})
    sub = strom(start="2026-01-01")
    sub["data"]["meter"]["entity"] = "sensor.strom_zaehler"
    entry = make_entry(sub)
    assert await setup(hass, entry)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "sensor.strom_zaehler" not in text and "Stadtwerke Muster" not in text and "Testhaus" not in text
    m = diag["meters"]["s1"]
    assert m["meter"]["entity"] == "**REDACTED**" and m["contracts"][0]["supplier"] == "**REDACTED**"
    assert m["result"] is not None and "periods" in m and "counts" in diag
