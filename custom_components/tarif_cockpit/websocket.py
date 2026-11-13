"""WebSocket-Befehl für die Karten (Integrations-Modus): welche Zähler gibt es, welche Sensoren gehören dazu.

Die Karten rechnen nichts (Regel 2): Sie bekommen hier nur die Zuordnung Kennung → entity_id und die Verträge und
lesen dann die Zustände dieser Sensoren aus ``hass.states``.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_meters)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/zaehler"})
@callback
def ws_meters(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], build_meters(hass))


def build_meters(hass: HomeAssistant) -> dict[str, Any]:
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    out: dict[str, Any] = {"haushalte": []}
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        rt = entry.runtime_data
        entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        by_meter: dict[str, dict[str, str]] = {}
        total = None
        for e in entities:
            if e.disabled_by is not None:  # deaktiviert: hat nie einen Zustand, die Karte würde darauf warten
                continue
            uid = e.unique_id or ""
            if uid == f"{entry.entry_id}_saldo_gesamt":
                total = e.entity_id
                continue
            for meter_id in rt.meters:
                if uid.startswith(f"{meter_id}_"):
                    by_meter.setdefault(meter_id, {})[uid[len(meter_id) + 1:]] = e.entity_id
        meters = []
        for meter_id, m in rt.meters.items():
            dev = next((d for d in dr.async_entries_for_config_entry(dev_reg, entry.entry_id) if (DOMAIN, meter_id) in d.identifiers), None)
            meters.append({
                "zaehler_id": meter_id, "device_id": dev.id if dev else None, "name": m.name or meter_id,
                "medium": m.medium.value, "unit": m.unit, "rolle": m.role, "hauptzaehler": m.parent_meter_id,
                "sensoren": by_meter.get(meter_id, {}),
                "vertraege": [{"lieferant": c.supplier, "tarif": c.tariff, "beginn": c.start_date.isoformat(),
                               "ende": c.end_date.isoformat() if c.end_date else None} for c in rt.contracts(meter_id)],
            })
        out["haushalte"].append({"entry_id": entry.entry_id, "name": rt.household.name, "saldo_gesamt": total, "zaehler": meters})
    return out
