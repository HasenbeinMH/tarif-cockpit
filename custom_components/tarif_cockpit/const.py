"""Konstanten der Integration Tarif-Cockpit."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "tarif_cockpit"
VERSION: Final = "0.8.0"

SUBENTRY_METER: Final = "zaehler"
SUBENTRY_GENERATOR: Final = "waermeerzeuger"

# Config Entry
CONF_HOUSEHOLD: Final = "household"
CONF_STORE_CREATED: Final = "store_created"
# Subentry Zähler
CONF_METER: Final = "meter"
CONF_INITIAL_CONTRACT: Final = "initial_contract"
CONF_INITIAL_READING: Final = "initial_reading"
CONF_INITIAL_PRICE: Final = "initial_price"
CONF_INITIAL_PLAN: Final = "initial_plan"
# Subentry Wärmeerzeuger
CONF_GENERATOR: Final = "generator"

# Store
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 3
STORAGE_SAVE_DELAY: Final = 10

# Frontend
URL_BASE: Final = "/tarif_cockpit"
CARD_FILE: Final = "tarif-cockpit.js"
OLD_RESOURCE_PREFIX: Final = "/hacsfiles/tarif-cockpit/"

# Tagesaggregation
AGG_HOUR: Final = 0
AGG_MINUTE: Final = 5
BACKFILL_DAYS: Final = 400  # höchstens so weit zurück
RETRY_MISSING_DAYS: Final = 7  # fehlende Tage so lange erneut versuchen

# Reparatur-Hinweise
ISSUE_STORE_LOST: Final = "store_verloren"
ISSUE_STORE_INVALID: Final = "store_ungueltig"
ISSUE_STORE_TOO_NEW: Final = "store_zu_neu"
ISSUE_OLD_RESOURCE: Final = "alte_dashboard_installation"
ISSUE_NO_STATISTICS: Final = "zaehler_ohne_statistik"


def signal_updated(entry_id: str) -> str:
    """Dispatcher-Signal: Daten eines Eintrags haben sich geändert."""
    return f"{DOMAIN}_{entry_id}_updated"
