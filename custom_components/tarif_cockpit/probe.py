"""Probe-Auswertung für die Zusammenfassung der Einrichtung: erste Prognose mit Qualität, ohne etwas zu speichern.

Der Rechenkern rechnet wie nach dem Speichern (Tageswerte aus der Statistik, Prognose, Kosten, Saldo); nur der Store
bleibt unberührt. Ohne geladene Integration oder ohne Zähler-Sensor steht dort ein Hinweis statt einer Zahl.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import BACKFILL_DAYS
from .engine.balance import evaluate_meter
from .engine.model import AdvancePlan, AdvanceStep, Contract, Meter, PriceSegment, Reading, from_dict
from .engine.quality import Quality
from .engine.pulses import unit_per_pulse
from .engine.units import convert

_LOGGER = logging.getLogger(__name__)


def _de(hass: HomeAssistant) -> bool:
    return str(hass.config.language or "de").startswith("de")


def _num(hass: HomeAssistant, v: Any, dec: int | None = None) -> str:
    """Zahl in der Schreibweise der Systemsprache (de: 1.234,56); ohne dec so viele Stellen wie nötig."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "–"
    txt = f"{f:,.{dec}f}" if dec is not None else f"{f:,.6f}".rstrip("0").rstrip(".")
    return txt.replace(",", "X").replace(".", ",").replace("X", ".") if _de(hass) else txt


def _money(hass: HomeAssistant, v: float | None) -> str:
    if v is None:
        return "–"
    return f"{_num(hass, v, 2)} {hass.config.currency}"


async def async_probe_summary(hass: HomeAssistant, rt: Any, data: dict[str, Any]) -> dict[str, str]:
    """Platzhalter für den Dialog „Zusammenfassung“: perioden, preis, abschlag, prognose.
    Ein Fehler in der Probe-Rechnung bricht die Einrichtung nie ab; dann steht dort der Standardtext."""
    try:
        return await _probe_summary(hass, rt, data)
    except Exception:  # noqa: BLE001 - nur Vorschau, der Zähler wird trotzdem angelegt
        _LOGGER.exception("Tarif-Cockpit: Probe-Prognose für die Zusammenfassung fehlgeschlagen")
        de = _de(hass)
        from .config_flow import MeterSubentryFlow  # noqa: PLC0415

        return {"perioden": MeterSubentryFlow._preview(data.get("contract", {})), "preis": "–", "abschlag": "–",
                "prognose": "Die Prognose erscheint nach dem Speichern." if de else "The forecast appears after saving."}


async def _probe_summary(hass: HomeAssistant, rt: Any, data: dict[str, Any]) -> dict[str, str]:
    de = _de(hass)
    raw = data["contract"]
    contract, _ = from_dict(Contract, dict(raw, contract_id="probe", meter_id="probe"))
    price = data.get("price") or {}
    plan = data.get("plan")
    from .config_flow import MeterSubentryFlow  # noqa: PLC0415

    out = {
        "perioden": MeterSubentryFlow._preview(raw),
        "preis": (f"{_num(hass, price.get('work_price'))} {hass.config.currency}/{'m³' if data['medium'] == 'wasser' else 'kWh'}, "
                  f"{'Grundpreis' if de else 'standing charge'} {_num(hass, price.get('base_price'), 2)} {hass.config.currency}/{'Monat' if de else 'month'}")
        if price else "–",
        "abschlag": (f"{_num(hass, plan['amount'], 2)} {hass.config.currency} · {'Zahltag' if de else 'day'} {int(plan['pay_day'])} · "
                     + ((f"alle {int(plan['rhythm'])} Monate" if de else f"every {int(plan['rhythm'])} months") if int(plan['rhythm']) > 1
                        else ("monatlich" if de else "monthly"))) if plan else ("keine" if de else "none"),
        "prognose": ("Die Prognose erscheint nach dem Speichern." if de else "The forecast appears after saving."),
    }
    # Mit Sensor oder mit Jahresverbrauch (Annahme) lässt sich schon eine erste Prognose rechnen
    if rt is None or rt.aggregator is None or contract is None or not (data.get("entity") or data.get("annual_consumption")):
        return out
    meter_raw = {k: v for k, v in data.items() if k in ("medium", "unit", "entity", "name", "history_entity", "annual_consumption", "pulse_constant", "pulse_mode")}
    meter, _ = from_dict(Meter, {**meter_raw, "meter_id": "probe", "conversion": data.get("conversion", {}),
                                    "data_level": 2, "role": "main"})
    if meter is None:
        return out
    tz = rt.tz
    today = dt_util.now(tz).date()
    days = [today - timedelta(days=i) for i in range(BACKFILL_DAYS, 0, -1)]
    readings: list[Reading] = []
    if data.get("reading"):
        r = data["reading"]
        readings.append(Reading("probe-r", "probe", datetime.fromisoformat(r["timestamp"]), float(r["value"]), Quality(r.get("quality", "real"))))
    daily = {v.date: v for v in await rt.aggregator.async_compute(meter, days, readings)} if meter.entity else {}
    st = hass.states.get(meter.entity) if meter.entity else None
    current = None
    try:
        if st is not None and meter.pulse_constant:
            k = unit_per_pulse(meter.pulse_constant, meter.pulse_mode)
            current = (dt_util.now(tz), float(st.state) * k) if k else None
        elif st is not None:
            current = (dt_util.now(tz), convert(float(st.state), st.attributes.get("unit_of_measurement"), meter.unit))
    except (TypeError, ValueError):
        current = None
    prices = [PriceSegment("probe", contract.start_date, **price)] if price else []
    plans = [AdvancePlan("probe", [AdvanceStep(contract.start_date, float(plan["amount"]))], int(plan["pay_day"]),
                         int(plan["rhythm"]), plan.get("max_per_period"))] if plan else []
    if contract.start_date > today:
        return out
    res = evaluate_meter(meter, [contract], prices, plans, [], readings, daily, dt_util.now(tz), tz, current,
                         rt.household.tolerance_pct)
    q = res.forecast.quality.value if res.forecast else "unzureichend"
    q_txt = {"sehr_gut": ("sehr gut", "very good"), "gut": ("gut", "good"), "vorlaeufig": ("vorläufig", "preliminary"),
             "annahme": ("Annahme", "assumption"), "unzureichend": ("unzureichend", "insufficient")}.get(q, (q, q))[0 if de else 1]
    if res.balance and res.balance.forecast_cost is not None:
        verdict = {"passt": ("passt", "on track"), "rueckzahlung": ("Rückzahlung", "refund"),
                   "nachzahlung": ("Nachzahlung", "back payment")}.get(res.balance.verdict or "", ("–", "–"))[0 if de else 1]
        out["prognose"] = (f"{'Kosten der Periode' if de else 'Costs of the period'} {_money(hass, res.balance.forecast_cost)}"
                           f" ({'Qualität' if de else 'quality'}: {q_txt})"
                           + (f", {verdict} {_money(hass, abs(res.balance.saldo))}" if res.balance.saldo is not None else ""))
    else:
        reason = res.forecast.details.get("grund") if res.forecast else None
        out["prognose"] = (f"{'Noch keine Prognose' if de else 'No forecast yet'} ({'Qualität' if de else 'quality'}: {q_txt}"
                           + (f"; {reason}" if reason and de else "") + ")")
    return out
