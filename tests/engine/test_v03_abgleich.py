"""Abnahme P3: Zahlen = bisherige Template-Sensoren aus 0.3 (±1 %).

Grundlage sind Daniels Werte vom 13.11.2026 (aus seinem HA gelesen): Helfer, Zählerstände, Tarife, Vorjahreswerte der
Automation und die Ergebnisse der Template-Sensoren. Abrechnungsbeginn laut Helfer: 30.06.2026.
Gas: Die Templates rechnen mit der Kennwert-Annahme 6,5. Die Integration nutzt keine Annahme, sondern einen gelernten
Kennwert; für den Abgleich wird der Kennwert 6,5 deshalb als Modell eingesetzt.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.balance import evaluate_meter
from engine.model import (
    AdvancePlan, AdvanceStep, BillingRule, Contract, Conversion, DailyConsumption, Medium, Meter, PriceSegment, Reading,
)
from engine.quality import Quality
from engine.regression import HeatModel, ModelQuality

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 11, 13, 18, 0, tzinfo=TZ)  # Zeitpunkt, zu dem die Template-Werte gelesen wurden (Kosten passen dazu)
START = date(2026, 6, 30)

# Template-Ergebnisse 0.3
SOLL = {
    "strom": {"kosten_bisher": 374.49, "abschlaege_bisher": 825.0, "prognose_verbrauch": 3532, "prognose_kosten": 1271.07,
              "abschlag_passend": 106, "differenz": 708.93, "urteil": "rueckzahlung"},
    "gas": {"kosten_bisher": 223.49, "abschlaege_bisher": 830.0, "prognose_verbrauch": 16206, "prognose_kosten": 1771.29,
            "abschlag_passend": 148, "differenz": 220.71, "urteil": "rueckzahlung"},
}


def _prev_year_daily(meter_id: str, so_far: float, rest: float, field: str) -> dict[date, DailyConsumption]:
    """Vorjahr: bisheriges Fenster (30.06.2025–12.11.2025) und Restfenster (13.11.2025–29.06.2026) gleichmäßig verteilt."""
    out = {}
    a0, a1, b0, b1 = date(2025, 6, 30), date(2025, 11, 12), date(2025, 11, 13), date(2026, 6, 29)
    na, nb = (a1 - a0).days + 1, (b1 - b0).days + 1
    for i in range(na):
        d = a0 + timedelta(days=i)
        out[d] = DailyConsumption(meter_id, d, **{field: so_far / na}, quality=Quality.REAL)
    for i in range(nb):
        d = b0 + timedelta(days=i)
        out[d] = DailyConsumption(meter_id, d, **{field: rest / nb}, quality=Quality.REAL)
    return out


def _common(meter_id: str, ap: float, gp: float, advance: float):
    contract = Contract("c-" + meter_id, meter_id, "Stadtwerke", START, BillingRule.FIXED_DAY, fixed_day="30.06")
    prices = [PriceSegment(contract.contract_id, START, ap, gp)]
    plan = AdvancePlan(contract.contract_id, [AdvanceStep(START, advance)], pay_day=1)
    return contract, prices, plan


def _check(name: str, res) -> dict:
    ist = {
        "kosten_bisher": res.balance.actual_cost,
        "abschlaege_bisher": res.payments.paid_to_date,
        "prognose_verbrauch": res.forecast_total,
        "prognose_kosten": res.balance.forecast_cost,
        "abschlag_passend": res.balance.fitting_advance,
        "differenz": res.balance.saldo,
        "urteil": res.balance.verdict,
    }
    for key, soll in SOLL[name].items():
        if isinstance(soll, str):
            assert ist[key] == soll, (name, key, ist[key])
        else:
            assert ist[key] == pytest.approx(soll, rel=0.01), (name, key, ist[key], soll)
    return ist


def test_strom_matches_templates():
    meter = Meter("strom", Medium.STROM, "kWh", entity="sensor.zaehler_strom", data_level=2)
    contract, prices, plan = _common("strom", 0.3154, 13.09, 165.0)
    readings = [Reading("r0", "strom", datetime(2026, 6, 30, 0, 0, tzinfo=TZ), 5645.0)]
    daily = _prev_year_daily("strom", 926.0, 2432.6, "consumption")
    res = evaluate_meter(meter, [contract], prices, [plan], [], readings, daily, NOW, TZ, (NOW, 6645.9))
    ist = _check("strom", res)
    assert res.forecast.method == "vorjahr"
    print("Strom", ist)


def test_gas_matches_templates_with_same_coefficient():
    meter = Meter("gas", Medium.GAS, "m³", entity="sensor.zaehler_gas", data_level=2, conversion=Conversion(11.318, 0.9624))
    contract, prices, plan = _common("gas", 0.0952, 19.04, 166.0)
    readings = [Reading("r0", "gas", datetime(2026, 6, 30, 0, 0, tzinfo=TZ), 9675.0)]
    daily = _prev_year_daily("gas", 0.0, 2270.3, "degree_days")
    model = HeatModel(heat_coefficient=6.5, hot_water_baseload=0.0, confidence=ModelQuality.PRELIMINARY)
    res = evaluate_meter(meter, [contract], prices, [plan], [], readings, daily, NOW, TZ, (NOW, 9808.0), heat_model_override=model)
    ist = _check("gas", res)
    print("Gas", ist)


def test_gas_without_learned_coefficient_has_no_forecast():
    meter = Meter("gas", Medium.GAS, "m³", entity="sensor.zaehler_gas", data_level=2, conversion=Conversion(11.318, 0.9624))
    contract, prices, plan = _common("gas", 0.0952, 19.04, 166.0)
    readings = [Reading("r0", "gas", datetime(2026, 6, 30, 0, 0, tzinfo=TZ), 9675.0)]
    res = evaluate_meter(meter, [contract], prices, [plan], [], readings, {}, NOW, TZ, (NOW, 9808.0))
    assert res.heat_model.confidence == ModelQuality.INSUFFICIENT
    assert res.forecast_total is None and res.balance.forecast_cost is None and res.balance.verdict is None
    assert res.balance.actual_cost == pytest.approx(223.49, rel=0.01)  # Kosten bisher gibt es trotzdem
