"""1.2.4: Ablese-Karte – Ablesung und Holz für Benutzer ohne Admin-Rechte (mit Grenzen), Antwort mit Verbrauch seit der
letzten Ablesung, Holz im WebSocket."""

from __future__ import annotations

from datetime import datetime

import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized

from custom_components.tarif_cockpit.const import DOMAIN

from .conftest import generator_subentry, make_entry, meter_device_id, meter_subentry, setup
from .test_p5 import HEATED, gas_sub


async def _user(hass: HomeAssistant) -> Context:
    """Normaler Benutzer ohne Admin-Rechte (z. B. Familienmitglied)."""
    group = await hass.auth.async_get_group("system-users")
    user = MockUser(is_owner=False, groups=[group]).add_to_hass(hass)
    assert not user.is_admin
    return Context(user_id=user.id)


async def add(hass: HomeAssistant, ctx: Context | None = None, **data):
    return await hass.services.async_call(DOMAIN, "add_ablesung", data, blocking=True, return_response=True, context=ctx)


async def test_reading_by_user_with_consumption_since_and_limits(hass: HomeAssistant) -> None:
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    rt = entry.runtime_data
    dev = meter_device_id(hass, "m1")
    ctx = await _user(hass)
    r = await add(hass, ctx, zaehler=dev, stand=1234.5, zeitpunkt="2026-11-01T08:00:00")
    assert r["einheit"] == "m³" and r["vorher_stand"] == 1000.0 and r["verbrauch_seit"] == pytest.approx(234.5)
    assert not r["kleiner_als_vorher"] and r["vorher_zeitpunkt"].startswith("2026-03-15T00:00:00") and r["zeitpunkt"].startswith("2026-11-01T08:00:00")
    assert r["sensor_stand"] is None and r["abweichung_sensor"] is None and r["nachher_stand"] is None
    # Tippfehler: kleiner als vorher → Warnung; Korrektur ohne Zeitpunkt gilt zum Zeitpunkt der ersetzten Ablesung
    bad = await add(hass, ctx, zaehler=dev, stand=1200.0, zeitpunkt="2026-11-10T08:00:00")
    assert bad["kleiner_als_vorher"] and bad["verbrauch_seit"] == pytest.approx(-34.5) and bad["vorher_stand"] == 1234.5
    fix = await add(hass, ctx, zaehler=dev, stand=1300.0, ersetzt=bad["ablesung_id"])
    assert fix["zeitpunkt"].startswith("2026-11-10T08:00:00") and fix["verbrauch_seit"] == pytest.approx(65.5) and not fix["kleiner_als_vorher"]
    # nur die letzte, von Hand eingetragene Ablesung lässt sich ohne Admin-Rechte ersetzen
    first = next(x for x in rt.data.readings if x.value == 1000.0)
    with pytest.raises(ServiceValidationError) as err:
        await add(hass, ctx, zaehler=dev, stand=999.0, ersetzt=first.reading_id)
    assert err.value.translation_key == "user_replace_not_allowed"
    older = next(x for x in rt.data.readings if x.value == 1234.5)
    with pytest.raises(ServiceValidationError) as err:
        await add(hass, ctx, zaehler=dev, stand=1235.0, ersetzt=older.reading_id)
    assert err.value.translation_key == "user_replace_not_allowed"
    # höchstens 14 Tage zurück
    with pytest.raises(ServiceValidationError) as err:
        await add(hass, ctx, zaehler=dev, stand=1100.0, zeitpunkt="2026-10-20T08:00:00")
    assert err.value.translation_key == "user_reading_too_old"
    # Admins und Automationen dürfen das weiterhin
    admin = await add(hass, zaehler=dev, stand=1100.0, zeitpunkt="2026-10-20T08:00:00")
    assert admin["nachher_stand"] == 1234.5 and not admin["groesser_als_nachher"]
    # Ungültig markieren bleibt Administratoren vorbehalten
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, "ablesung_ungueltig", {"zaehler": dev, "ablesung_id": fix["ablesung_id"]},
                                       blocking=True, context=ctx)


async def test_read_only_user_cannot_write(hass: HomeAssistant, hass_read_only_user) -> None:
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    with pytest.raises(Unauthorized):
        await add(hass, Context(user_id=hass_read_only_user.id), zaehler=meter_device_id(hass, "m1"), stand=1100.0)


