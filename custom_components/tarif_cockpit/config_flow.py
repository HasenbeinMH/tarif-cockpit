"""Einrichtung: Haushalt (Config Entry) und Zähler mit erstem Vertrag, Preisen und Abschlägen (Subentry).

Minimaler Ablauf (0.5/0.6); der Fragen-Assistent mit Situation und Heizung folgt in 0.7.
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

from .const import (
    CONF_HOUSEHOLD, CONF_INITIAL_CONTRACT, CONF_INITIAL_PLAN, CONF_INITIAL_PRICE, CONF_INITIAL_READING, CONF_METER, DOMAIN,
    SUBENTRY_METER,
)
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
# mögliche Unterzähler je Medium (Entscheidung D: Wallbox; Wasser: Gartenwasser ohne Abwasser)
ROLES = {Medium.STROM: "wallbox", Medium.WASSER: "garden"}


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
    MINOR_VERSION = 3

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
            role = user_input.get("role", "main")
            if role != "main" and not self._mains(medium):
                errors["role"] = "no_main_meter"
            if not errors:
                self._data["name"] = user_input["name"]
                self._data["entity"] = entity
                self._data["history_entity"] = user_input.get("history_entity")
                self._data["role"] = role
                return await self.async_step_einheit()
        fields: dict[Any, Any] = {
            vol.Required("name", default=self._data.get("name") or medium.value.capitalize()): str,
            vol.Optional("entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
            vol.Optional("history_entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
        }
        if medium in ROLES:
            fields[vol.Required("role", default="main")] = _select(["main", ROLES[medium]], "role")
        return self.async_show_form(step_id="quelle", data_schema=vol.Schema(fields), errors=errors)

    def _mains(self, medium: Medium) -> dict[str, str]:
        """Hauptzähler gleichen Mediums (für Unterzähler): subentry_id → Titel."""
        return {
            sid: sub.title for sid, sub in self._get_entry().subentries.items()
            if sub.subentry_type == SUBENTRY_METER and sub.data.get(CONF_METER, {}).get("medium") == medium
            and sub.data.get(CONF_METER, {}).get("role", "main") == "main"
        }

    async def async_step_unterzaehler(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Wallbox oder Gartenzähler: gehört zu einem Hauptzähler, hat keinen eigenen Vertrag."""
        mains = self._mains(Medium(self._data["medium"]))
        if user_input is not None:
            self._data["parent_meter_id"] = user_input["parent"]
            return self.async_create_entry(title=self._data["name"], data={CONF_METER: self._meter_dict()}, unique_id=self._data.get("entity"))
        schema = vol.Schema({vol.Required("parent", default=next(iter(mains))): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value=k, label=v) for k, v in mains.items()]))})
        return self.async_show_form(step_id="unterzaehler", data_schema=schema)

    def _meter_dict(self) -> dict[str, Any]:
        return {
            "medium": self._data["medium"], "unit": self._data["unit"], "entity": self._data.get("entity"),
            "name": self._data["name"], "data_level": 2 if self._data.get("entity") else 1,
            "conversion": self._data.get("conversion", {}), "history_entity": self._data.get("history_entity"),
            "role": self._data.get("role", "main"), "parent_meter_id": self._data.get("parent_meter_id"),
            "annual_consumption": self._data.get("annual_consumption"),
        }

    async def async_step_einheit(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        medium = Medium(self._data["medium"])
        units = UNITS[medium]
        if user_input is not None:
            if medium == Medium.GAS and user_input["unit"] in ("m³", "m3") and (user_input.get("calorific") is None or user_input.get("z_factor") is None):
                return self.async_show_form(step_id="einheit", data_schema=self._einheit_schema(medium), errors={"calorific": "required_for_m3"})
            self._data["unit"] = user_input["unit"]
            conv = {k: float(user_input[k]) for k in ("calorific", "z_factor") if user_input.get(k) is not None}
            self._data["conversion"] = conv
            if user_input.get("annual_consumption") is not None:
                self._data["annual_consumption"] = float(user_input["annual_consumption"])
            if self._data.get("role", "main") != "main":
                return await self.async_step_unterzaehler()
            return await self.async_step_vertrag()
        return self.async_show_form(step_id="einheit", data_schema=self._einheit_schema(medium))

    def _einheit_schema(self, medium: Medium) -> vol.Schema:
        units = UNITS[medium]
        default_unit = units[0]
        if self._data.get("entity"):
            state = self.hass.states.get(self._data["entity"])
            unit = state.attributes.get("unit_of_measurement") if state else None
            if unit in units:
                default_unit = unit
        fields: dict[Any, Any] = {vol.Required("unit", default=default_unit): selector.SelectSelector(selector.SelectSelectorConfig(options=units))}
        if medium == Medium.GAS:
            # bei m³ Pflicht: ohne Brennwert und Zustandszahl lässt sich der Zähler nicht in kWh umrechnen
            fields[vol.Optional("calorific")] = _number(8, 13, "any", "kWh/m³")
            fields[vol.Optional("z_factor")] = _number(0.8, 1.1, "any")
        elif self._data.get("role", "main") == "main":
            fields[vol.Optional("annual_consumption")] = _number(0, 1e7, "any", default_unit)
        return vol.Schema(fields)

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
                return await self.async_step_preis()
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
                return self.async_create_entry(
                    title=self._data["name"],
                    data={CONF_METER: self._meter_dict(), CONF_INITIAL_CONTRACT: contract, CONF_INITIAL_READING: reading,
                          CONF_INITIAL_PRICE: self._data.get("price"), CONF_INITIAL_PLAN: self._data.get("plan")},
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

    async def async_step_preis(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Preise zu Vertragsbeginn (weitere Preisänderungen per Aktion set_preis)."""
        medium = Medium(self._data["medium"])
        if user_input is not None:
            price = {"work_price": float(user_input["work_price"]), "base_price": float(user_input["base_price"])}
            for key in ("metering_price", "wastewater_price", "fixed_yearly"):
                if user_input.get(key) is not None:
                    price[key] = float(user_input[key])
            self._data["price"] = price
            return await self.async_step_abschlag()
        per = "m³" if medium == Medium.WASSER else "kWh"
        cur = self.hass.config.currency
        fields: dict[Any, Any] = {
            vol.Required("work_price"): _number(0, 100, "any", f"{cur}/{per}"),
            vol.Required("base_price", default=0): _number(0, 10000, "any", f"{cur}/Monat"),
            vol.Optional("metering_price"): _number(0, 1000, "any", f"{cur}/Monat"),
        }
        if medium == Medium.WASSER:
            fields[vol.Optional("wastewater_price")] = _number(0, 100, "any", f"{cur}/m³")
            fields[vol.Optional("fixed_yearly")] = _number(0, 10000, "any", f"{cur}/Jahr")
        return self.async_show_form(step_id="preis", data_schema=vol.Schema(fields))

    async def async_step_abschlag(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Abschlagsplan: Betrag, Zahltag, Rhythmus, Anzahl je Periode. Ohne Betrag: keine Abschläge."""
        if user_input is not None:
            if user_input.get("amount"):
                plan = {"amount": float(user_input["amount"]), "pay_day": int(user_input["pay_day"]), "rhythm": int(user_input["rhythm"])}
                if user_input.get("max_per_period"):
                    plan["max_per_period"] = int(user_input["max_per_period"])
                self._data["plan"] = plan
            return await self.async_step_startstand()
        cur = self.hass.config.currency
        schema = vol.Schema({
            vol.Optional("amount"): _number(0, 100000, "any", cur),
            vol.Required("pay_day", default=1): _number(1, 31, 1),
            vol.Required("rhythm", default="1"): _select(["1", "2", "3"], "rhythm"),
            vol.Optional("max_per_period"): _number(1, 12, 1),
        })
        return self.async_show_form(step_id="abschlag", data_schema=schema)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Stammdaten ändern: Name, Ersatzquelle, Jahresverbrauch, Brennwert/Zustandszahl. Verträge und Preise per Aktion."""
        entry = self._get_entry()
        sub = self._get_reconfigure_subentry()
        meter = dict(sub.data.get(CONF_METER, {}))
        medium = Medium(meter.get("medium", "strom"))
        if user_input is not None:
            meter["name"] = user_input["name"]
            meter["history_entity"] = user_input.get("history_entity")
            if medium == Medium.GAS:
                conv = {k: float(user_input[k]) for k in ("calorific", "z_factor") if user_input.get(k) is not None}
                meter["conversion"] = conv
            else:
                meter["annual_consumption"] = float(user_input["annual_consumption"]) if user_input.get("annual_consumption") is not None else None
            return self.async_update_and_abort(entry, sub, title=user_input["name"], data={**sub.data, CONF_METER: meter})
        conv = meter.get("conversion") or {}
        fields: dict[Any, Any] = {
            vol.Required("name", default=meter.get("name") or sub.title): str,
            vol.Optional("history_entity", description={"suggested_value": meter.get("history_entity")}):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
        }
        if medium == Medium.GAS:
            fields[vol.Optional("calorific", description={"suggested_value": conv.get("calorific")})] = _number(8, 13, "any", "kWh/m³")
            fields[vol.Optional("z_factor", description={"suggested_value": conv.get("z_factor")})] = _number(0.8, 1.1, "any")
        else:
            fields[vol.Optional("annual_consumption", description={"suggested_value": meter.get("annual_consumption")})] = _number(0, 1e7, "any", meter.get("unit"))
        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema(fields))

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
