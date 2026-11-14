"""1.0: Rest-Gradtage (Vorhersage, Mehrjahresmittel, Band), Archiv und Prognose gegen Realität, Abschluss, Kündigungsfrist."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from engine.archive import build_archive, close_criteria, forecast_vs_actual
from engine.balance import Balance, MeterResult
from engine.billing import CostBreakdown, Installment, PaymentState, PeriodSpec, notice_deadline
from engine.forecast import expected_degree_days, heat_forecast
from engine.model import BillingRule, Contract, ForecastSnapshot, Invoice, PriceSegment, Reading
from engine.quality import Quality
from engine.regression import HeatModel, ModelQuality

TZ = ZoneInfo("Europe/Berlin")


def _years(levels):
    """Gradtage je Tag für mehrere Vorjahre: levels[y-1] Kd/Tag im Jahr y zurück (2026 = heute)."""
    out = {}
    for y, lvl in enumerate(levels, start=1):
        for i in range(60):
            out[date(2026 - y, 11, 1) + timedelta(days=i)] = lvl
    return out


def test_expected_degree_days_mean_band_and_forecast():
    vals = _years([12.0, 15.0, 9.0])
    days = [date(2026, 11, 13) + timedelta(days=i) for i in range(10)]
    exp, src, totals = expected_degree_days(vals, days)
    assert src == "mittel" and exp[days[0]] == pytest.approx(12.0)  # Mittel aus 12, 15, 9
    assert sorted(totals) == [90.0, 120.0, 150.0]
    fc = {days[0]: 20.0, days[1]: 18.0}
    exp2, src2, _ = expected_degree_days(vals, days, fc)
    assert src2 == "vorhersage+mittel" and exp2[days[0]] == 20.0 and exp2[days[2]] == pytest.approx(12.0)
    one = expected_degree_days(_years([10.0]), days)
    assert one[1] == "vorjahr"
    model = HeatModel(heat_coefficient=5.0, hot_water_baseload=2.0, confidence=ModelQuality.GOOD)
    f = heat_forecast(model, vals, days[0], days[-1], forecast_dd=fc)
    assert f.rest == pytest.approx(5.0 * (20 + 18 + 8 * 12.0) + 2.0 * 10)
    # Band: Vorhersagetage (20 + 18) gelten in jedem Jahr, der Rest aus dem kältesten (15) bzw. wärmsten (9) Jahr
    assert f.details["rest_kalt"] == pytest.approx(5.0 * (38 + 8 * 15.0) + 20) and f.details["rest_warm"] == pytest.approx(5.0 * (38 + 8 * 9.0) + 20)
    assert f.details["rest_warm"] <= f.rest <= f.details["rest_kalt"]
    # sehr kalte Vorhersage: das Band schließt die Prognose trotzdem ein
    cold = heat_forecast(model, vals, days[0], days[-1], forecast_dd={d: 30.0 for d in days[:5]})
    assert cold.details["rest_warm"] <= cold.rest <= cold.details["rest_kalt"]
    assert f.details["vorhersage_tage"] == 2 and f.details["quelle"] == "vorhersage+mittel"


def _result():
    spec = PeriodSpec("c1", date(2025, 1, 1), date(2025, 12, 31), date(2025, 12, 31), False, False)
    res = MeterResult(period=spec, contract=Contract("c1", "m1", "SW", date(2025, 1, 1), BillingRule.CALENDAR_YEAR))
    res.actual = CostBreakdown(energy=900.0, base=100.0, total=1000.0, gross=1000.0)
    res.payments = PaymentState(paid_to_date=1100.0, period_total=1100.0, installments=[Installment(date(2025, 1, 1), 100.0, "gezahlt")])
    res.balance = Balance(actual_cost=1000.0, forecast_cost=1000.0, saldo=100.0, verdict="rueckzahlung")
    res.used_billing = 3000.0
    return res


def test_archive_and_forecast_vs_actual():
    snaps = [ForecastSnapshot("c1-2025-01-01", datetime(2025, 3, 1, tzinfo=TZ), "vorlaeufig", 3100.0, 1100.0, 95.0, saldo=0.0, verdict="passt"),
             ForecastSnapshot("c1-2025-01-01", datetime(2025, 9, 1, tzinfo=TZ), "gut", 3000.0, 990.0, 90.0, saldo=110.0, verdict="rueckzahlung"),
             ForecastSnapshot("p0", datetime(2024, 9, 1, tzinfo=TZ), "gut", 1.0, 1.0)]
    prices = [PriceSegment("c1", date(2025, 1, 1), 0.3, 8.33), PriceSegment("cX", date(2025, 1, 1), 9.0, 9.0)]
    a = build_archive(_result(), snaps, prices, final=True, now=datetime(2026, 1, 5, tzinfo=TZ), reason="endablesung")
    assert a["stand"] == "abgeschlossen" and a["kosten"]["gesamt"] == 1000.0 and a["saldo"] == 100.0 and a["urteil"] == "rueckzahlung"
    assert len(a["prognosen"]) == 2 and len(a["preise"]) == 1
    rows = forecast_vs_actual(a)
    assert rows[0]["abweichung"] == pytest.approx(100.0) and rows[0]["abweichung_pct"] == pytest.approx(10.0)
    assert rows[1]["abweichung"] == pytest.approx(-10.0)


def test_close_criteria():
    end = date(2025, 12, 31)
    reading = Reading("r", "m1", datetime(2026, 1, 3, 9, tzinfo=TZ), 5000.0)
    # im ±10-Tage-Fenster (set_periodenende noch möglich) bleibt es vorläufig, danach endgültig
    assert close_criteria(end, [reading], [], "c1", date(2026, 1, 5), TZ)[:2] == (False, "endablesung")
    assert close_criteria(end, [reading], [], "c1", date(2026, 1, 11), TZ)[:3] == (True, "endablesung", reading)
    # eine Ablesung vor dem Ende schließt nicht ab (Verbrauch bis zum Ende fehlt)
    early = Reading("r0", "m1", datetime(2025, 12, 25, 9, tzinfo=TZ), 4900.0)
    assert close_criteria(end, [early], [], "c1", date(2026, 1, 20), TZ)[:2] == (False, "wartet_auf_endablesung")
    far = Reading("r2", "m1", datetime(2026, 2, 1, tzinfo=TZ), 5100.0)
    est = Reading("r3", "m1", datetime(2026, 1, 1, tzinfo=TZ), 5000.0, Quality.ESTIMATED)
    assert close_criteria(end, [far, est], [], "c1", date(2026, 1, 20), TZ)[:2] == (False, "wartet_auf_endablesung")
    inv = Invoice("i1", "c1", date(2026, 1, 20), date(2025, 1, 1), date(2025, 12, 31), 1000.0)
    assert close_criteria(end, [], [inv], "c1", date(2026, 1, 21), TZ)[:2] == (True, "rechnung")
    assert close_criteria(end, [], [], "c1", date(2026, 3, 1), TZ)[:2] == (True, "frist_60_tage")


def test_forecast_vs_actual_incomplete_costs():
    res = _result()
    res.actual.flags.append("kein_preis")
    snaps = [ForecastSnapshot("c1-2025-01-01", datetime(2025, 3, 1, tzinfo=TZ), "gut", 3100.0, 1100.0)]
    a = build_archive(res, snaps, [], final=True, now=datetime(2026, 1, 5, tzinfo=TZ), reason="frist_60_tage")
    assert "abweichung" not in a["prognose_gegen_realitaet"][0]
    b = build_archive(_result(), snaps, [], final=True, now=datetime(2026, 1, 5, tzinfo=TZ), reason="frist_60_tage", values_until=date(2025, 12, 20))
    assert b["tageswerte_bis"] == "2025-12-20" and "abweichung" not in b["prognose_gegen_realitaet"][0]


def test_notice_deadline():
    c = Contract("c1", "m1", "SW", date(2025, 7, 1), BillingRule.CONTRACT_YEAR, min_term_months=24, notice_period_weeks=6)
    deadline, end, kind = notice_deadline(c, date(2026, 11, 14))
    assert end == date(2027, 6, 30) and deadline == date(2027, 6, 30) - timedelta(weeks=6) and kind == "termin"
    assert notice_deadline(c, date(2027, 8, 1))[2] == "nach_mindestlaufzeit"
    fixed = Contract("c2", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR, end_date=date(2026, 12, 31), notice_period_weeks=4)
    assert notice_deadline(fixed, date(2026, 11, 14))[0] == date(2026, 12, 3)
    assert notice_deadline(Contract("c3", "m1", "SW", date(2026, 1, 1), BillingRule.CALENDAR_YEAR), date(2026, 11, 14))[2] == "keine_angaben"
    # Monatsende (§ 188 BGB): Beginn 31.01., 1 Monat → Ende 28.02.
    eom = Contract("c4", "m1", "SW", date(2027, 1, 31), BillingRule.CALENDAR_YEAR, min_term_months=1, notice_period_weeks=1)
    assert notice_deadline(eom, date(2027, 2, 1))[1] == date(2027, 2, 28)
