"""Einrichtung (Arbeitspaket Abschnitt 7): Fragen-Assistent für den Haushalt, Zähler mit Vertrag, Preisen, Abschlägen.

- Haushalt (Config Entry): zuerst Fragen zur Situation (Heizung, Warmwasser, PV/Speicher/Wallbox, Eigentümer/Mieter,
  Abschlagsrhythmus), danach nur die Schritte, die dazu passen. Optionen ändern dieselben Angaben später.
- Zähler (Subentry): Medium (vorgeschlagen aus der Situation), Quelle, Einheit, Vertrag mit Periodenvorschau, Preise,
  Abschläge, Startstand, Zusammenfassung mit einer ersten Prognose.
- „Neu konfigurieren“ am Zähler: Stammdaten, Anbieter wechseln, Preis ändern, Abschlag ändern.
- Wärmeerzeuger (Subentry, 0.8): Typ (vorgeschlagen aus der Situation), Zuordnung (eigener Zähler oder Haushaltsstrom),
  Leistungsbereich laut Typschild, optionale Entitäten, beim Kaminofen Erkennung und Holz, Zusammenfassung der Annahmen.

Startvertrag, -preis, -abschlag und -stand stehen nur einmal im Subentry (``initial_*``); beim Setup übernimmt sie der
Store, danach gilt der Store (Entscheidung E). Änderungen danach gehen über die Laufzeitfunktionen wie die Aktionen.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry, ConfigEntryState, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, OptionsFlow, SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_GENERATOR, CONF_HOUSEHOLD, CONF_INITIAL_CONTRACT, CONF_INITIAL_PLAN, CONF_INITIAL_PRICE, CONF_INITIAL_READING,
    CONF_METER, DOMAIN, SUBENTRY_GENERATOR, SUBENTRY_METER,
)
from .engine import billing
from .engine.model import BillingRule, Contract, Medium, PeriodSpan, PriceSegment, ReadingSource, VatMode, from_dict, new_id, to_dict
from .engine.generators import (
    HS_HI, KIND_DEFAULTS, ON_POWER_KINDS, default as gen_default, gas_per_hour, stove_relief_per_hour, suggested_kinds,
)
from .engine.model import GeneratorKind, HeatGenerator, PowerBasis
from .engine.quality import Quality

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

HEATING = ["gas", "fernwaerme", "waermepumpe", "strom", "kaminofen", "oel_pellets", "keine"]
HOT_WATER = ["heizung", "strom", "waermepumpe", "solarthermie"]
EXTRAS = ["pv", "speicher", "wallbox"]
TENURE = ["eigentuemer", "mieter"]


def _select(options: list[str], key: str, multiple: bool = False) -> selector.SelectSelector:
    mode = selector.SelectSelectorMode.LIST if multiple else selector.SelectSelectorMode.DROPDOWN
    return selector.SelectSelector(selector.SelectSelectorConfig(options=options, translation_key=key, mode=mode, multiple=multiple))


def _number(lo: float, hi: float, step: float | str, unit: str | None = None) -> selector.NumberSelector:
    cfg = selector.NumberSelectorConfig(min=lo, max=hi, step=step, mode=selector.NumberSelectorMode.BOX)
    if unit:
        cfg["unit_of_measurement"] = unit
    return selector.NumberSelector(cfg)


def _heated(situation: dict[str, Any]) -> bool:
    return any(h != "keine" for h in situation.get("heating", []))


def suggested_media(situation: dict[str, Any]) -> list[str]:
    """Zähler, die aus der Situation folgen (Strom immer)."""
    out = [Medium.STROM.value]
    heating = situation.get("heating", [])
    if "gas" in heating:
        out.append(Medium.GAS.value)
    if "fernwaerme" in heating:
        out.append(Medium.FERNWAERME.value)
    out.append(Medium.WASSER.value)
    return out


# ---------------------------------------------------------------- Haushalt


def _situation_schema(defaults: dict[str, Any], suggest: bool = True) -> vol.Schema:
    """Fragen zum Haushalt. ``suggest=False`` (migrierter Haushalt ohne Antworten): nichts vorbelegen, damit
    beim Ändern z. B. nur der Toleranz keine erfundenen Antworten gespeichert werden."""
    def d(key: str, fallback: Any) -> Any:
        return defaults.get(key, fallback) if suggest or key in defaults else vol.UNDEFINED

    rhythm = d("rhythm", 1)
    return vol.Schema({
        vol.Required("heating", default=d("heating", ["gas"])): _select(HEATING, "heating", multiple=True),
        vol.Required("hot_water", default=d("hot_water", "heizung")): _select(HOT_WATER, "hot_water"),
        vol.Optional("extras", default=defaults.get("extras", [])): _select(EXTRAS, "extras", multiple=True),
        vol.Required("tenure", default=d("tenure", "eigentuemer")): _select(TENURE, "tenure"),
        vol.Required("rhythm", default=str(rhythm) if rhythm is not vol.UNDEFINED else vol.UNDEFINED): _select(["1", "2", "3"], "rhythm"),
    })


def _climate_schema(defaults: dict[str, Any]) -> vol.Schema:
    temp = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="temperature"))
    return vol.Schema({
        vol.Optional("outdoor_temp_entity", description={"suggested_value": defaults.get("outdoor_temp_entity")}): temp,
        vol.Optional("weather_entity", description={"suggested_value": defaults.get("weather_entity")}):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
        vol.Optional("rooms", description={"suggested_value": [r["entity"] for r in defaults.get("rooms", [])] or None}):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)),
        vol.Required("heating_limit", default=defaults.get("heating_limit", 15.0)): _number(5, 25, 0.5, "°C"),
        vol.Required("indoor_ref", default=defaults.get("indoor_ref", 20.0)): _number(15, 25, 0.5, "°C"),
    })


def _situation_from(user_input: dict[str, Any]) -> dict[str, Any]:
    return {"heating": list(user_input.get("heating", [])), "hot_water": user_input["hot_water"],
            "extras": list(user_input.get("extras", [])), "tenure": user_input["tenure"], "rhythm": int(user_input["rhythm"])}


def _climate_from(user_input: dict[str, Any]) -> dict[str, Any]:
    return {"outdoor_temp_entity": user_input.get("outdoor_temp_entity"), "weather_entity": user_input.get("weather_entity"),
            "rooms": [{"entity": e} for e in user_input.get("rooms", []) or []],
            "heating_limit": float(user_input["heating_limit"]), "indoor_ref": float(user_input["indoor_ref"])}


class TarifCockpitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Haushalt anlegen (höchstens einer): Fragen zuerst, dann nur passende Schritte."""

    VERSION = 1
    MINOR_VERSION = 4

    def __init__(self) -> None:
        self._hh: dict[str, Any] = {}

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_METER: MeterSubentryFlow, SUBENTRY_GENERATOR: GeneratorSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HouseholdOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._hh["name"] = user_input["name"]
            self._hh["situation"] = _situation_from(user_input)
            if _heated(self._hh["situation"]):
                return await self.async_step_klima()
            return await self.async_step_abschluss()
        schema = vol.Schema({vol.Required("name", default="Zuhause"): str}).extend(_situation_schema({}).schema)
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_klima(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Nur wenn geheizt wird: Außentemperatur, Wetter, Räume, Gradtag-Parameter."""
        if user_input is not None:
            self._hh.update(_climate_from(user_input))
            return await self.async_step_abschluss()
        return self.async_show_form(step_id="klima", data_schema=_climate_schema({}))

    async def async_step_abschluss(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            household = {"heating_limit": 15.0, "indoor_ref": 20.0, "rooms": [], **self._hh,
                         "tolerance_pct": float(user_input["tolerance_pct"])}
            return self.async_create_entry(title=household["name"], data={CONF_HOUSEHOLD: household})
        schema = vol.Schema({vol.Required("tolerance_pct", default=5.0): _number(0, 50, 1, "%")})
        kinds = suggested_kinds(self._hh["situation"])
        return self.async_show_form(step_id="abschluss", data_schema=schema, description_placeholders={
            "zaehler": ", ".join(_media_label(self.hass, m) for m in suggested_media(self._hh["situation"]))
            + (", " + _media_label(self.hass, "wallbox") if "wallbox" in self._hh["situation"].get("extras", []) else ""),
            "erzeuger": ", ".join(_kind_label(self.hass, k) for k in kinds) or "–",
        })


def _media_label(hass: Any, key: str) -> str:
    de = str(hass.config.language or "de").startswith("de")
    names = {"strom": ("Strom", "Electricity"), "gas": ("Gas", "Gas"), "wasser": ("Wasser", "Water"),
             "fernwaerme": ("Fernwärme", "District heating"), "wallbox": ("Wallbox", "Wallbox")}
    return names.get(key, (key, key))[0 if de else 1]


class HouseholdOptionsFlow(OptionsFlow):
    """Situation, Klima-Angaben und Toleranz des Haushalts ändern (lädt die Integration neu)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        hh = dict(self.config_entry.data.get(CONF_HOUSEHOLD, {}))
        if user_input is not None:
            hh["situation"] = _situation_from(user_input)
            hh.update(_climate_from(user_input))
            hh["tolerance_pct"] = float(user_input["tolerance_pct"])
            self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, CONF_HOUSEHOLD: hh})
            return self.async_create_entry(data={})
        situation = hh.get("situation") or {}
        schema = _situation_schema(situation, suggest=bool(situation)).extend(_climate_schema(hh).schema).extend(
            {vol.Required("tolerance_pct", default=hh.get("tolerance_pct", 5.0)): _number(0, 50, 1, "%")})
        return self.async_show_form(step_id="init", data_schema=schema)