async def test_response_flags_later_reading_and_same_time(hass: HomeAssistant) -> None:
    entry = make_entry(meter_subentry("m1"))
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "m1")
    await add(hass, zaehler=dev, stand=1200.0, zeitpunkt="2026-11-10T08:00:00")
    r = await add(hass, zaehler=dev, stand=1300.0, zeitpunkt="2026-11-01T08:00:00")
    assert r["groesser_als_nachher"] and r["nachher_stand"] == 1200.0
    same = await add(hass, zaehler=dev, stand=1210.0, zeitpunkt="2026-11-10T08:00:00")
    assert same["gleicher_zeitpunkt"]


async def test_reading_with_sensor_reports_difference(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.strom", "21712.3", {"unit_of_measurement": "kWh", "state_class": "total_increasing"})
    entry = make_entry(meter_subentry("s1", "Strom", "strom", "kWh", entity="sensor.strom",
                                      reading={"timestamp": "2026-11-01T08:00:00+01:00", "value": 21500.5, "quality": "real"}))
    assert await setup(hass, entry)
    dev = meter_device_id(hass, "s1")
    r = await add(hass, zaehler=dev, stand=21698.4)
    assert r["sensor_stand"] == pytest.approx(21712.3) and r["abweichung_sensor"] == pytest.approx(-13.9)
    assert r["verbrauch_seit"] == pytest.approx(197.9)
    # Korrektur: kein Sensorstand von „jetzt“ neben einer älteren Ablesung
    fix = await add(hass, zaehler=dev, stand=21700.0, ersetzt=r["ablesung_id"])
    assert fix["sensor_stand"] is None and datetime.fromisoformat(fix["zeitpunkt"]) == datetime.fromisoformat(r["zeitpunkt"])


async def test_wood_by_user_limits_and_websocket_wood(hass: HomeAssistant, hass_ws_client, hass_read_only_access_token) -> None:
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    stove = generator_subentry("o1", "fireplace", "Kaminofen", nominal_kw=8.0, entities={"state": "binary_sensor.ofen"})
    klima = generator_subentry("k1", "air_air_hp", "Klima", on_household_power=True)
    entry = make_entry(gas_sub(), stove, klima, household=HEATED)
    assert await setup(hass, entry)
    ctx = await _user(hass)
    dev = meter_device_id(hass, "o1")
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json({"id": 1, "type": "tarif_cockpit/zaehler"})
    gens = {g["erzeuger_id"]: g for g in (await client.receive_json())["result"]["haushalte"][0]["waermeerzeuger"]}
    assert gens["o1"]["holz"] == {"datum": "2026-11-13", "heute": None, "kg_je_scheit": None} and gens["k1"]["holz"] is None
    r = await hass.services.async_call(DOMAIN, "holz_erfassen", {"erzeuger": dev, "kg": 9.0, "scheite": 10},
                                       blocking=True, return_response=True, context=ctx)
    assert r["kg_tag"] == 9.0
    await client.send_json({"id": 2, "type": "tarif_cockpit/zaehler"})
    gens = {g["erzeuger_id"]: g for g in (await client.receive_json())["result"]["haushalte"][0]["waermeerzeuger"]}
    assert gens["o1"]["holz"] == {"datum": "2026-11-13", "heute": 9.0, "kg_je_scheit": 0.9}
    # ohne Admin-Rechte: Tag ersetzen nur heute/gestern, Einträge höchstens 14 Tage zurück
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "holz_erfassen", {"erzeuger": dev, "datum": "2026-11-10", "ersetzen": True},
                                       blocking=True, context=ctx)
    assert err.value.translation_key == "user_wood_replace_old"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "holz_erfassen", {"erzeuger": dev, "datum": "2026-10-01", "kg": 5},
                                       blocking=True, context=ctx)
    assert err.value.translation_key == "user_reading_too_old"
    # Preise und Abschläge bleiben admin-only
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, "set_abschlag", {"zaehler": meter_device_id(hass, "g1"), "ab": "2026-12-01", "betrag": 100},
                                       blocking=True, context=ctx)
