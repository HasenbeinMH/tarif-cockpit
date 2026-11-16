"""1.2.2: Aktion „Holz erfassen“, gelernte Ofenleistung, Holz-Sensoren, Speicher 1.7."""

from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.tarif_cockpit.const import DOMAIN
from custom_components.tarif_cockpit.engine.generators import WOOD_KWH_PER_KG
from custom_components.tarif_cockpit.engine.model import GeneratorDaily
from custom_components.tarif_cockpit.engine.quality import Quality

from .conftest import generator_subentry, make_entry, meter_device_id, setup
from .test_init import KEY, stored
from .test_p5 import HEATED, gas_sub


async def _setup(hass: HomeAssistant):
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    stove = generator_subentry("o1", "fireplace", "Kaminofen", nominal_kw=8.0, efficiency=0.75, effective_share=0.6,
                               wood_price=260.0, wood_price_unit="rm", kg_per_rm=480.0, entities={"state": "binary_sensor.ofen"})
    hp = generator_subentry("w1", "air_air_hp", "Klima", nominal_kw=3.5, on_household_power=True)
    entry = make_entry(gas_sub(), stove, hp, household=HEATED)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    today = rt.today()
    for i, h in enumerate([5.0, 4.0, 6.0, 2.0]):
        d = today - timedelta(days=4 - i)
        rt.put_generator_daily([GeneratorDaily("o1", d, energy_input=h * 8 / 0.75, estimated_thermal_output=h * 8 * 0.6,
                                               measurement_quality=Quality.ASSUMPTION, hours=h)])
    rt.coordinator.async_refresh_now()
    await hass.async_block_till_done()
    return entry, rt, today


async def call(hass: HomeAssistant, **data):
    return await hass.services.async_call(DOMAIN, "holz_erfassen", data, blocking=True, return_response=True)


async def test_wood_service_learns_stove_output(hass: HomeAssistant) -> None:
    entry, rt, today = await _setup(hass)
    dev = meter_device_id(hass, "o1")
    ent = er.async_get(hass)
    power = ent.async_get_entity_id("sensor", DOMAIN, "o1_ofenleistung")
    wood = ent.async_get_entity_id("sensor", DOMAIN, "o1_holz_geschaetzt")
    assert power is not None and hass.states.get(power).state == "unknown"

    # Tag 1: Korb gewogen, zwei Einträge werden addiert; mit Scheiten wird das Gewicht je Scheit gemerkt
    r = await call(hass, erzeuger=dev, datum=(today - timedelta(days=4)).isoformat(), kg=10.0, scheite=8)
    assert r["kg_tag"] == 10.0 and r["leistung_kw"] is None
    r = await call(hass, erzeuger=dev, datum=(today - timedelta(days=4)).isoformat(), kg=5.0)
    assert r["kg_tag"] == 15.0
    # Tag 2: nur Scheite gezählt → 1,25 kg je Scheit aus dem ersten Eintrag
    r = await call(hass, erzeuger=dev, datum=(today - timedelta(days=3)).isoformat(), scheite=8)
    assert r["kg"] == pytest.approx(10.0) and r["kg_tag"] == pytest.approx(10.0)
    # Korrektur: Tag ersetzen
    r = await call(hass, erzeuger=dev, datum=(today - timedelta(days=3)).isoformat(), kg=12.0, ersetzen=True)
    assert r["kg_tag"] == 12.0
    r = await call(hass, erzeuger=dev, datum=(today - timedelta(days=2)).isoformat(), kg=18.0, notiz="Buche")
    await hass.async_block_till_done()
    assert r["tage_gelernt"] == 3 and r["kg_je_brennstunde"] == pytest.approx(3.0)

    st = hass.states.get(power)
    assert float(st.state) == pytest.approx(3.0 * WOOD_KWH_PER_KG * 0.75, abs=0.01)
    assert st.attributes["qualitaet"] == "vorlaeufig" and st.attributes["tage"] == 3 and st.attributes["tage_gewogen_gesamt"] == 3
    w = hass.states.get(wood)
    assert float(w.state) == pytest.approx(45.0 + 2.0 * 3.0, abs=0.1)  # gestern: 2 h × 3 kg/h
    assert w.attributes["gewogen_kg"] == 45.0 and w.attributes["tage_gewogen"] == 3
    # gespeichert
    assert len(rt.data.wood_log) == 4 and {x.note for x in rt.data.wood_log} == {None, "Buche"}
    # Entlastungs-Annahme für die Gas-Prognose nutzt die gelernte Wärme
    kw = rt.coordinator._heat_inputs(rt.meters["g1"])
    assert kw["stove_relief"] == pytest.approx(3.0 * WOOD_KWH_PER_KG * 0.75 * 0.6 / 0.9 * 1.11, abs=0.05)
    # Korrektur: Tag ohne Menge ersetzen → wieder nicht gewogen
    r = await call(hass, erzeuger=dev, datum=(today - timedelta(days=4)).isoformat(), ersetzen=True)
    assert r["entfernt"] == 2 and r["kg_tag"] is None and r["tage_gelernt"] == 0
    assert hass.states.get(power).state == "unknown"


