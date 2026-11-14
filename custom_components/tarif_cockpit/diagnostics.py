"""Diagnose-Download für Fehlerberichte (1.0): Haushalt, Zähler, Verträge, Perioden mit Archiv, Preise, Pläne, Zahlungen,
Schnappschüsse, Ergebnisse, Erzeuger und Abgleich. Entitäts-IDs, Namen und Lieferanten werden geschwärzt."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TarifConfigEntry
from .engine.model import to_dict
from .engine.quality import Quality

TO_REDACT = {
    "entity", "history_entity", "outdoor_temp_entity", "weather_entity", "room_entity", "entities", "rooms",
    "name", "supplier", "tariff", "note", "lieferant", "tarif",
}


def _result(res: Any) -> dict[str, Any] | None:
    if res is None:
        return None
    return {
        "period": None if res.period is None else {"start": res.period.start_date.isoformat(), "end": res.period.end_date.isoformat()},
        "used_billing": res.used_billing, "forecast_total": res.forecast_total,
        "forecast": None if res.forecast is None else {"method": res.forecast.method, "quality": res.forecast.quality.value,
                                                       "rest": res.forecast.rest, "details": res.forecast.details},
        "heat_model": None if res.heat_model is None else res.heat_model.as_dict(),
        "balance": None if res.balance is None else to_dict(res.balance),
        "flags": res.flags,
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: TarifConfigEntry) -> dict[str, Any]:
    rt = entry.runtime_data
    ds = rt.data
    coord = rt.coordinator
    meters = {}
    for meter_id, meter in rt.meters.items():
        spec = rt.current_period(meter_id)
        daily = [d for d in ds.daily if d.meter_id == meter_id]
        ids = {c.contract_id for c in rt.contracts(meter_id)}
        rec = coord.reconciliations.get(meter_id) if coord is not None else None
        meters[meter_id] = {
            "meter": to_dict(meter),
            "contracts": [to_dict(c) for c in rt.contracts(meter_id)],
            "current_period": None if spec is None else {
                "start": spec.start_date.isoformat(), "end": spec.end_date.isoformat(),
                "partial": spec.is_partial, "final": spec.is_final,
            },
            "periods": [to_dict(p) for p in ds.periods if p.contract_id in ids],
            "prices": [to_dict(p) for p in ds.prices if p.contract_id in ids],
            "plans": [to_dict(p) for p in ds.advance_plans if p.contract_id in ids],
            "payments": [to_dict(p) for p in ds.payments if p.contract_id in ids],
            "readings_last_10": [to_dict(r) for r in rt.readings(meter_id)[-10:]],
            "daily_count": len(daily),
            "daily_by_quality": {q.value: sum(1 for d in daily if d.quality == q) for q in Quality},
            "daily_last_7": [to_dict(d) for d in sorted(daily, key=lambda d: d.date)[-7:]],
            "result": _result(coord.results.get(meter_id)) if coord is not None else None,
            "reconciliation": None if rec is None else {
                "offset": rec.offset, "factor_median": rec.factor_median, "flags": rec.flags,
                "intervals": [{"start": i.start.isoformat(), "end": i.end.isoformat(), "read": i.read, "measured": i.measured,
                               "deviation_pct": i.deviation_pct, "applied": i.applied, "flags": i.flags} for i in rec.intervals[-5:]],
            },
        }
    generators = {gid: {"generator": to_dict(g), "result": to_dict(coord.gen_results[gid]) if coord is not None and gid in coord.gen_results else None}
                  for gid, g in rt.generators.items()}
    data = {
        "household": to_dict(rt.household),
        "store": {"key": rt.store.key, "version": rt.store.version, "minor_version": rt.store.minor_version, "blocked": rt.store.blocked},
        "counts": {k: len(v) for k, v in ds.to_dict().items() if isinstance(v, list)},
        "snapshots_last_12": [to_dict(s) for s in ds.snapshots[-12:]],
        "weather_forecast_days": len(coord.forecast_dd) if coord is not None else 0,
        "meters": meters,
        "generators": generators,
    }
    return async_redact_data(data, TO_REDACT)
