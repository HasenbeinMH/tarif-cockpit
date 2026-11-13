"""Tarif-Cockpit: Tarife, Kosten und Abschlagsprognose für Strom, Gas und Wasser.

Die Integration hält die Daten (Haushalt, Zähler, Verträge, Perioden, Ablesungen, Tageswerte) und liefert die
Karten mit. In 0.5: Datenhaltung, Perioden und Tagesaggregation; Kosten und Prognose folgen in 0.6.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.storage import UnsupportedStorageVersionError
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .aggregation import async_setup_aggregation
from .const import (
    CONF_HOUSEHOLD, CONF_INITIAL_CONTRACT, CONF_INITIAL_READING, CONF_METER, CONF_STORE_CREATED, DOMAIN,
    ISSUE_STORE_INVALID, ISSUE_STORE_LOST, ISSUE_STORE_TOO_NEW, SUBENTRY_METER,
)
from .engine.model import Contract, Dataset, Household, Meter, ReadingSource, from_dict, new_id
from .engine.quality import Quality
from .frontend import async_register_frontend
from .runtime import TarifRuntime
from .services import async_setup_services
from .store import TarifStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TarifConfigEntry = ConfigEntry[TarifRuntime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Services einmal je Home Assistant registrieren."""
    async_setup_services(hass)
    return True


def household_from_entry(entry: ConfigEntry) -> Household:
    hh, errors = from_dict(Household, dict(entry.data.get(CONF_HOUSEHOLD, {})))
    if errors or hh is None:
        raise ConfigEntryError(f"Haushalt ungültig: {'; '.join(errors)}")
    return hh


def meters_from_entry(entry: ConfigEntry) -> dict[str, Meter]:
    meters: dict[str, Meter] = {}
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_METER:
            continue
        raw = dict(sub.data.get(CONF_METER, {}))
        raw["meter_id"] = sub.subentry_id
        raw.setdefault("name", sub.title)
        meter, errors = from_dict(Meter, raw)
        if meter is None:
            _LOGGER.error("Tarif-Cockpit: Zähler %s ungültig: %s", sub.title, "; ".join(errors))
            continue
        meters[meter.meter_id] = meter
    return meters


async def _async_load_dataset(hass: HomeAssistant, entry: ConfigEntry, store: TarifStore) -> Dataset:
    """Store laden und prüfen. Nie still leer starten, nie ungültige Daten überschreiben (Regel 3)."""
    try:
        raw = await store.async_load()
    except (NotImplementedError, UnsupportedStorageVersionError) as err:
        # Store einer neueren Version: nichts anfassen, melden
        store.blocked = True
        ir.async_create_issue(
            hass, DOMAIN, f"{ISSUE_STORE_TOO_NEW}_{entry.entry_id}", is_fixable=False,
            severity=ir.IssueSeverity.CRITICAL, translation_key=ISSUE_STORE_TOO_NEW, translation_placeholders={"key": store.key},
        )
        raise ConfigEntryError(f"Gespeicherte Daten stammen aus einer neueren Version: {err}") from err
    if raw is None:
        if entry.data.get(CONF_STORE_CREATED):
            ir.async_create_issue(
                hass, DOMAIN, f"{ISSUE_STORE_LOST}_{entry.entry_id}", is_fixable=False,
                severity=ir.IssueSeverity.CRITICAL, translation_key=ISSUE_STORE_LOST,
                translation_placeholders={"key": store.key},
            )
            store.blocked = True
            raise ConfigEntryError(
                "Die gespeicherten Daten des Tarif-Cockpits fehlen oder waren beschädigt. "
                "Bitte die Datei unter .storage wiederherstellen (siehe Reparaturen)."
            )
        return Dataset()
    dataset, errors = Dataset.from_dict(raw)
    if dataset is None:
        store.blocked = True
        ir.async_create_issue(
            hass, DOMAIN, f"{ISSUE_STORE_INVALID}_{entry.entry_id}", is_fixable=False,
            severity=ir.IssueSeverity.CRITICAL, translation_key=ISSUE_STORE_INVALID,
            translation_placeholders={"key": store.key, "errors": "; ".join(errors[:5]), "count": str(len(errors))},
        )
        raise ConfigEntryError(f"Gespeicherte Daten ungültig ({len(errors)} Fehler): {'; '.join(errors[:3])}")
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_STORE_LOST}_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_STORE_INVALID}_{entry.entry_id}")
    return dataset


