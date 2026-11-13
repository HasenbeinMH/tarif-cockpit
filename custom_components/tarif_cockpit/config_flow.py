"""Einrichtung: Haushalt (Config Entry) und Zähler mit erstem Vertrag (Subentry).

Minimaler Ablauf in 0.5; der Fragen-Assistent mit Situation, Heizung und Vorschau folgt in 0.7.
Startvertrag und Startstand stehen nur einmal im Subentry (``initial_*``); beim Setup übernimmt sie der Store,
danach gilt der Store (Entscheidung E).
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, SubentryFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import CONF_HOUSEHOLD, CONF_INITIAL_CONTRACT, CONF_INITIAL_READING, CONF_METER, DOMAIN, SUBENTRY_METER
from .engine import billing
from .engine.model import BillingRule, Contract, Medium, PeriodSpan, VatMode, to_dict

UNITS: dict[str, list[str]] = {
    Medium.STROM: ["kWh"],
    Medium.GAS: ["m³", "kWh"],
    Medium.WASSER: ["m³"],
    Medium.FERNWAERME: ["kWh", "MWh"],
}
DEVICE_CLASSES: dict[str, list[str]] = {
    Medium.STROM: ["energy"],
    Medium.GAS: ["gas", "energy"],
    Medium.WASSER: ["water"],
    Medium.FERNWAERME: ["energy"],
}
DEFAULT_VAT = {Medium.STROM: 19.0, Medium.GAS: 19.0, Medium.WASSER: 7.0, Medium.FERNWAERME: 19.0}


def _select(options: list[str], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(selector.SelectSelectorConfig(options=options, translation_key=key, mode=selector.SelectSelectorMode.DROPDOWN))


def _number(lo: float, hi: float, step: float | str, unit: str | None = None) -> selector.NumberSelector:
    cfg = selector.NumberSelectorConfig(min=lo, max=hi, step=step, mode=selector.NumberSelectorMode.BOX)
    if unit:
        cfg["unit_of_measurement"] = unit
    return selector.NumberSelector(cfg)


class TarifCockpitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Haushalt anlegen (höchstens einer)."""

    VERSION = 1
    MINOR_VERSION = 2

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_METER: MeterSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            household = {
                "name": user_input["name"],
                "outdoor_temp_entity": user_input.get("outdoor_temp_entity"),
                "weather_entity": user_input.get("weather_entity"),
                "heating_limit": float(user_input["heating_limit"]),
                "indoor_ref": float(user_input["indoor_ref"]),
                "tolerance_pct": float(user_input["tolerance_pct"]),
                "rooms": [{"entity": e} for e in user_input.get("rooms", [])],
            }
            return self.async_create_entry(title=user_input["name"], data={CONF_HOUSEHOLD: household})
        temp = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="temperature"))
        schema = vol.Schema({
            vol.Required("name", default="Zuhause"): str,
            vol.Optional("outdoor_temp_entity"): temp,
            vol.Optional("weather_entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
            vol.Optional("rooms"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)),
            vol.Required("heating_limit", default=15.0): _number(5, 25, 0.5, "°C"),
            vol.Required("indoor_ref", default=20.0): _number(15, 25, 0.5, "°C"),
            vol.Required("tolerance_pct", default=5.0): _number(0, 50, 1, "%"),
        })
        return self.async_show_form(step_id="user", data_schema=schema)