async def test_wood_service_errors(hass: HomeAssistant) -> None:
    entry, rt, today = await _setup(hass)
    dev = meter_device_id(hass, "o1")
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, erzeuger=dev)
    assert err.value.translation_key == "wood_amount_missing"
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, erzeuger=dev, scheite=5)
    assert err.value.translation_key == "wood_kg_per_log_missing"
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, erzeuger=dev, kg=5, datum=(today + timedelta(days=1)).isoformat())
    assert err.value.translation_key == "wood_date_invalid"
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, erzeuger=dev, kg=5, datum=(today - timedelta(days=900)).isoformat())
    assert err.value.translation_key == "wood_date_invalid"
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, erzeuger=meter_device_id(hass, "w1"), kg=5)
    assert err.value.translation_key == "not_a_stove"
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, erzeuger=meter_device_id(hass, "g1"), kg=5)
    assert err.value.translation_key == "unknown_generator"
    assert rt.data.wood_log == []
    # ohne Datum: heute
    r = await call(hass, erzeuger=dev, scheite=6, kg_je_scheit=1.5)
    assert r["datum"] == today.isoformat() and r["kg"] == pytest.approx(9.0)
    assert r["zaehlt_ab"] == (today + timedelta(days=1)).isoformat()
    # 0 Scheite = kein Holz, auch ohne bekanntes Gewicht; spätere Angabe am selben Tag gilt als letzte
    r = await call(hass, erzeuger=dev, scheite=0, datum=(today - timedelta(days=1)).isoformat())
    assert r["kg"] == 0.0
    await call(hass, erzeuger=dev, kg=8.0, scheite=4)
    assert rt.last_kg_per_log("o1") == 2.0


async def test_store_migration_1_6_to_1_7_and_reload(hass: HomeAssistant, hass_storage) -> None:
    hass_storage[KEY] = stored("g1", minor=6)
    assert "wood_log" not in hass_storage[KEY]["data"]
    hass.states.async_set("sensor.gas", "100", {"unit_of_measurement": "kWh"})
    stove = generator_subentry("o1", "fireplace", "Kaminofen", nominal_kw=8.0, entities={"state": "binary_sensor.ofen"})
    entry = make_entry(gas_sub(), stove, household=HEATED, store_created=True)
    assert await setup(hass, entry)
    rt = entry.runtime_data
    assert rt.data.wood_log == []
    day = rt.today() - timedelta(days=2)
    await call(hass, erzeuger=meter_device_id(hass, "o1"), datum=day.isoformat(), kg=11.5, notiz="Eiche")
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[KEY]["minor_version"] == 7 and len(hass_storage[KEY]["data"]["wood_log"]) == 1
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    w = entry.runtime_data.data.wood_log[0]
    assert w.date == day and w.kg == 11.5 and w.note == "Eiche" and entry.runtime_data.wood("o1") == {day: 11.5}
