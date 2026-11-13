"""Engine-Tests laufen ohne Home Assistant: das Paket engine wird direkt importiert."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
# engine als eigenständiges Paket importierbar machen (ohne custom_components/tarif_cockpit/__init__.py, das HA braucht)
sys.path.insert(0, str(ROOT / "custom_components" / "tarif_cockpit"))

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def fixture_data():
    def load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return load