class MeterSubentryFlow(ConfigSubentryFlow):
    """Zähler mit erstem Vertrag und Startstand."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            self._data["medium"] = user_input["medium"]
            return await self.async_step_quelle()
        schema = vol.Schema({vol.Required("medium", default=Medium.STROM.value): _select([m.value for m in Medium], "medium")})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_quelle(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        medium = Medium(self._data["medium"])
        errors: dict[str, str] = {}
        if user_input is not None:
            entity = user_input.get("entity")
            if entity:
                for sub in self._get_entry().subentries.values():
                    if sub.subentry_type == SUBENTRY_METER and sub.data.get(CONF_METER, {}).get("entity") == entity:
                        errors["entity"] = "already_configured"
            if not errors:
                self._data["name"] = user_input["name"]
                self._data["entity"] = entity
                return await self.async_step_einheit()
        schema = vol.Schema({
            vol.Required("name", default=self._data.get("name") or medium.value.capitalize()): str,
            vol.Optional("entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
        })
        return self.async_show_form(step_id="quelle", data_schema=schema, errors=errors)

    async def async_step_einheit(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        medium = Medium(self._data["medium"])
        units = UNITS[medium]
        if user_input is not None:
            self._data["unit"] = user_input["unit"]
            conv = {k: float(user_input[k]) for k in ("calorific", "z_factor") if user_input.get(k) is not None}
            self._data["conversion"] = conv
            return await self.async_step_vertrag()
        default_unit = units[0]
        if self._data.get("entity"):
            state = self.hass.states.get(self._data["entity"])
            unit = state.attributes.get("unit_of_measurement") if state else None
            if unit in units:
                default_unit = unit
        fields: dict[Any, Any] = {vol.Required("unit", default=default_unit): selector.SelectSelector(selector.SelectSelectorConfig(options=units))}
        if medium == Medium.GAS:
            fields[vol.Optional("calorific")] = _number(8, 13, "any", "kWh/m³")
            fields[vol.Optional("z_factor")] = _number(0.8, 1.1, "any")
        return self.async_show_form(step_id="einheit", data_schema=vol.Schema(fields))

    async def async_step_vertrag(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        medium = Medium(self._data["medium"])
        errors: dict[str, str] = {}
        if user_input is not None:
            rule = BillingRule(user_input["billing_rule"])
            start = date.fromisoformat(user_input["start_date"])
            manual: list[PeriodSpan] = []
            if rule == BillingRule.MANUAL:
                if not user_input.get("first_period_end"):
                    errors["first_period_end"] = "required_for_manual"
                else:
                    manual = [PeriodSpan(start, date.fromisoformat(user_input["first_period_end"]))]
            contract = Contract(
                contract_id="neu", meter_id="neu", supplier=user_input["supplier"], start_date=start, billing_rule=rule,
                tariff=user_input.get("tariff"), fixed_day=user_input.get("fixed_day") if rule == BillingRule.FIXED_DAY else None,
                manual_periods=manual, vat_mode=VatMode(user_input["vat_mode"]), vat_rate=float(user_input["vat_rate"]),
            )
            if not errors:
                problems = billing.validate_contract(contract)
                if problems:
                    errors["fixed_day" if rule == BillingRule.FIXED_DAY else "base"] = "invalid_billing"
            if not errors:
                raw = to_dict(contract)
                del raw["contract_id"], raw["meter_id"]
                self._data["contract"] = raw
                return await self.async_step_startstand()
        schema = vol.Schema({
            vol.Required("supplier"): str,
            vol.Optional("tariff"): str,
            vol.Required("start_date"): selector.DateSelector(),
            vol.Required("billing_rule", default=BillingRule.CALENDAR_YEAR.value): _select([r.value for r in BillingRule], "billing_rule"),
            vol.Optional("fixed_day"): str,
            vol.Optional("first_period_end"): selector.DateSelector(),
            vol.Required("vat_mode", default=VatMode.GROSS.value): _select([v.value for v in VatMode], "vat_mode"),
            vol.Required("vat_rate", default=DEFAULT_VAT[medium]): _number(0, 30, 0.1, "%"),
        })
        return self.async_show_form(step_id="vertrag", data_schema=schema, errors=errors)

    async def async_step_startstand(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        contract = self._data["contract"]
        start = date.fromisoformat(contract["start_date"])
        needs_reading = not self._data.get("entity")
        errors: dict[str, str] = {}
        if user_input is not None:
            reading = None
            if user_input.get("value") is not None:
                ts = dt_util.parse_datetime(user_input["timestamp"]) if user_input.get("timestamp") else None
                if ts is None:
                    ts = datetime.combine(start, time(0))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt_util.get_default_time_zone())
                reading = {"timestamp": ts.isoformat(), "value": float(user_input["value"]), "quality": user_input["quality"]}
            elif needs_reading:
                errors["value"] = "required_without_entity"
            if not errors:
                meter = {
                    "medium": self._data["medium"], "unit": self._data["unit"], "entity": self._data.get("entity"),
                    "name": self._data["name"], "data_level": 2 if self._data.get("entity") else 1,
                    "conversion": self._data.get("conversion", {}),
                }
                return self.async_create_entry(
                    title=self._data["name"],
                    data={CONF_METER: meter, CONF_INITIAL_CONTRACT: contract, CONF_INITIAL_READING: reading},
                    unique_id=self._data.get("entity"),
                )
        schema = vol.Schema({
            vol.Optional("value"): _number(0, 1e9, "any", self._data["unit"]),
            vol.Optional("timestamp", default=datetime.combine(start, time(0)).isoformat(sep=" ")): selector.DateTimeSelector(),
            vol.Required("quality", default="real"): _select(["real", "estimated"], "quality"),
        })
        return self.async_show_form(
            step_id="startstand", data_schema=schema, errors=errors,
            description_placeholders={"preview": self._preview(contract)},
        )

    @staticmethod
    def _preview(raw_contract: dict[str, Any]) -> str:
        """Vorschau der ersten Perioden, z. B. '15.03.2026 – 31.12.2026 *' (* = Rumpfjahr, erklärt im Dialogtext)."""
        from .engine.model import from_dict  # noqa: PLC0415

        c, _ = from_dict(Contract, dict(raw_contract, contract_id="vorschau", meter_id="vorschau"))
        if c is None:
            return "–"
        try:
            specs = billing.generate_periods(c, billing.add_years(c.start_date, 1))[:2]
        except billing.BillingError:
            return "–"
        fmt = "%d.%m.%Y"
        return ", ".join(
            f"{s.start_date.strftime(fmt)} – {s.end_date.strftime(fmt)}{' *' if s.is_partial else ''}" for s in specs
        )
