"""Persistenter Store mit Versionsnummer und Migrationen (Arbeitspaket 2.1, Regel 3 und 8).

Schutz gegen stillen Datenverlust:
- Beschädigtes JSON benennt Home Assistant selbst um (``<datei>.corrupt.<zeit>``) und meldet es; ``async_load``
  liefert dann ``None``. Weil der Eintrag sich merkt, dass schon einmal gespeichert wurde (``store_created``),
  startet die Integration in diesem Fall nicht leer, sondern meldet ``store_verloren``.
- Inhaltlich ungültige Daten (Prüfung im Rechenkern) werden gemeldet; es wird nichts gespeichert.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_MINOR_VERSION, STORAGE_SAVE_DELAY, STORAGE_VERSION
from .engine.model import Dataset

_LOGGER = logging.getLogger(__name__)


class TarifStore(Store[dict[str, Any]]):
    """Store je Haushalt (Config Entry)."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            minor_version=STORAGE_MINOR_VERSION,
            atomic_writes=True,
        )
        self._dataset: Dataset | None = None
        self.blocked = False  # True bei ungültigen Daten: niemals speichern
        self.closed = False  # True nach dem Entladen: spätere Änderungen alter Laufzeitdaten nicht mehr schreiben

    async def _async_migrate_func(self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]) -> dict[str, Any]:
        """Store-Migrationen. Jede Stufe einzeln, Daten werden nur ergänzt, nie verworfen."""
        if old_major_version > STORAGE_VERSION:
            raise NotImplementedError(f"Store-Version {old_major_version} ist neuer als diese Integration")
        data = dict(old_data)
        if old_major_version == 1 and old_minor_version < 2:
            # 1.1 → 1.2: Ablesungen haben jetzt ein Qualitätsmerkmal; Altbestand war immer echt abgelesen
            readings = []
            for r in data.get("readings", []):
                r = dict(r)
                r.setdefault("quality", "real")
                readings.append(r)
            data["readings"] = readings
            _LOGGER.info("Tarif-Cockpit: Store von 1.%s auf 1.2 migriert (%s Ablesungen)", old_minor_version, len(readings))
        return data

    def schedule_save(self, dataset: Dataset) -> None:
        """Verzögert speichern (mehrere Änderungen werden zusammengefasst)."""
        if self.closed:
            return
        if self.blocked:
            _LOGGER.error("Tarif-Cockpit: Speichern blockiert, weil die gespeicherten Daten ungültig sind")
            return
        self._dataset = dataset
        self.async_delay_save(self._data_to_save, STORAGE_SAVE_DELAY)

    async def async_save_now(self, dataset: Dataset) -> None:
        if self.blocked or self.closed:
            return
        self._dataset = dataset
        await self.async_save(dataset.to_dict())

    def _data_to_save(self) -> dict[str, Any]:
        assert self._dataset is not None
        return self._dataset.to_dict()
