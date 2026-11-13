"""Diagnose-Download für Fehlerberichte: Haushalt, Zähler, Verträge, Perioden, Umfang der Daten."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import TarifConfigEntry
from .engine.model import to_dict
from .engine.quality import Quality


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: TarifConfigEntry) -> dict[str, Any]:
    rt = entry.runtime_data
    ds = rt.data
    meters = {}
    for meter_id, meter in rt.meters.items():
        spec = rt.current_period(meter_id)
        daily = [d for d in ds.daily if d.meter_id == meter_id]
        meters[meter_id] = {
            "meter": to_dict(meter),
            "contracts": [to_dict(c) for c in rt.contracts(meter_id)],
            "current_period": None if spec is None else {
                "start": spec.start_date.isoformat(), "end": spec.end_date.isoformat(),
                "partial": spec.is_partial, "final": spec.is_final,
            },
            "readings_last_10": [to_dict(r) for r in rt.readings(meter_id)[-10:]],
            "daily_count": len(daily),
            "daily_by_quality": {q.value: sum(1 for d in daily if d.quality == q) for q in Quality},
            "daily_last_7": [to_dict(d) for d in sorted(daily, key=lambda d: d.date)[-7:]],
        }
    return {
        "household": to_dict(rt.household),
        "store": {"key": rt.store.key, "version": rt.store.version, "minor_version": rt.store.minor_version, "blocked": rt.store.blocked},
        "counts": {k: len(v) for k, v in ds.to_dict().items() if isinstance(v, list)},
        "meters": meters,
    }
