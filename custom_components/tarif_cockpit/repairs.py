"""Reparaturen mit Knopf (1.1): Vorschläge aus dem Vergleich Jahresabrechnung ↔ Integration übernehmen.

Der Hinweis ``rechnung_abweichung_<rechnung>`` zeigt Abweichung und Vorschläge (Brennwert, Zustandszahl, Faktor der
Ersatzquelle). Erst „Übernehmen“ schreibt sie als Kalibrierung; danach wird neu gerechnet und der Hinweis verschwindet,
weil die Rechnung dann passt. „Ignorieren“ bietet Home Assistant selbst an.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class InvoiceRepairFlow(RepairsFlow):
    def __init__(self, invoice_id: str, meter_id: str | None) -> None:
        self.invoice_id = invoice_id
        self.meter_id = meter_id

    def _runtime(self):
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED and any(i.invoice_id == self.invoice_id for i in entry.runtime_data.data.invoices):
                return entry.runtime_data
        return None

    def _check(self, rt):
        if rt is None or rt.coordinator is None:
            return None
        for checks in rt.coordinator.invoice_checks.values():
            for chk in checks:
                if chk.invoice_id == self.invoice_id:
                    return chk
        return None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        from .coordinator import invoice_placeholders  # noqa: PLC0415

        rt = self._runtime()
        chk = self._check(rt)
        if chk is None or not chk.proposals:
            return self.async_abort(reason="invoice_gone")
        if user_input is not None:
            rt.apply_invoice_proposals(self.invoice_id, chk.proposals)
            rt.store.schedule_save(rt.data)
            meter_id = self.meter_id if self.meter_id in rt.meters else None
            rt.changed(meter_id=meter_id)
            # HA löscht den Hinweis nach dem Abschluss; erst danach neu prüfen (sonst verschwände ein verbleibender Hinweis)
            from homeassistant.helpers.event import async_call_later  # noqa: PLC0415

            coord = rt.coordinator
            async_call_later(self.hass, 1, callback(lambda _now: coord.check_invoices()))
            return self.async_create_entry(data={})
        meter = rt.meters.get(self.meter_id) if self.meter_id else None
        placeholders = invoice_placeholders(meter, chk) if meter is not None else {}
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}), description_placeholders=placeholders)


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None) -> RepairsFlow:
    data = data or {}
    return InvoiceRepairFlow(str(data.get("invoice_id") or issue_id.rsplit("_", 1)[-1]), data.get("meter_id"))