def _import_initial(runtime: TarifRuntime) -> bool:
    """Startvertrag und Startstand aus der Einrichtung einmalig in den Store übernehmen."""
    changed = False
    for sub in runtime.entry.subentries.values():
        meter_id = sub.subentry_id
        if sub.subentry_type != SUBENTRY_METER or meter_id in runtime.data.imported_meters or meter_id not in runtime.meters:
            continue
        raw_contract: dict[str, Any] | None = sub.data.get(CONF_INITIAL_CONTRACT)
        if raw_contract:
            c_raw = dict(raw_contract, contract_id=new_id(), meter_id=meter_id)
            contract, errors = from_dict(Contract, c_raw)
            if contract is None:
                _LOGGER.error("Tarif-Cockpit: Startvertrag von %s ungültig: %s", sub.title, "; ".join(errors))
                continue
            runtime.data.contracts.append(contract)
        raw_reading: dict[str, Any] | None = sub.data.get(CONF_INITIAL_READING)
        if raw_reading:
            ts = dt_util.parse_datetime(raw_reading["timestamp"]) or datetime.fromisoformat(raw_reading["timestamp"])
            runtime.add_reading(
                meter_id, ts, float(raw_reading["value"]), Quality(raw_reading.get("quality", "real")), ReadingSource.INITIAL
            )
        runtime.data.imported_meters.append(meter_id)
        changed = True
    return changed


async def async_setup_entry(hass: HomeAssistant, entry: TarifConfigEntry) -> bool:
    await async_register_frontend(hass)
    store = TarifStore(hass, entry.entry_id)
    dataset = await _async_load_dataset(hass, entry, store)
    runtime = TarifRuntime(
        hass=hass,
        entry=entry,
        store=store,
        data=dataset,
        household=household_from_entry(entry),
        meters=meters_from_entry(entry),
        subentry_ids=frozenset(entry.subentries),
    )
    imported = _import_initial(runtime)
    if runtime.sync_periods() or imported or not entry.data.get(CONF_STORE_CREATED):
        await store.async_save_now(runtime.data)
        if not entry.data.get(CONF_STORE_CREATED):
            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_STORE_CREATED: True})
    entry.runtime_data = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_aggregation(hass, runtime)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TarifConfigEntry) -> None:
    """Neu laden, wenn Zähler hinzukommen oder wegfallen (Subentries)."""
    runtime: TarifRuntime | None = getattr(entry, "runtime_data", None)
    if runtime is None or frozenset(entry.subentries) != runtime.subentry_ids:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TarifConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime = entry.runtime_data
        for unsub in runtime.unsubs:
            unsub()
        runtime.unsubs.clear()
        # ausstehende verzögerte Speicherung sofort schreiben, danach schreibt diese Laufzeit nichts mehr
        await runtime.store.async_save_now(runtime.data)
        runtime.store.closed = True
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config-Entry-Migrationen (Regel 8)."""
    if entry.version > 1:
        return False
    if entry.version == 1 and entry.minor_version < 2:
        # 1.1 → 1.2: Toleranz für "Passt" gehört zum Haushalt
        household = dict(entry.data.get(CONF_HOUSEHOLD, {}))
        household.setdefault("tolerance_pct", 5.0)
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_HOUSEHOLD: household}, minor_version=2)
        _LOGGER.info("Tarif-Cockpit: Eintrag auf Version 1.2 migriert")
    return True
