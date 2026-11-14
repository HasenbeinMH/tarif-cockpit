"""Services: Ablesungen, Folgevertrag, Ablesetermin, Perioden von Hand, Neuberechnung der Tageswerte.

Der Zähler wird über sein Gerät gewählt (Geräte-Selektor). Ablesungen werden nur angehängt; eine Korrektur
ersetzt eine frühere Ablesung, ohne sie zu löschen. Beendete Perioden werden nicht verändert (Regel 3).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .engine import billing
from .engine.model import BillingRule, Contract, Medium, PaymentStatus, PaymentType, PeriodSpan, ReadingSource, VatMode, new_id, to_dict
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
    vol.Optional("mindestlaufzeit"): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
    vol.Optional("kuendigungsfrist"): vol.All(vol.Coerce(int), vol.Range(min=0, max=104)),
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
        # Abgleich (0.9): bei einer Ablesung "jetzt" den Stand des Zähler-Sensors mit merken
        sensor_value = None
        if rt.meters[meter_id].entity and rt.coordinator is not None and abs((ts - dt_util.now()).total_seconds()) <= 600:
            sensor_value = rt.coordinator.sensor_raw(meter_id)
        try:
            reading = rt.add_reading(
                meter_id, ts, call.data["stand"], Quality(call.data["qualitaet"]), ReadingSource.MANUAL,
                call.data.get("notiz"), call.data.get("ersetzt"), sensor_value=sensor_value,
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
            min_term_months=call.data.get("mindestlaufzeit"), notice_period_weeks=call.data.get("kuendigungsfrist"),
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

    def reg(domain: str, name: str, func: Any, schema: Any, supports_response: SupportsResponse = SupportsResponse.NONE) -> None:
        # Schreibende Aktionen nur für Administratoren; Automationen und Skripte laufen ohne Benutzer und sind nicht betroffen
        async_register_admin_service(hass, domain, name, func, schema, supports_response)

    reg(DOMAIN, "add_ablesung", add_reading, SCHEMA_ADD_READING, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "ablesung_ungueltig", invalidate, SCHEMA_INVALIDATE)
    reg(DOMAIN, "add_folgevertrag", follow_up, SCHEMA_FOLLOW_UP, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "set_periodenende", period_end, SCHEMA_PERIOD_END, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "add_periode", add_period, SCHEMA_PERIOD_END, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "recalculate", recalculate, SCHEMA_RECALC)
    async_setup_services_06(hass)
    async_setup_service_v03(hass)


# ---------------------------------------------------------------- Preise, Abschläge, Zahlungen, Rechnungen (0.6)

SCHEMA_PRICE = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("ab"): cv.date,
    vol.Required("arbeitspreis"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Required("grundpreis"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("messpreis"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("brennwert"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("zustandszahl"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("abwasserpreis"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("fest_jahr"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("leistungspreis"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("anschlussleistung"): vol.All(vol.Coerce(float), vol.Range(min=0)),
})
SCHEMA_ADVANCE = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("ab"): cv.date,
    vol.Required("betrag"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("zahltag"): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
    vol.Optional("rhythmus"): vol.All(vol.Coerce(int), vol.In([1, 2, 3])),
    vol.Optional("anzahl_je_periode"): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
})
SCHEMA_PAYMENT = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("datum"): cv.date,
    vol.Required("betrag"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("art", default="one_off"): vol.In([t.value for t in PaymentType]),
    vol.Optional("status", default="paid"): vol.In([s.value for s in PaymentStatus]),
})
SCHEMA_INVOICE = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Required("datum"): cv.date,
    vol.Required("von"): cv.date,
    vol.Required("bis"): cv.date,
    vol.Required("betrag"): vol.Coerce(float),
    vol.Optional("korrigiert"): cv.string,
})

PRICE_FIELDS = {
    "arbeitspreis": "work_price", "grundpreis": "base_price", "messpreis": "metering_price", "brennwert": "calorific",
    "zustandszahl": "z_factor", "abwasserpreis": "wastewater_price", "fest_jahr": "fixed_yearly",
    "leistungspreis": "demand_price", "anschlussleistung": "demand_kw",
}


@callback
def async_setup_services_06(hass: HomeAssistant) -> None:
    async def set_price(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        values = {PRICE_FIELDS[k]: v for k, v in call.data.items() if k in PRICE_FIELDS}
        try:
            seg = rt.set_price(meter_id, call.data["ab"], **values)
        except billing.BillingError as err:
            raise _billing_error(err, "period_invalid") from err
        rt.changed(meter_id=meter_id, flags={"costs"})
        return {"vertrag_id": seg.contract_id, "ab": seg.valid_from.isoformat()}

    async def set_advance(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        try:
            plan = rt.set_advance(meter_id, call.data["ab"], call.data["betrag"], call.data.get("zahltag"),
                                  call.data.get("rhythmus"), call.data.get("anzahl_je_periode"))
        except billing.BillingError as err:
            raise _billing_error(err, "period_invalid") from err
        rt.changed(meter_id=meter_id, flags={"payments"})
        return {"stufen": [{"ab": s.from_date.isoformat(), "betrag": s.amount} for s in plan.steps]}

    async def add_payment(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        try:
            p = rt.add_payment(meter_id, call.data["datum"], call.data["betrag"], PaymentType(call.data["art"]), PaymentStatus(call.data["status"]))
        except billing.BillingError as err:
            raise _billing_error(err, "period_invalid") from err
        rt.changed(meter_id=meter_id, flags={"payments"})
        return {"zahlung_id": p.payment_id}

    async def add_invoice(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        if call.data["bis"] < call.data["von"]:
            raise _billing_error(billing.BillingError("'bis' liegt vor 'von'"), "period_invalid")
        try:
            inv = rt.add_invoice(meter_id, call.data["datum"], call.data["von"], call.data["bis"], call.data["betrag"], call.data.get("korrigiert"))
        except billing.BillingError as err:
            raise _billing_error(err, "period_invalid") from err
        except KeyError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_invoice", translation_placeholders={"id": str(err.args[0])}) from err
        rt.changed(meter_id=meter_id, flags=set())
        return {"rechnung_id": inv.invoice_id}

    def reg(domain: str, name: str, func: Any, schema: Any, supports_response: SupportsResponse = SupportsResponse.NONE) -> None:
        # Schreibende Aktionen nur für Administratoren; Automationen und Skripte laufen ohne Benutzer und sind nicht betroffen
        async_register_admin_service(hass, domain, name, func, schema, supports_response)

    reg(DOMAIN, "set_preis", set_price, SCHEMA_PRICE, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "set_abschlag", set_advance, SCHEMA_ADVANCE, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "add_zahlung", add_payment, SCHEMA_PAYMENT, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "add_rechnung", add_invoice, SCHEMA_INVOICE, supports_response=SupportsResponse.OPTIONAL)



# ---------------------------------------------------------------- Übernahme aus 0.3 (1.0)

SCHEMA_V03 = vol.Schema({
    vol.Required(ATTR_METER): cv.string,
    vol.Optional("ab"): cv.date,
    vol.Optional("abschlag"): cv.entity_id,
    vol.Optional("zahltag"): cv.entity_id,
    vol.Optional("arbeitspreis"): cv.entity_id,
    vol.Optional("grundpreis"): cv.entity_id,
    vol.Optional("startstand"): cv.entity_id,
    vol.Optional("abrechnungsbeginn"): cv.entity_id,
    vol.Optional("brennwert"): cv.entity_id,
    vol.Optional("zustandszahl"): cv.entity_id,
})


@callback
def async_setup_service_v03(hass: HomeAssistant) -> None:
    """``tarif_cockpit.uebernahme_v03``: Werte aus den Helfern von 0.3 in einen Zähler übernehmen."""

    def num(entity_id: str | None) -> float | None:
        st = hass.states.get(entity_id) if entity_id else None
        try:
            return float(st.state) if st is not None else None
        except (TypeError, ValueError):
            return None

    def day(entity_id: str | None) -> date | None:
        st = hass.states.get(entity_id) if entity_id else None
        if st is None:
            return None
        try:
            return date.fromisoformat(str(st.state)[:10])
        except ValueError:
            return None

    async def take_over(call: ServiceCall) -> ServiceResponse:
        rt, meter_id = _resolve(hass, call.data[ATTR_METER])
        taken: list[str] = []
        skipped: list[dict[str, str]] = []
        spec = rt.current_period(meter_id)
        start = call.data.get("ab") or day(call.data.get("abrechnungsbeginn")) or (spec.start_date if spec else rt.today())

        def skip(field: str, reason: str) -> None:
            if call.data.get(field):
                skipped.append({"feld": field, "grund": reason})

        work, base = num(call.data.get("arbeitspreis")), num(call.data.get("grundpreis"))
        contract = billing.contract_on(rt.contracts(meter_id), start)
        # vorhandenen Preisabschnitt zum Datum übernehmen, nur die gelesenen Werte ersetzen (fehlend ist nie 0)
        existing = None if contract is None else next(
            (p for p in sorted(rt.data.prices, key=lambda p: p.valid_from, reverse=True)
             if p.contract_id == contract.contract_id and p.valid_from <= start and (p.valid_to is None or p.valid_to >= start)), None)
        if base is None and existing is not None:
            base = existing.base_price
        if work is not None and base is None:
            for f in ("arbeitspreis", "grundpreis", "brennwert", "zustandszahl"):
                skip(f, "Grundpreis fehlt (kein Zahlenwert und kein Preis aus der Einrichtung)")
        elif work is not None:
            values: dict = {}
            if existing is not None:
                values = {k: v for k, v in to_dict(existing).items() if k not in ("contract_id", "valid_from", "valid_to")}
                values["components"] = dict(existing.components)
            values.update(work_price=work, base_price=base)
            cal, z = num(call.data.get("brennwert")), num(call.data.get("zustandszahl"))
            if cal is not None:
                values["calorific"] = cal
            if z is not None:
                values["z_factor"] = z
            try:
                rt.set_price(meter_id, start, **values)
                taken += ["arbeitspreis"] + [k for k in ("grundpreis", "brennwert", "zustandszahl") if num(call.data.get(k)) is not None]
                for k in ("grundpreis", "brennwert", "zustandszahl"):
                    if call.data.get(k) and num(call.data.get(k)) is None:
                        skip(k, "kein Zahlenwert")
            except billing.BillingError as err:
                for f in ("arbeitspreis", "grundpreis", "brennwert", "zustandszahl"):
                    skip(f, str(err))
        else:
            skip("arbeitspreis", "kein Zahlenwert")
        amount = num(call.data.get("abschlag"))
        if amount is not None:
            pay_day = num(call.data.get("zahltag"))
            try:
                rt.set_advance(meter_id, start, amount, int(pay_day) if pay_day else None)
                taken += ["abschlag"] + (["zahltag"] if pay_day else [])
            except billing.BillingError as err:
                skip("abschlag", str(err))
        else:
            skip("abschlag", "kein Zahlenwert")
        reading = num(call.data.get("startstand"))
        if reading is not None:
            ts = datetime.combine(start, time(0), tzinfo=rt.tz)
            same = [r for r in rt.readings(meter_id) if r.timestamp == ts and not r.superseded_by and r.quality != Quality.INVALID]
            try:
                rt._not_in_ended_period(meter_id, start, "Ein Startstand")  # noqa: SLF001
                ended = None
            except billing.BillingError as err:
                ended = str(err)
            if ended:
                skip("startstand", ended)
            elif any(abs(r.value - reading) < 1e-9 for r in same):
                skip("startstand", "schon vorhanden")
            elif same:
                skip("startstand", f"zum {start} gibt es schon den Stand {same[0].value}; bitte mit add_ablesung und ersetzt korrigieren")
            else:
                rt.add_reading(meter_id, ts, reading, Quality.REAL, ReadingSource.IMPORT, "Übernahme aus 0.3")
                taken.append("startstand")
        else:
            skip("startstand", "kein Zahlenwert")
        if call.data.get("abrechnungsbeginn") and spec is not None and day(call.data["abrechnungsbeginn"]) not in (None, spec.start_date):
            skipped.append({"feld": "abrechnungsbeginn", "grund": f"Periode beginnt laut Vertrag am {spec.start_date}; bitte Vertrag prüfen"})
        await rt.after_readings_changed(meter_id)
        rt.changed(meter_id=meter_id)
        return {"uebernommen": taken, "uebersprungen": skipped, "ab": start.isoformat()}

    async_register_admin_service(hass, DOMAIN, "uebernahme_v03", take_over, SCHEMA_V03, SupportsResponse.OPTIONAL)