# ---------------------------------------------------------------- Zähler


def _contract_schema(medium: Medium, defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema({
        vol.Required("supplier", default=d.get("supplier", vol.UNDEFINED)): str,
        vol.Optional("tariff"): str,
        vol.Required("start_date", default=d.get("start_date", vol.UNDEFINED)): selector.DateSelector(),
        vol.Required("billing_rule", default=d.get("billing_rule", BillingRule.CALENDAR_YEAR.value)): _select([r.value for r in BillingRule], "billing_rule"),
        vol.Optional("fixed_day"): str,
        vol.Optional("first_period_end"): selector.DateSelector(),
        vol.Required("vat_mode", default=VatMode.GROSS.value): _select([v.value for v in VatMode], "vat_mode"),
        vol.Required("vat_rate", default=DEFAULT_VAT[medium]): _number(0, 30, 0.1, "%"),
    })


def _contract_from(user_input: dict[str, Any]) -> tuple[Contract | None, dict[str, str]]:
    """Formular → Vertrag (mit Prüfung der Regel). Liefert (Vertrag, Fehler)."""
    errors: dict[str, str] = {}
    rule = BillingRule(user_input["billing_rule"])
    start = date.fromisoformat(user_input["start_date"])
    manual: list[PeriodSpan] = []
    if rule == BillingRule.MANUAL:
        if not user_input.get("first_period_end"):
            return None, {"first_period_end": "required_for_manual"}
        manual = [PeriodSpan(start, date.fromisoformat(user_input["first_period_end"]))]
    contract = Contract(
        contract_id="neu", meter_id="neu", supplier=user_input["supplier"], start_date=start, billing_rule=rule,
        tariff=user_input.get("tariff"), fixed_day=user_input.get("fixed_day") if rule == BillingRule.FIXED_DAY else None,
        manual_periods=manual, vat_mode=VatMode(user_input["vat_mode"]), vat_rate=float(user_input["vat_rate"]),
    )
    if billing.validate_contract(contract):
        errors["fixed_day" if rule == BillingRule.FIXED_DAY else "base"] = "invalid_billing"
        return None, errors
    return contract, errors


def _price_schema(hass: Any, medium: Medium, with_date: bool = False, current: PriceSegment | None = None) -> vol.Schema:
    """Preisformular; ``current`` belegt alle Felder mit dem laufenden Preisabschnitt vor (nichts geht still verloren)."""
    per = "m³" if medium == Medium.WASSER else "kWh"
    cur = hass.config.currency

    def opt(key: str) -> vol.Optional:
        value = getattr(current, key, None) if current is not None else None
        return vol.Optional(key, description={"suggested_value": value}) if value is not None else vol.Optional(key)

    fields: dict[Any, Any] = {}
    if with_date:
        fields[vol.Required("valid_from")] = selector.DateSelector()
    fields.update({
        vol.Required("work_price", default=current.work_price if current else vol.UNDEFINED): _number(0, 10000, "any", f"{cur}/{per}"),
        vol.Required("base_price", default=current.base_price if current else 0): _number(0, 10000, "any", f"{cur}/Monat"),
        opt("metering_price"): _number(0, 1000, "any", f"{cur}/Monat"),
    })
    if medium == Medium.GAS:
        fields[opt("calorific")] = _number(8, 13, "any", "kWh/m³")
        fields[opt("z_factor")] = _number(0.8, 1.1, "any")
    if medium == Medium.WASSER:
        fields[opt("wastewater_price")] = _number(0, 100, "any", f"{cur}/m³")
        fields[opt("fixed_yearly")] = _number(0, 10000, "any", f"{cur}/Jahr")
    if medium == Medium.FERNWAERME:
        fields[vol.Required("price_unit", default="kwh")] = _select(["kwh", "mwh"], "price_unit")
        fields[opt("demand_price")] = _number(0, 10000, "any", f"{cur}/kW·Jahr")
        fields[opt("demand_kw")] = _number(0, 1000, "any", "kW")
    return vol.Schema(fields)


PRICE_KEYS = ("metering_price", "calorific", "z_factor", "wastewater_price", "fixed_yearly", "demand_price", "demand_kw")


def _price_from(user_input: dict[str, Any]) -> dict[str, float]:
    """Formular → Preisabschnitt. Fernwärme je MWh wird auf kWh umgerechnet (gerechnet wird immer je kWh)."""
    work = float(user_input["work_price"])
    if user_input.get("price_unit") == "mwh":
        work = work / 1000.0
    price = {"work_price": work, "base_price": float(user_input["base_price"])}
    for key in PRICE_KEYS:
        if user_input.get(key) is not None:
            price[key] = float(user_input[key])
    return price


def _advance_schema(hass: Any, rhythm: int = 1, with_date: bool = False, amount_required: bool = False,
                    pay_day: int = 1, max_per_period: int | None = None, amount: float | None = None) -> vol.Schema:
    cur = hass.config.currency
    fields: dict[Any, Any] = {}
    if with_date:
        fields[vol.Required("valid_from")] = selector.DateSelector()
    amount_key = vol.Required if amount_required else vol.Optional
    fields[amount_key("amount", description={"suggested_value": amount}) if amount is not None else amount_key("amount")] = _number(0, 100000, "any", cur)
    fields[vol.Required("pay_day", default=pay_day)] = _number(1, 31, 1)
    fields[vol.Required("rhythm", default=str(rhythm))] = _select(["1", "2", "3"], "rhythm")
    fields[vol.Optional("max_per_period", description={"suggested_value": max_per_period}) if max_per_period else vol.Optional("max_per_period")] = _number(1, 12, 1)
    return vol.Schema(fields)


def current_price(rt: Any, meter_id: str) -> PriceSegment | None:
    """Laufender (sonst jüngster) Preisabschnitt des Vertrags, der heute gilt."""
    contract = billing.contract_on(rt.contracts(meter_id), rt.today()) or (rt.contracts(meter_id) or [None])[-1]
    if contract is None:
        return None
    segs = sorted((p for p in rt.data.prices if p.contract_id == contract.contract_id), key=lambda p: p.valid_from)
    today = rt.today()
    running = [p for p in segs if p.valid_from <= today and (p.valid_to is None or p.valid_to >= today)]
    return (running or segs or [None])[-1]


def current_advance(rt: Any, meter_id: str) -> dict[str, Any]:
    """Betrag, Zahltag, Rhythmus und Höchstzahl, die heute gelten (Stufen mit eigenem Zahltag/Rhythmus beachtet)."""
    contract = billing.contract_on(rt.contracts(meter_id), rt.today()) or (rt.contracts(meter_id) or [None])[-1]
    plan = next((p for p in rt.data.advance_plans if contract and p.contract_id == contract.contract_id), None)
    if plan is None:
        return {}
    out: dict[str, Any] = {"pay_day": plan.pay_day, "rhythm": plan.rhythm, "max_per_period": plan.max_per_period}
    for step in sorted(plan.steps, key=lambda s: s.from_date):
        if step.from_date > rt.today() and "amount" in out:
            break
        out["amount"] = step.amount
        if step.pay_day is not None:
            out["pay_day"] = step.pay_day
        if step.rhythm is not None:
            out["rhythm"] = step.rhythm
    return out


def _rescale_pulses(rt: Any, meter_id: str, f: float) -> None:
    """Impulskonstante geändert: gemerkte Sensorstände umrechnen und die Tageswerte beim Neuladen neu holen."""
    rt.data.readings = [replace(r, sensor_value=r.sensor_value * f) if r.meter_id == meter_id and r.sensor_value is not None else r
                        for r in rt.data.readings]
    rt.data.sensor_resets = [replace(x, prev_raw=x.prev_raw * f) if x.meter_id == meter_id else x for x in rt.data.sensor_resets]
    if meter_id in rt.data.sensor_last_raw:
        rt.data.sensor_last_raw[meter_id] *= f
    if meter_id in rt.data.reaggregated_meters:
        rt.data.reaggregated_meters.remove(meter_id)  # beim Start einmal alle Tageswerte neu (overwrite)
    rt.store.schedule_save(rt.data)


class MeterSubentryFlow(ConfigSubentryFlow):
    """Zähler mit erstem Vertrag, Preisen, Abschlägen und Startstand; Menü zum Ändern."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._switch: dict[str, Any] = {}

    def _situation(self) -> dict[str, Any]:
        return dict(self._get_entry().data.get(CONF_HOUSEHOLD, {}).get("situation", {}))

    def _existing_media(self) -> list[str]:
        return [s.data.get(CONF_METER, {}).get("medium") for s in self._get_entry().subentries.values()
                if s.subentry_type == SUBENTRY_METER and s.data.get(CONF_METER, {}).get("role", "main") == "main"]

    def _runtime(self) -> Any:
        """Laufzeit nur, solange der Eintrag geladen ist (sonst None)."""
        entry = self._get_entry()
        return getattr(entry, "runtime_data", None) if entry.state is ConfigEntryState.LOADED else None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            self._data["medium"] = user_input["medium"]
            return await self.async_step_quelle()
        sit = self._situation()
        missing = [m for m in suggested_media(sit) if m not in self._existing_media()]
        default = missing[0] if missing else Medium.STROM.value
        schema = vol.Schema({vol.Required("medium", default=default): _select([m.value for m in Medium], "medium")})
        return self.async_show_form(step_id="user", data_schema=schema, description_placeholders={
            "fehlen": ", ".join(_media_label(self.hass, m) for m in missing) or "–"})

    async def async_step_quelle(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        medium = Medium(self._data["medium"])
        errors: dict[str, str] = {}
        roles = self._roles(medium)
        if user_input is not None:
            entity = user_input.get("entity")
            pulse = user_input.get("pulse_entity")
            if entity and pulse:
                errors["base"] = "entity_or_pulses"
            entity = entity or pulse
            self._data["pulses"] = bool(pulse) and not errors
            if entity:
                for sub in self._get_entry().subentries.values():
                    if sub.subentry_type == SUBENTRY_METER and sub.data.get(CONF_METER, {}).get("entity") == entity:
                        errors["entity"] = "already_configured"
            role = user_input.get("role", "main")
            if role != "main" and not self._mains(medium):
                errors["role"] = "no_main_meter"
            if not errors:
                self._data.update(name=user_input["name"], entity=entity, history_entity=user_input.get("history_entity"), role=role)
                return await self.async_step_einheit()
        fields: dict[Any, Any] = {
            vol.Required("name", default=self._data.get("name") or _media_label(self.hass, medium.value)): str,
            vol.Optional("entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
            vol.Optional("history_entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
            # Impulszähler: ohne Geräteklasse (z. B. ESPHome pulse_counter, Zähler-Helfer)
            vol.Optional("pulse_entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "counter", "input_number"])),
        }
        if len(roles) > 1:
            fields[vol.Required("role", default="main")] = _select(roles, "role")
        return self.async_show_form(step_id="quelle", data_schema=vol.Schema(fields), errors=errors)

    def _roles(self, medium: Medium) -> list[str]:
        """Unterzähler nur, wenn passend: Wallbox nur mit Wallbox in der Situation (oder ohne Situationsangaben)."""
        if medium not in ROLES:
            return ["main"]
        role = ROLES[medium]
        sit = self._situation()
        if role == "wallbox" and sit and "wallbox" not in sit.get("extras", []):
            return ["main"]
        return ["main", role]

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
            "pulse_constant": self._data.get("pulse_constant"), "pulse_mode": self._data.get("pulse_mode", "per_unit"),
        }

    async def async_step_einheit(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        medium = Medium(self._data["medium"])
        if user_input is not None:
            if medium == Medium.GAS and user_input["unit"] in ("m³", "m3") and (user_input.get("calorific") is None or user_input.get("z_factor") is None):
                return self.async_show_form(step_id="einheit", data_schema=self._einheit_schema(medium), errors={"calorific": "required_for_m3"})
            self._data["unit"] = user_input["unit"]
            self._data["conversion"] = {k: float(user_input[k]) for k in ("calorific", "z_factor") if user_input.get(k) is not None}
            if self._data.get("pulses"):
                self._data["pulse_constant"] = float(user_input["pulse_constant"])
                self._data["pulse_mode"] = user_input["pulse_mode"]
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
        if self._data.get("pulses"):
            fields[vol.Required("pulse_constant", default=self._data.get("pulse_constant", 100.0))] = _number(0.000001, 1e6, "any")
            fields[vol.Required("pulse_mode", default=self._data.get("pulse_mode", "per_unit"))] = _select(["per_unit", "per_pulse"], "pulse_mode")
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
            contract, errors = _contract_from(user_input)
            if contract is not None:
                raw = to_dict(contract)
                del raw["contract_id"], raw["meter_id"]
                self._data["contract"] = raw
                return await self.async_step_preis()
        return self.async_show_form(step_id="vertrag", data_schema=_contract_schema(medium), errors=errors)

    async def async_step_preis(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Preise zu Vertragsbeginn (weitere Preisänderungen über „Neu konfigurieren“ oder die Aktion set_preis)."""
        medium = Medium(self._data["medium"])
        if user_input is not None:
            self._data["price"] = _price_from(user_input)
            return await self.async_step_abschlag()
        schema = _price_schema(self.hass, medium)
        if medium == Medium.GAS:  # Brennwert steht bei Gas schon im Zähler
            schema = vol.Schema({k: v for k, v in schema.schema.items() if str(k) not in ("calorific", "z_factor")})
        return self.async_show_form(step_id="preis", data_schema=schema)

    async def async_step_abschlag(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Abschlagsplan: Betrag, Zahltag, Rhythmus, Anzahl je Periode. Ohne Betrag: keine Abschläge."""
        if user_input is not None:
            if user_input.get("amount"):
                plan = {"amount": float(user_input["amount"]), "pay_day": int(user_input["pay_day"]), "rhythm": int(user_input["rhythm"])}
                if user_input.get("max_per_period"):
                    plan["max_per_period"] = int(user_input["max_per_period"])
                self._data["plan"] = plan
            return await self.async_step_startstand()
        return self.async_show_form(step_id="abschlag", data_schema=_advance_schema(self.hass, int(self._situation().get("rhythm", 1))))

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
                self._data["reading"] = reading
                return await self.async_step_zusammenfassung()
        schema = vol.Schema({
            vol.Optional("value"): _number(0, 1e9, "any", self._data["unit"]),
            vol.Optional("timestamp", default=datetime.combine(start, time(0)).isoformat(sep=" ")): selector.DateTimeSelector(),
            vol.Required("quality", default="real"): _select(["real", "estimated"], "quality"),
        })
        return self.async_show_form(step_id="startstand", data_schema=schema, errors=errors,
                                    description_placeholders={"preview": self._preview(contract)})

    async def async_step_zusammenfassung(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Zusammenfassung mit Perioden, Preisen, Abschlägen und einer ersten Prognose (ohne Speichern gerechnet)."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._data["name"],
                data={CONF_METER: self._meter_dict(), CONF_INITIAL_CONTRACT: self._data["contract"],
                      CONF_INITIAL_READING: self._data.get("reading"), CONF_INITIAL_PRICE: self._data.get("price"),
                      CONF_INITIAL_PLAN: self._data.get("plan")},
                unique_id=self._data.get("entity"),
            )
        from .probe import async_probe_summary  # noqa: PLC0415

        summary = await async_probe_summary(self.hass, self._runtime(), self._data)
        return self.async_show_form(step_id="zusammenfassung", data_schema=vol.Schema({}), description_placeholders=summary)

    # ------------------------------------------------------------ Ändern

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        meter = sub.data.get(CONF_METER, {})
        options = ["stammdaten"]
        if meter.get("role", "main") == "main" and self._runtime() is not None:
            options += ["anbieterwechsel", "preis_aendern", "abschlag_aendern"]
        return self.async_show_menu(step_id="reconfigure", menu_options=options)

    async def async_step_stammdaten(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Name, Ersatzquelle, Jahresverbrauch, Brennwert/Zustandszahl."""
        entry = self._get_entry()
        sub = self._get_reconfigure_subentry()
        meter = dict(sub.data.get(CONF_METER, {}))
        medium = Medium(meter.get("medium", "strom"))
        if user_input is not None and medium == Medium.GAS and meter.get("unit") == "m³" and user_input.get("calorific") is None:
            errors = {"calorific": "required_for_m3"}
            user_input = None
        else:
            errors = {}
        if user_input is not None:
            meter["name"] = user_input["name"]
            meter["history_entity"] = user_input.get("history_entity")
            if meter.get("pulse_constant"):
                from .engine.pulses import unit_per_pulse  # noqa: PLC0415

                old_k = unit_per_pulse(meter["pulse_constant"], meter.get("pulse_mode", "per_unit"))
                meter["pulse_constant"] = float(user_input["pulse_constant"])
                meter["pulse_mode"] = user_input["pulse_mode"]
                new_k = unit_per_pulse(meter["pulse_constant"], meter["pulse_mode"])
                rt = getattr(entry, "runtime_data", None)
                if rt is not None and old_k and new_k and abs(new_k - old_k) > 1e-15:
                    _rescale_pulses(rt, sub.subentry_id, new_k / old_k)
            if medium == Medium.GAS:
                meter["conversion"] = {k: float(user_input[k]) for k in ("calorific", "z_factor") if user_input.get(k) is not None}
            else:
                meter["annual_consumption"] = float(user_input["annual_consumption"]) if user_input.get("annual_consumption") is not None else None
            return self.async_update_and_abort(entry, sub, title=user_input["name"], data={**sub.data, CONF_METER: meter})
        conv = meter.get("conversion") or {}
        fields: dict[Any, Any] = {
            vol.Required("name", default=meter.get("name") or sub.title): str,
            vol.Optional("history_entity", description={"suggested_value": meter.get("history_entity")}):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=DEVICE_CLASSES[medium])),
        }
        if meter.get("pulse_constant"):
            fields[vol.Required("pulse_constant", default=meter["pulse_constant"])] = _number(0.000001, 1e6, "any")
            fields[vol.Required("pulse_mode", default=meter.get("pulse_mode", "per_unit"))] = _select(["per_unit", "per_pulse"], "pulse_mode")
        if medium == Medium.GAS:
            fields[vol.Optional("calorific", description={"suggested_value": conv.get("calorific")})] = _number(8, 13, "any", "kWh/m³")
            fields[vol.Optional("z_factor", description={"suggested_value": conv.get("z_factor")})] = _number(0.8, 1.1, "any")
        else:
            fields[vol.Optional("annual_consumption", description={"suggested_value": meter.get("annual_consumption")})] = _number(0, 1e7, "any", meter.get("unit"))
        return self.async_show_form(step_id="stammdaten", data_schema=vol.Schema(fields), errors=errors)

    def _meter_id_and_medium(self) -> tuple[str, Medium]:
        sub = self._get_reconfigure_subentry()
        return sub.subentry_id, Medium(sub.data.get(CONF_METER, {}).get("medium", "strom"))

    async def async_step_preis_aendern(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        meter_id, medium = self._meter_id_and_medium()
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        rt = self._runtime()
        if rt is None:
            return self.async_abort(reason="not_loaded")
        if user_input is not None:
            try:
                rt.set_price(meter_id, date.fromisoformat(user_input["valid_from"]), **_price_from(user_input))
            except billing.BillingError as err:
                errors["base"] = "billing_error"
                placeholders["error"] = str(err)
            else:
                rt.changed(meter_id=meter_id, flags={"costs"})
                return self.async_abort(reason="price_saved")
        return self.async_show_form(step_id="preis_aendern", data_schema=_price_schema(self.hass, medium, with_date=True, current=current_price(rt, meter_id)),
                                    errors=errors, description_placeholders=placeholders)

    async def async_step_abschlag_aendern(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        meter_id, _ = self._meter_id_and_medium()
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        rt = self._runtime()
        if rt is None:
            return self.async_abort(reason="not_loaded")
        if user_input is not None:
            try:
                rt.set_advance(meter_id, date.fromisoformat(user_input["valid_from"]), float(user_input["amount"]),
                               int(user_input["pay_day"]), int(user_input["rhythm"]),
                               int(user_input["max_per_period"]) if user_input.get("max_per_period") else None)
            except billing.BillingError as err:
                errors["base"] = "billing_error"
                placeholders["error"] = str(err)
            else:
                rt.changed(meter_id=meter_id, flags={"payments"})
                return self.async_abort(reason="advance_saved")
        now = current_advance(rt, meter_id)  # Zahltag und Rhythmus bleiben, wenn man nur den Betrag ändert
        schema = _advance_schema(self.hass, int(now.get("rhythm") or self._situation().get("rhythm", 1)), with_date=True,
                                 amount_required=True, pay_day=int(now.get("pay_day") or 1),
                                 max_per_period=now.get("max_per_period"), amount=now.get("amount"))
        return self.async_show_form(step_id="abschlag_aendern", data_schema=schema, errors=errors, description_placeholders=placeholders)

    async def async_step_anbieterwechsel(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Anbieterwechsel 1/3: Wechseldatum und Wechselablesung."""
        meter_id, medium = self._meter_id_and_medium()
        rt = self._runtime()
        if rt is None:
            return self.async_abort(reason="not_loaded")
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            day = date.fromisoformat(user_input["switch_date"])
            rt.sync_periods()
            try:
                billing.check_not_in_ended_period(day, rt.stored_periods(meter_id))
                current = billing.contract_on(rt.contracts(meter_id), day)
                if current is None or current.start_date >= day:
                    raise billing.BillingError(f"Am {day} läuft kein Vertrag, der vorher begonnen hat; ein Wechsel ist erst danach möglich.")
            except billing.BillingError as err:
                errors["switch_date"] = "switch_invalid"
                placeholders["error"] = str(err)
            if not errors and user_input.get("value") is not None and day > rt.today():
                errors["value"] = "switch_reading_future"
            if not errors:
                self._switch = {"date": user_input["switch_date"], "value": user_input.get("value"), "quality": user_input["quality"]}
                return await self.async_step_wechsel_vertrag()
        schema = vol.Schema({
            vol.Required("switch_date"): selector.DateSelector(),
            vol.Optional("value"): _number(0, 1e9, "any"),
            vol.Required("quality", default="real"): _select(["real", "estimated"], "quality"),
        })
        return self.async_show_form(step_id="anbieterwechsel", data_schema=schema, errors=errors, description_placeholders=placeholders)

    async def async_step_wechsel_vertrag(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Anbieterwechsel 2/3: neuer Vertrag ab dem Wechseldatum."""
        _, medium = self._meter_id_and_medium()
        errors: dict[str, str] = {}
        if user_input is not None:
            contract, errors = _contract_from({**user_input, "start_date": self._switch["date"]})
            if contract is not None:
                self._switch["contract"] = contract
                return await self.async_step_wechsel_preis()
        schema = vol.Schema({k: v for k, v in _contract_schema(medium).schema.items() if str(k) != "start_date"})
        return self.async_show_form(step_id="wechsel_vertrag", data_schema=schema, errors=errors,
                                    description_placeholders={"datum": self._switch["date"]})

    async def async_step_wechsel_preis(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Anbieterwechsel 3/3: Preise und Abschlag des neuen Vertrags; dann wird alles übernommen."""
        meter_id, medium = self._meter_id_and_medium()
        errors: dict[str, str] = {}
        placeholders = {"error": "", "preview": ""}
        new: Contract = self._switch["contract"]
        placeholders["preview"] = self._preview({k: v for k, v in to_dict(new).items() if k not in ("contract_id", "meter_id")})
        rt = self._runtime()
        if rt is None:
            return self.async_abort(reason="not_loaded")
        if user_input is not None:
            start = new.start_date
            created = replace(new, contract_id=new_id(), meter_id=meter_id)
            try:
                rt.add_follow_up(created)
                rt.set_price(meter_id, start, **_price_from(user_input))
                if user_input.get("amount"):
                    rt.set_advance(meter_id, start, float(user_input["amount"]), int(user_input["pay_day"]), int(user_input["rhythm"]),
                                   int(user_input["max_per_period"]) if user_input.get("max_per_period") else None)
            except billing.BillingError as err:
                errors["base"] = "billing_error"
                placeholders["error"] = str(err)
            else:
                if self._switch.get("value") is not None:
                    ts = datetime.combine(start, time(0), tzinfo=rt.tz)
                    rt.add_reading(meter_id, ts, float(self._switch["value"]), Quality(self._switch["quality"]), ReadingSource.SWITCH, "Wechselablesung")
                await rt.after_readings_changed(meter_id)
                return self.async_abort(reason="switch_saved")
        schema = _price_schema(self.hass, medium).extend(_advance_schema(self.hass, int(self._situation().get("rhythm", 1))).schema)
        return self.async_show_form(step_id="wechsel_preis", data_schema=schema, errors=errors, description_placeholders=placeholders)

    @staticmethod
    def _preview(raw_contract: dict[str, Any]) -> str:
        """Vorschau der ersten Perioden, z. B. '15.03.2026 – 31.12.2026¹' (¹ = Rumpfjahr, erklärt im Dialogtext)."""
        c, _ = from_dict(Contract, dict(raw_contract, contract_id="vorschau", meter_id="vorschau"))
        if c is None:
            return "–"
        try:
            specs = billing.generate_periods(c, billing.add_years(c.start_date, 1))[:2]
        except billing.BillingError:
            return "–"
        fmt = "%d.%m.%Y"
        return ", ".join(f"{s.start_date.strftime(fmt)} – {s.end_date.strftime(fmt)}{'¹' if s.is_partial else ''}" for s in specs)



# ---------------------------------------------------------------- Wärmeerzeuger (0.8)

KINDS = [k.value for k in GeneratorKind]
KIND_MEDIA = {
    GeneratorKind.GAS_BOILER: (Medium.GAS,),
    GeneratorKind.DISTRICT_HEATING: (Medium.FERNWAERME,),
    GeneratorKind.WATER_HP: (Medium.STROM,),
    GeneratorKind.AIR_AIR_HP: (Medium.STROM,),
    GeneratorKind.ELECTRIC: (Medium.STROM,),
    GeneratorKind.FIREPLACE: (),
}
DHW_KINDS = (GeneratorKind.GAS_BOILER, GeneratorKind.WATER_HP, GeneratorKind.DISTRICT_HEATING, GeneratorKind.ELECTRIC)
HOUSEHOLD_POWER = "haushaltsstrom"
NO_METER = "kein_zaehler"


def _kind_label(hass: Any, kind: GeneratorKind | str) -> str:
    de = str(hass.config.language or "de").startswith("de")
    names = {
        "gas_boiler": ("Gastherme", "Gas boiler"), "air_air_hp": ("Split-Klima / Luft-Luft-Wärmepumpe", "Split air conditioner / air-to-air heat pump"),
        "water_hp": ("Wärmepumpe", "Heat pump"), "district_heating": ("Fernwärme", "District heating"),
        "fireplace": ("Kaminofen", "Wood stove"), "electric": ("Elektroheizung", "Electric heating"),
    }
    k = kind.value if isinstance(kind, GeneratorKind) else kind
    return names.get(k, (k, k))[0 if de else 1]


def _gen_number(gen: dict[str, Any], key: str, kind: GeneratorKind) -> Any:
    v = gen.get(key)
    return v if v is not None else KIND_DEFAULTS.get(kind, {}).get(key, vol.UNDEFINED)


class GeneratorSubentryFlow(ConfigSubentryFlow):
    """Wärmeerzeuger: Typ → Zuordnung → Leistung → Entitäten → [Kaminofen] → Zusammenfassung; „Neu konfigurieren“."""

    def __init__(self) -> None:
        self._gen: dict[str, Any] = {}

    def _situation(self) -> dict[str, Any]:
        return dict(self._get_entry().data.get(CONF_HOUSEHOLD, {}).get("situation", {}))

    def _kind(self) -> GeneratorKind:
        return GeneratorKind(self._gen["kind"])

    def _existing_kinds(self) -> list[str]:
        return [s.data.get(CONF_GENERATOR, {}).get("kind") for s in self._get_entry().subentries.values()
                if s.subentry_type == SUBENTRY_GENERATOR]

    def _meters_for(self, kind: GeneratorKind) -> list[tuple[str, str]]:
        media = KIND_MEDIA.get(kind, ())
        return [(sid, s.title) for sid, s in self._get_entry().subentries.items()
                if s.subentry_type == SUBENTRY_METER and s.data.get(CONF_METER, {}).get("role", "main") == "main"
                and s.data.get(CONF_METER, {}).get("medium") in media]

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            self._gen = {"kind": user_input["kind"], "name": (user_input.get("name") or "").strip() or _kind_label(self.hass, user_input["kind"])}
            if self._meters_for(self._kind()) or self._kind() in ON_POWER_KINDS:
                return await self.async_step_zuordnung()
            return await self.async_step_leistung()
        have = self._existing_kinds()
        open_kinds = [k.value for k in suggested_kinds(self._situation()) if k.value not in have]
        default = open_kinds[0] if open_kinds else GeneratorKind.GAS_BOILER.value
        schema = vol.Schema({
            vol.Required("kind", default=default): _select(KINDS, "generator_kind"),
            vol.Optional("name"): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, description_placeholders={
            "vorschlag": ", ".join(_kind_label(self.hass, k) for k in open_kinds) or "–"})

    async def async_step_zuordnung(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Woher kommt die Energie: eigener Zähler oder Haushaltsstrom (Split-Klima am Hauszähler)?"""
        kind = self._kind()
        if user_input is not None:
            src = user_input["source"]
            self._gen["on_household_power"] = src == HOUSEHOLD_POWER
            self._gen["meter_id"] = src if src not in (HOUSEHOLD_POWER, NO_METER) else None
            return await self.async_step_leistung()
        options = [selector.SelectOptionDict(value=sid, label=title) for sid, title in self._meters_for(kind)]
        if kind in ON_POWER_KINDS:
            options.append(selector.SelectOptionDict(value=HOUSEHOLD_POWER, label="Haushaltsstrom" if self._de() else "Household electricity"))
        options.append(selector.SelectOptionDict(value=NO_METER, label="Ohne Zähler" if self._de() else "No meter"))
        default = HOUSEHOLD_POWER if kind in ON_POWER_KINDS else options[0]["value"]
        schema = vol.Schema({vol.Required("source", default=default): selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST))})
        return self.async_show_form(step_id="zuordnung", data_schema=schema)

    def _de(self) -> bool:
        return str(self.hass.config.language or "de").startswith("de")

    def _leistung_schema(self, g: dict[str, Any]) -> vol.Schema:
        kind = GeneratorKind(g["kind"])
        fields: dict[Any, Any] = {
            vol.Required("nominal_kw", default=_gen_number(g, "nominal_kw", kind)): _number(0.1, 100, "any", "kW"),
            vol.Optional("min_kw", description={"suggested_value": g.get("min_kw")}): _number(0, 100, "any", "kW"),
        }
        if kind == GeneratorKind.GAS_BOILER:
            fields[vol.Required("power_basis", default=g.get("power_basis", PowerBasis.OUTPUT.value))] = _select(
                [b.value for b in PowerBasis], "power_basis")
        if kind in (GeneratorKind.AIR_AIR_HP, GeneratorKind.WATER_HP):
            fields[vol.Required("cop", default=_gen_number(g, "cop", kind))] = _number(1, 8, "any")
        else:
            fields[vol.Required("efficiency", default=_gen_number(g, "efficiency", kind))] = _number(0.3, 1.1, "any")
        if kind in DHW_KINDS:
            sit_hw = self._situation().get("hot_water")
            dhw_default = g.get("central_dhw", (sit_hw == "heizung" and kind in (GeneratorKind.GAS_BOILER, GeneratorKind.DISTRICT_HEATING))
                                or (sit_hw == "waermepumpe" and kind == GeneratorKind.WATER_HP))
            fields[vol.Required("central_dhw", default=dhw_default)] = selector.BooleanSelector()
            fields[vol.Optional("max_dhw_kw", description={"suggested_value": g.get("max_dhw_kw")})] = _number(0, 100, "any", "kW")
        return vol.Schema(fields)

    def _leistung_from(self, user_input: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"nominal_kw": float(user_input["nominal_kw"])}
        for key in ("min_kw", "cop", "efficiency", "max_dhw_kw"):
            out[key] = float(user_input[key]) if user_input.get(key) is not None else None
        if "power_basis" in user_input:
            out["power_basis"] = user_input["power_basis"]
        out["central_dhw"] = bool(user_input.get("central_dhw", False))
        return out

    async def async_step_leistung(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Leistungsbereich im Heizbetrieb laut Typschild/Datenblatt."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get("min_kw") is not None and float(user_input["min_kw"]) > float(user_input["nominal_kw"]):
                errors["min_kw"] = "min_above_nominal"
            else:
                self._gen.update(self._leistung_from(user_input))
                return await self.async_step_entitaeten()
        return self.async_show_form(step_id="leistung", data_schema=self._leistung_schema(self._gen), errors=errors)

    def _entity_schema(self, g: dict[str, Any]) -> vol.Schema:
        ent = g.get("entities", {})

        def opt(key: str, cfg: selector.EntitySelectorConfig) -> tuple[Any, Any]:
            k = vol.Optional(key, description={"suggested_value": ent.get(key)}) if ent.get(key) else vol.Optional(key)
            return k, selector.EntitySelector(cfg)

        fields = dict([
            opt("energy", selector.EntitySelectorConfig(domain="sensor", device_class="energy")),
            opt("power", selector.EntitySelectorConfig(domain="sensor", device_class="power")),
            opt("heat", selector.EntitySelectorConfig(domain="sensor", device_class="energy")),
            opt("state", selector.EntitySelectorConfig(domain=["binary_sensor", "switch", "input_boolean", "sensor", "climate"])),
            opt("room", selector.EntitySelectorConfig(domain="sensor", device_class="temperature")),
        ])
        if GeneratorKind(g["kind"]) not in (GeneratorKind.FIREPLACE,):
            fields.update(dict([opt("modulation", selector.EntitySelectorConfig(domain="sensor"))]))
        return vol.Schema(fields)

    async def async_step_entitaeten(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Optionale Entitäten: eingesetzte Energie, Leistung, erzeugte Wärme, Betriebszustand, Raumtemperatur."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ents = {k: v for k, v in user_input.items() if v}
            if self._kind() == GeneratorKind.FIREPLACE and not (ents.get("state") or ents.get("room")):
                errors["base"] = "stove_entity_required"
                self._gen["entities"] = ents
            else:
                self._gen["entities"] = ents
                if self._kind() == GeneratorKind.FIREPLACE:
                    return await self.async_step_ofen()
                return await self.async_step_zusammenfassung()
        return self.async_show_form(step_id="entitaeten", data_schema=self._entity_schema(self._gen), errors=errors)

    def _ofen_schema(self, g: dict[str, Any]) -> vol.Schema:
        cur = self.hass.config.currency
        has_state = bool(g.get("entities", {}).get("state"))
        return vol.Schema({
            vol.Required("stove_detection", default=g.get("stove_detection", "entity" if has_state else "room")): _select(
                ["entity", "room"], "stove_detection"),
            vol.Required("stove_threshold_k", default=g.get("stove_threshold_k", 1.5)): _number(0.5, 5, 0.1, "K"),
            vol.Required("effective_share", default=_gen_number(g, "effective_share", GeneratorKind.FIREPLACE)): _number(0.05, 1, 0.05),
            vol.Optional("wood_price", description={"suggested_value": g.get("wood_price")}): _number(0, 10000, "any", cur),
            vol.Required("wood_price_unit", default=g.get("wood_price_unit", "rm")): _select(["kg", "rm"], "wood_price_unit"),
            vol.Required("kg_per_rm", default=g.get("kg_per_rm", 400.0)): _number(100, 800, 1, "kg"),
        })

    async def async_step_ofen(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Kaminofen: Erkennung (Betriebszustand-Entität oder Raumtemperatur), wirksamer Anteil, Holzpreis."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ent = self._gen.get("entities", {})
            if user_input["stove_detection"] == "entity" and not ent.get("state"):
                errors["stove_detection"] = "state_entity_missing"
            elif user_input["stove_detection"] == "room" and not ent.get("room"):
                errors["stove_detection"] = "room_entity_missing"
            else:
                self._gen.update({
                    "stove_detection": user_input["stove_detection"], "stove_threshold_k": float(user_input["stove_threshold_k"]),
                    "effective_share": float(user_input["effective_share"]),
                    "wood_price": float(user_input["wood_price"]) if user_input.get("wood_price") is not None else None,
                    "wood_price_unit": user_input["wood_price_unit"], "kg_per_rm": float(user_input["kg_per_rm"]),
                })
                return await self.async_step_zusammenfassung()
        return self.async_show_form(step_id="ofen", data_schema=self._ofen_schema(self._gen), errors=errors)

    def _summary(self, g: dict[str, Any]) -> str:
        """Annahmen in Worten (Systemsprache)."""
        de = self._de()
        gen, _ = from_dict(HeatGenerator, {**g, "generator_id": "probe"})
        if gen is None:
            return "–"
        lines = []

        def num(v: float, n: int = 2) -> str:
            txt = f"{v:,.{n}f}"
            return txt.replace(",", "X").replace(".", ",").replace("X", ".") if de else txt

        if gen.kind == GeneratorKind.GAS_BOILER:
            per_h = gas_per_hour(gen)
            if per_h:
                basis = ("Nennwärmebelastung × Hs/Hi" if gen.power_basis == PowerBasis.INPUT else "Nennwärmeleistung ÷ Wirkungsgrad × Hs/Hi") if de \
                    else ("rated heat input × Hs/Hi" if gen.power_basis == PowerBasis.INPUT else "rated output ÷ efficiency × Hs/Hi")
                lines.append((f"Gaseinsatz bei Volllast: {num(per_h, 1)} kWh je Stunde ({basis}, Hs/Hi = {num(HS_HI)}, Annahme)") if de
                             else f"Gas input at full load: {num(per_h, 1)} kWh per hour ({basis}, Hs/Hi = {num(HS_HI)}, assumption)")
        if gen.kind in (GeneratorKind.AIR_AIR_HP, GeneratorKind.WATER_HP):
            cop = gen_default(gen, "cop") or 0
            lines.append((f"Wärme = Strom × {num(cop, 1)} (COP, Annahme bis ein Wärmemengenzähler da ist). Die Entlastung der Heizung "
                          "wird erst aus deinen Daten gelernt (Vergleichstage).") if de
                         else f"Heat = electricity × {num(cop, 1)} (COP, assumption until a heat meter exists). The relief of the heating "
                              "is learned from your data only (comparison days).")
        if gen.kind == GeneratorKind.FIREPLACE:
            relief = stove_relief_per_hour(gen, Medium.GAS) or 0
            lines.append((f"Vor genug Vergleichstagen (je 10 mit und ohne Ofen): Entlastung {num(relief, 1)} kWh Gas je Ofenstunde "
                          "(Nennleistung × wirksamer Anteil ÷ 0,9 × Hs/Hi, Annahme). Holz: eingesetzte Energie ÷ 4,2 kWh/kg (Schätzung).") if de
                         else f"Until there are enough comparison days (10 with and without stove): relief {num(relief, 1)} kWh gas per stove "
                              "hour (rated output × effective share ÷ 0.9 × Hs/Hi, assumption). Wood: energy input ÷ 4.2 kWh/kg (estimate).")
        if gen.meter_id and gen.kind in ON_POWER_KINDS:
            title = next((s.title for sid, s in self._get_entry().subentries.items() if sid == gen.meter_id), gen.meter_id)
            lines.append(f"Der Zähler „{title}“ gilt komplett als Heizstrom (keine Grundlast)." if de
                         else f"The meter “{title}” counts completely as heating electricity (no base load).")
        if not g.get("entities"):
            lines.append("Ohne Entitäten zählt nur, was ein zugeordneter Zähler misst." if de else "Without entities only an assigned meter is used.")
        return "\n\n".join(lines) or "–"

    async def async_step_zusammenfassung(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if user_input is not None:
            data = {k: v for k, v in self._gen.items() if k != "name"}
            return self.async_create_entry(title=self._gen["name"], data={CONF_GENERATOR: {**data, "name": self._gen["name"]}})
        return self.async_show_form(step_id="zusammenfassung", data_schema=vol.Schema({}),
                                    description_placeholders={"annahmen": self._summary(self._gen)})

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Leistung, Entitäten und (Kaminofen) Erkennung/Holz in einem Formular ändern."""
        entry = self._get_entry()
        sub = self._get_reconfigure_subentry()
        g = dict(sub.data.get(CONF_GENERATOR, {}))
        kind = GeneratorKind(g["kind"])
        errors: dict[str, str] = {}
        schema = vol.Schema({vol.Required("name", default=g.get("name") or sub.title): str}).extend(
            self._leistung_schema(g).schema).extend(self._entity_schema(g).schema)
        if kind == GeneratorKind.FIREPLACE:
            schema = schema.extend(self._ofen_schema(g).schema)
        if user_input is not None:
            ents = {k: user_input[k] for k in ("energy", "power", "heat", "state", "room", "modulation") if user_input.get(k)}
            if user_input.get("min_kw") is not None and float(user_input["min_kw"]) > float(user_input["nominal_kw"]):
                errors["min_kw"] = "min_above_nominal"
            elif kind == GeneratorKind.FIREPLACE and user_input.get("stove_detection") == "entity" and not ents.get("state"):
                errors["stove_detection"] = "state_entity_missing"
            elif kind == GeneratorKind.FIREPLACE and user_input.get("stove_detection") == "room" and not ents.get("room"):
                errors["stove_detection"] = "room_entity_missing"
            else:
                g.update(self._leistung_from(user_input))
                g["entities"] = ents
                g["name"] = user_input["name"]
                if kind == GeneratorKind.FIREPLACE:
                    g.update({
                        "stove_detection": user_input["stove_detection"], "stove_threshold_k": float(user_input["stove_threshold_k"]),
                        "effective_share": float(user_input["effective_share"]),
                        "wood_price": float(user_input["wood_price"]) if user_input.get("wood_price") is not None else None,
                        "wood_price_unit": user_input["wood_price_unit"], "kg_per_rm": float(user_input["kg_per_rm"]),
                    })
                return self.async_update_and_abort(entry, sub, title=user_input["name"], data={CONF_GENERATOR: g})
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)
