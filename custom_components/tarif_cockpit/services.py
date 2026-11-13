"""Services: Ablesungen, Folgevertrag, Ablesetermin, Perioden von Hand, Neuberechnung der Tageswerte.

Der Zähler wird über sein Gerät gewählt (Geräte-Selektor). Ablesungen werden nur angehängt; eine Korrektur
ersetzt eine frühere Ablesung, ohne sie zu löschen. Beendete Perioden werden nicht verändert (Regel 3).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .engine import billing
from .engine.model import BillingRule, Contract, Medium, PeriodSpan, ReadingSource, VatMode, new_id
from .engine.quality import Quality
from .runtime import TarifRuntime

ATTR_METER = "zaehler"
DEFAULT_VAT = {Medium.STROM: 19.0, Medium.GAS: 19.0, Medium.WASSER: 7.0, Medium.FERNWAERME: 19.0}

SCHEMA_ADD_READING = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("stand"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("zeitpunkt"): cv.datetime,
    vol.Optional("qualitaet", default="real"): vol.In(["real", "estimated"]),
    vol.Optional("notiz"): cv.string,
    vol.Optional("ersetzt"): cv.string,
})
SCHEMA_INVALIDATE = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("ablesung_id"): cv.string,
    vol.Optional("grund"): cv.string,
})
SCHEMA_FOLLOW_UP = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("lieferant"): cv.string,
    vol.Required("beginn"): cv.date,
    vol.Required("abrechnungsregel"): vol.In([r.value for r in BillingRule]),
    vol.Optional("tarif"): cv.string,
    vol.Optional("stichtag"): cv.string,
    vol.Optional("erste_periode_ende"): cv.date,
    vol.Optional("vat_mode", default="gross"): vol.In([v.value for v in VatMode]),
    vol.Optional("vat_rate"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    vol.Optional("wechselstand"): vol.All(vol.Coerce(float), vol.Range(min=0)),
})
SCHEMA_PERIOD_END = vol.Schema({vol.Required(ATTR_METER): cv.string, vol.Required("ende"): cv.date})
SCHEMA_RECALC = vol.Schema({
    vol.Optional(ATTR_METER): cv.string,
    vol.Optional("von"): cv.date,
    vol.Optional("bis"): cv.date,
})


def _resolve(hass: HomeAssistant, device_id: str) -> tuple[TarifRuntime, str]:
    """Gerät → (Laufzeitdaten, meter_id)."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_meter", translation_placeholders={"id": device_id})
    meter_id = next((ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED and meter_id in entry.runtime_data.meters:
            return entry.runtime_data, meter_id
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_meter", translation_placeholders={"id": device_id})


def _billing_error(err: billing.BillingError, key: str = "contract_invalid") -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key, translation_placeholders={"error": str(err)})


def _unknown_reading(err: KeyError) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_reading", translation_placeholders={"id": str(err.args[0])})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def add_reading(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        ts: datetime = call.data.get("zeitpunkt") or dt_util.now()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=rt.tz)
        if ts > dt_util.now() + timedelta(minutes=5):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="reading_in_future")
        try:
            reading = rt.add_reading(
                meter_id, ts, call.data["stand"], Quality(call.data["qualitaet"]), ReadingSource.MANUAL,
                call.data.get("notiz"), call.data.get("ersetzt"),
            )
        except KeyError as err:
            raise _unknown_reading(err) from err
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="reading_already_replaced", translation_placeholders={"id": str(err.args[0])}
            ) from err
        await rt.after_readings_changed(meter_id)
        return {"ablesung_id": reading.reading_id}

    async def invalidate(call: ServiceCall) -> None:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        try:
            rt.invalidate_reading(meter_id, call.data["ablesung_id"], call.data.get("grund"))
        except KeyError as err:
            raise _unknown_reading(err) from err
        await rt.after_readings_changed(meter_id)

    async def follow_up(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        start: date = call.data["beginn"]
        rule = BillingRule(call.data["abrechnungsregel"])
        manual: list[PeriodSpan] = []
        if rule == BillingRule.MANUAL:
            if "erste_periode_ende" not in call.data:
                raise _billing_error(billing.BillingError("Bei 'von Hand' wird erste_periode_ende gebraucht"))
            manual = [PeriodSpan(start, call.data["erste_periode_ende"])]
        new = Contract(
            contract_id=new_id(), meter_id=meter_id, supplier=call.data["lieferant"], start_date=start,
            billing_rule=rule, tariff=call.data.get("tarif"), manual_periods=manual,
            fixed_day=call.data.get("stichtag") if rule == BillingRule.FIXED_DAY else None,
            vat_mode=VatMode(call.data["vat_mode"]),
            vat_rate=call.data.get("vat_rate", DEFAULT_VAT[rt.meters[meter_id].medium]),
        )
        try:
            old, created = rt.add_follow_up(new)
        except billing.BillingError as err:
            raise _billing_error(err) from err
        if "wechselstand" in call.data:
            ts = datetime.combine(start, time(0), tzinfo=rt.tz)
            rt.add_reading(meter_id, ts, call.data["wechselstand"], Quality.REAL, ReadingSource.SWITCH, "Wechselablesung")
            await rt.after_readings_changed(meter_id)
        else:
            rt.changed()
        return {"vertrag_id": created.contract_id, "alter_vertrag_endet": old.end_date.isoformat() if old.end_date else None}

    async def period_end(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        try:
            bp = rt.set_period_end(meter_id, call.data["ende"])
        except billing.BillingError as err:
            raise _billing_error(err, "period_invalid") from err
        rt.changed()
        return {"periode_id": bp.period_id, "beginn": bp.start_date.isoformat(), "ende": bp.end_date.isoformat()}

    async def add_period(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        try:
            contract = rt.append_manual_period(meter_id, call.data["ende"])
        except billing.BillingError as err:
            raise _billing_error(err, "period_invalid") from err
        rt.changed()
        last = contract.manual_periods[-1]
        return {"beginn": last.start.isoformat(), "ende": last.end.isoformat()}

    async def recalculate(call: ServiceCall) -> None:
        targets: list[tuple[TarifRuntime, list[str] | None]] = []
        if ATTR_METER in call.data:
            rt, meter_id = _resolve(hass, call.data[ATTR_METER])
            targets.append((rt, [meter_id]))
        else:
            targets = [(e.runtime_data, None) for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
        for rt, meters in targets:
            await rt.aggregator.async_run(meters=meters, start=call.data.get("von"), end=call.data.get("bis"), overwrite=True)

    reg = hass.services.async_register
    reg(DOMAIN, "add_ablesung", add_reading, SCHEMA_ADD_READING, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "ablesung_ungueltig", invalidate, SCHEMA_INVALIDATE)
    reg(DOMAIN, "add_folgevertrag", follow_up, SCHEMA_FOLLOW_UP, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "set_periodenende", period_end, SCHEMA_PERIOD_END, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "add_periode", add_period, SCHEMA_PERIOD_END, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "recalculate", recalculate, SCHEMA_RECALC)
