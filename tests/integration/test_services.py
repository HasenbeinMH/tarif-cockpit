"""Services: Ablesung, Korrektur, ungültig, Folgevertrag, Neuberechnung; Tageswerte aus Ablesungen."""

from __future__ import annotations

from datetime import date

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.tarif_cockpit.const import DOMAIN
from custom_components.tarif_cockpit.engine.quality import Quality

from .conftest import make_entry, meter_device_id, meter_subentry, setup


async def _entry(hass: HomeAssistant):
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    return entry, meter_device_id(hass, "m1")


async def test_add_reading_and_daily_interpolation(hass: HomeAssistant) -> None:
    entry, dev = await _entry(hass)
    resp = await hass.services.async_call(
        DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 1100.0, "zeitpunkt": "2026-11-01T00:00:00"},
        blocking=True, return_response=True,
    )
    await hass.async_block_till_done()
    rt = entry.runtime_data
    assert resp["ablesung_id"] == rt.readings("m1")[-1].reading_id
    daily = rt.daily("m1")
    # 100 m³ über 231 Tage (15.03.–31.10.), linear verteilt
    d = daily[date(2026, 6, 1)]
    assert d.quality == Quality.INTERPOLATED
    assert d.consumption == pytest.approx(100.0 / 231, rel=1e-3)
    # nach der letzten Ablesung: fehlend, nicht 0
    assert daily[date(2026, 11, 5)].consumption is None
    last = next(s for s in hass.states.async_all("sensor") if "ablesung_id" in s.attributes)
    assert last.attributes["stand"] == 1100.0


async def test_correction_and_invalid_keep_history(hass: HomeAssistant) -> None:
    entry, dev = await _entry(hass)
    rt = entry.runtime_data
    r1 = await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 9999.0, "zeitpunkt": "2026-11-01T00:00:00"}, blocking=True, return_response=True)
    r2 = await hass.services.async_call(
        DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 1100.0, "zeitpunkt": "2026-11-01T00:00:00", "ersetzt": r1["ablesung_id"]},
        blocking=True, return_response=True,
    )
    old = next(r for r in rt.data.readings if r.reading_id == r1["ablesung_id"])
    assert old.value == 9999.0 and old.superseded_by == r2["ablesung_id"]
    await hass.services.async_call(DOMAIN, "ablesung_ungueltig", {"zaehler": dev, "ablesung_id": r2["ablesung_id"], "grund": "Tippfehler"}, blocking=True)
    bad = next(r for r in rt.data.readings if r.reading_id == r2["ablesung_id"])
    assert bad.quality == Quality.INVALID and bad.value == 1100.0 and "Tippfehler" in bad.note
    assert len(rt.data.readings) == 3  # nichts gelöscht
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "ablesung_ungueltig", {"zaehler": dev, "ablesung_id": "gibtsnicht"}, blocking=True)


async def test_reading_in_future_is_rejected(hass: HomeAssistant) -> None:
    _, dev = await _entry(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 1.0, "zeitpunkt": "2027-01-01T00:00:00"}, blocking=True)


async def test_follow_up_contract(hass: HomeAssistant, freezer) -> None:
    entry, dev = await _entry(hass)
    resp = await hass.services.async_call(
        DOMAIN, "add_folgevertrag",
        {"zaehler": dev, "lieferant": "Neu AG", "beginn": "2026-12-01", "abrechnungsregel": "fixed_day", "stichtag": "01.12", "wechselstand": 1200.0},
        blocking=True, return_response=True,
    )
    assert resp["alter_vertrag_endet"] == "2026-11-30"
    rt = entry.runtime_data
    chain = rt.contracts("m1")
    assert [c.supplier for c in chain] == ["Stadtwerke", "Neu AG"]
    period = next(s for s in hass.states.async_all("sensor") if s.attributes.get("periode_id"))
    assert period.state == "2026-11-30" and period.attributes["schlussperiode"] is True
    freezer.move_to("2026-12-02 12:00:00+01:00")
    rt.changed(save=False)
    await hass.async_block_till_done()
    period = next(s for s in hass.states.async_all("sensor") if s.attributes.get("periode_id"))
    assert period.state == "2027-11-30" and period.attributes["lieferant"] == "Neu AG"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_folgevertrag", {"zaehler": dev, "lieferant": "X", "beginn": "2026-01-01", "abrechnungsregel": "calendar_year"}, blocking=True)


