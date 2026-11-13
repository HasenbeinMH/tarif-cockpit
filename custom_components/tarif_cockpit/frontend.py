"""Karten ausliefern: statischer Pfad und Laden im Frontend, gekapselt (Arbeitspaket 1).

Die Karten werden über ``add_extra_js_url`` geladen, also ohne Eintrag unter Dashboard-Ressourcen.
Gibt es noch die frühere Dashboard-Installation (``/hacsfiles/tarif-cockpit/``), erscheint ein Reparatur-Hinweis,
denn beide Dateien würden dieselben Karten definieren (es gewinnt die zuerst geladene).
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CARD_FILE, DOMAIN, ISSUE_OLD_RESOURCE, OLD_RESOURCE_PREFIX, URL_BASE, VERSION

_LOGGER = logging.getLogger(__name__)
DATA_FRONTEND = f"{DOMAIN}_frontend"
CARD_URL = f"{URL_BASE}/{CARD_FILE}?v={VERSION}"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Einmal je Home Assistant: Pfad registrieren und Karten laden."""
    if hass.data.get(DATA_FRONTEND):
        return
    path = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([StaticPathConfig(URL_BASE, str(path), cache_headers=False)])
    hass.data[DATA_FRONTEND] = True
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

        add_extra_js_url(hass, CARD_URL)
    else:
        _LOGGER.debug("Tarif-Cockpit: Frontend nicht geladen, Karten werden nicht eingebunden")
    await async_check_old_resource(hass)


async def async_check_old_resource(hass: HomeAssistant) -> bool:
    """Reparatur-Hinweis, wenn die Karte noch als Dashboard-Ressource aus der früheren Installation geladen wird."""
    found = False
    if "lovelace" in hass.config.components:
        try:
            from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: PLC0415

            resources = hass.data[LOVELACE_DATA].resources
            if hasattr(resources, "async_get_info"):
                await resources.async_get_info()
            found = any(str(item.get("url", "")).startswith(OLD_RESOURCE_PREFIX) for item in resources.async_items())
        except Exception as err:  # noqa: BLE001 - interne API, darf die Einrichtung nie stören
            _LOGGER.debug("Tarif-Cockpit: Dashboard-Ressourcen nicht lesbar: %s", err)
    if found:
        ir.async_create_issue(
            hass, DOMAIN, ISSUE_OLD_RESOURCE, is_fixable=False, severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_OLD_RESOURCE, learn_more_url="https://github.com/HasenbeinMH/tarif-cockpit/blob/main/docs/MIGRATION.md",
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_OLD_RESOURCE)
    return found