async def test_recalculate_and_unknown_meter(hass: HomeAssistant) -> None:
    entry, dev = await _entry(hass)
    await hass.services.async_call(DOMAIN, "recalculate", {"zaehler": dev, "von": "2026-11-01"}, blocking=True)
    await hass.services.async_call(DOMAIN, "recalculate", {}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": "kein_geraet", "stand": 1.0}, blocking=True)


async def test_replacing_twice_is_rejected(hass: HomeAssistant) -> None:
    _, dev = await _entry(hass)
    a = await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 9999.0, "zeitpunkt": "2026-11-01T00:00:00"}, blocking=True, return_response=True)
    await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 1100.0, "zeitpunkt": "2026-11-01T00:00:00", "ersetzt": a["ablesung_id"]}, blocking=True, return_response=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_ablesung", {"zaehler": dev, "stand": 1200.0, "zeitpunkt": "2026-11-01T00:00:00", "ersetzt": a["ablesung_id"]}, blocking=True)


async def test_follow_up_into_ended_period_is_rejected(hass: HomeAssistant) -> None:
    contract = {"supplier": "Alt", "start_date": "2024-01-01", "billing_rule": "calendar_year"}
    entry = make_entry(meter_subentry("m1", contract=contract, reading={"timestamp": "2024-01-01T00:00:00+01:00", "value": 0.0, "quality": "real"}))
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    stored = entry.runtime_data.stored_periods("m1")
    assert [p.end_date for p in stored] == [date(2024, 12, 31), date(2025, 12, 31)]  # beendete Perioden eingefroren
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_folgevertrag", {"zaehler": dev, "lieferant": "Neu", "beginn": "2025-04-01", "abrechnungsregel": "calendar_year"}, blocking=True)
    assert [c.supplier for c in entry.runtime_data.contracts("m1")] == ["Alt"]


async def test_set_period_end_and_manual_periods(hass: HomeAssistant) -> None:
    entry = make_entry(meter_subentry("m1", contract={"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "calendar_year"}))
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    resp = await hass.services.async_call(DOMAIN, "set_periodenende", {"zaehler": dev, "ende": "2026-12-28"}, blocking=True, return_response=True)
    assert resp["ende"] == "2026-12-28"
    period = next(s for s in hass.states.async_all("sensor") if s.attributes.get("periode_id"))
    assert period.state == "2026-12-28"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "set_periodenende", {"zaehler": dev, "ende": "2027-02-15"}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_periode", {"zaehler": dev, "ende": "2027-06-30"}, blocking=True)


async def test_manual_rule_append_period(hass: HomeAssistant, freezer) -> None:
    contract = {"supplier": "SW", "start_date": "2026-01-01", "billing_rule": "manual", "manual_periods": [{"start": "2026-01-01", "end": "2026-12-31"}]}
    entry = make_entry(meter_subentry("m1", contract=contract))
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    await hass.services.async_call(DOMAIN, "add_periode", {"zaehler": dev, "ende": "2027-09-30"}, blocking=True)
    freezer.move_to("2027-02-01 12:00:00+01:00")
    entry.runtime_data.changed(save=False)
    await hass.async_block_till_done()
    period = next(s for s in hass.states.async_all("sensor") if s.attributes.get("periode_id"))
    assert period.state == "2027-09-30" and period.attributes["beginn"] == "2027-01-01"


async def test_recalculate_keeps_real_values_without_statistics(hass: HomeAssistant) -> None:
    from custom_components.tarif_cockpit.engine.model import DailyConsumption

    contract = {"supplier": "SW", "start_date": "2026-11-01", "billing_rule": "calendar_year"}
    entry = make_entry(meter_subentry("m1", "Strom", "strom", "kWh", entity="sensor.zaehler", contract=contract))
    assert await setup(hass, entry)
    rt = entry.runtime_data
    rt.put_daily([DailyConsumption("m1", date(2026, 11, 5), 12.5, quality=Quality.REAL)])
    dev = meter_device_id(hass, "m1")
    await hass.services.async_call(DOMAIN, "recalculate", {"zaehler": dev}, blocking=True)
    kept = rt.daily("m1")[date(2026, 11, 5)]
    assert kept.consumption == 12.5 and kept.quality == Quality.REAL
