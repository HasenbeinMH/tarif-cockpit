"""Abrechnungsperioden und Vertragskette."""

from __future__ import annotations

from datetime import date

import pytest

from engine.billing import (
    BillingError,
    add_follow_up,
    contract_on,
    current_period,
    generate_periods,
    parse_fixed_day,
    period_status,
    periods_for_chain,
    validate_chain,
)
from engine.model import BillingRule, Contract, PeriodSpan, PeriodStatus


def mk(rule, start, end=None, fixed=None, cid="c1", manual=None, supplier="A"):
    return Contract(
        contract_id=cid, meter_id="m1", supplier=supplier, start_date=start, end_date=end,
        billing_rule=rule, fixed_day=fixed, manual_periods=manual or [],
    )


def spans(ps):
    return [(p.start_date, p.end_date, p.is_partial, p.is_final) for p in ps]


def test_contract_year():
    ps = generate_periods(mk(BillingRule.CONTRACT_YEAR, date(2026, 3, 15)), date(2027, 6, 1))
    assert spans(ps) == [
        (date(2026, 3, 15), date(2027, 3, 14), False, False),
        (date(2027, 3, 15), date(2028, 3, 14), False, False),
    ]


def test_calendar_year_rumpfjahr():
    ps = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2026, 3, 15)), date(2027, 2, 1))
    assert spans(ps) == [
        (date(2026, 3, 15), date(2026, 12, 31), True, False),
        (date(2027, 1, 1), date(2027, 12, 31), False, False),
    ]


def test_calendar_year_starting_jan_first_is_not_partial():
    ps = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 1)), date(2026, 5, 1))
    assert spans(ps) == [(date(2026, 1, 1), date(2026, 12, 31), False, False)]


def test_fixed_day_first_period_until_next_stichtag():
    ps = generate_periods(mk(BillingRule.FIXED_DAY, date(2026, 3, 15), fixed="30.06."), date(2026, 8, 1))
    assert spans(ps) == [
        (date(2026, 3, 15), date(2026, 6, 29), True, False),
        (date(2026, 6, 30), date(2027, 6, 29), False, False),
    ]


def test_fixed_day_on_stichtag_is_full_year():
    ps = generate_periods(mk(BillingRule.FIXED_DAY, date(2026, 7, 30), fixed="30.07"), date(2026, 11, 13))
    assert spans(ps) == [(date(2026, 7, 30), date(2027, 7, 29), False, False)]


@pytest.mark.parametrize("bad", ["31.02", "29.02.", "1.13", "", None, "abc"])
def test_fixed_day_invalid(bad):
    with pytest.raises(BillingError):
        parse_fixed_day(bad)


def test_manual_periods():
    c = mk(BillingRule.MANUAL, date(2026, 1, 10), manual=[PeriodSpan(date(2026, 1, 10), date(2026, 9, 30)), PeriodSpan(date(2026, 10, 1), date(2027, 9, 30))])
    assert spans(generate_periods(c, date(2026, 12, 1))) == [
        (date(2026, 1, 10), date(2026, 9, 30), False, False),
        (date(2026, 10, 1), date(2027, 9, 30), False, False),
    ]


def test_manual_gap_is_error():
    c = mk(BillingRule.MANUAL, date(2026, 1, 1), manual=[PeriodSpan(date(2026, 1, 1), date(2026, 6, 30)), PeriodSpan(date(2026, 7, 5), date(2026, 12, 31))])
    with pytest.raises(BillingError):
        generate_periods(c, date(2026, 12, 1))


def test_leap_year_start():
    ps = generate_periods(mk(BillingRule.CONTRACT_YEAR, date(2028, 2, 29)), date(2029, 6, 1))
    assert ps[0].end_date == date(2029, 2, 28)
    assert ps[1].start_date == date(2029, 3, 1)


def test_leap_day_inside_period_counts():
    ps = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2028, 1, 1)), date(2028, 2, 29))
    assert ps[0].contains(date(2028, 2, 29))


def test_actual_reading_shifts_only_this_end():
    c = mk(BillingRule.CONTRACT_YEAR, date(2026, 3, 15))
    ps = generate_periods(c, date(2028, 6, 1), {date(2027, 3, 14): date(2027, 3, 18)})
    assert spans(ps)[:3] == [
        (date(2026, 3, 15), date(2027, 3, 18), False, False),
        (date(2027, 3, 19), date(2028, 3, 14), False, False),
        (date(2028, 3, 15), date(2029, 3, 14), False, False),
    ]


def test_actual_reading_shift_too_large():
    with pytest.raises(BillingError):
        generate_periods(mk(BillingRule.CONTRACT_YEAR, date(2026, 3, 15)), date(2027, 6, 1), {date(2027, 3, 14): date(2027, 4, 14)})


def test_contract_end_gives_final_partial_period():
    ps = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2025, 1, 1), end=date(2026, 8, 31)), date(2026, 11, 1))
    assert spans(ps) == [
        (date(2025, 1, 1), date(2025, 12, 31), False, False),
        (date(2026, 1, 1), date(2026, 8, 31), True, True),
    ]


def test_contract_end_on_regular_end_is_final_not_partial():
    ps = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2025, 1, 1), end=date(2025, 12, 31)), date(2026, 3, 1))
    assert spans(ps) == [(date(2025, 1, 1), date(2025, 12, 31), False, True)]


def test_long_contract_does_not_invent_final_period():
    ps = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2020, 1, 1), end=date(2030, 6, 30)), date(2026, 5, 1))
    assert ps[-1].start_date == date(2026, 1, 1) and ps[-1].end_date == date(2026, 12, 31)
    assert not ps[-1].is_final


def test_follow_up_contract_and_chain():
    old = mk(BillingRule.CALENDAR_YEAR, date(2025, 1, 1), cid="old", supplier="Alt")
    new = mk(BillingRule.CONTRACT_YEAR, date(2026, 9, 1), cid="new", supplier="Neu")
    changed, created = add_follow_up([old], new)
    assert changed.end_date == date(2026, 8, 31)
    assert old.end_date is None  # Original unverändert (Regel 3)
    chain = [changed, created]
    assert validate_chain(chain) == []
    ps = periods_for_chain(chain, date(2026, 12, 1))
    assert spans(ps) == [
        (date(2025, 1, 1), date(2025, 12, 31), False, False),
        (date(2026, 1, 1), date(2026, 8, 31), True, True),
        (date(2026, 9, 1), date(2027, 8, 31), False, False),
    ]
    assert contract_on(chain, date(2026, 8, 31)).contract_id == "old"
    assert contract_on(chain, date(2026, 9, 1)).contract_id == "new"
    assert current_period(chain, date(2026, 10, 1)).start_date == date(2026, 9, 1)


def test_follow_up_before_current_start_is_error():
    old = mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 1), cid="old")
    with pytest.raises(BillingError):
        add_follow_up([old], mk(BillingRule.CALENDAR_YEAR, date(2025, 12, 1), cid="new"))


def test_chain_gap_and_overlap():
    a = mk(BillingRule.CALENDAR_YEAR, date(2025, 1, 1), end=date(2025, 12, 31), cid="a", supplier="A")
    b = mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 5), cid="b", supplier="B")
    assert "Lücke" in validate_chain([a, b])[0]
    c = mk(BillingRule.CALENDAR_YEAR, date(2025, 12, 1), cid="c", supplier="C")
    assert "Überschneidung" in validate_chain([a, c])[0]


def test_period_status():
    p = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 1)), date(2026, 5, 1))[0]
    assert period_status(p, date(2026, 5, 1), False) == PeriodStatus.OPEN
    assert period_status(p, date(2027, 1, 3), False) == PeriodStatus.CLOSING
    assert period_status(p, date(2027, 1, 3), True) == PeriodStatus.CLOSED


def test_period_id_is_stable():
    c = mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 1))
    a = generate_periods(c, date(2026, 5, 1))[0].period_id
    b = generate_periods(c, date(2027, 5, 1))[0].period_id
    assert a == b == "c1-2026-01-01"


def test_follow_up_must_not_touch_ended_period():
    from engine.billing import check_not_in_ended_period
    from engine.model import BillingPeriod

    ended = [BillingPeriod("c1-2025-01-01", "c1", date(2025, 1, 1), date(2025, 12, 31))]
    with pytest.raises(BillingError):
        check_not_in_ended_period(date(2025, 4, 1), ended)
    check_not_in_ended_period(date(2026, 1, 1), ended)


def test_append_manual_period():
    from engine.billing import append_manual_period

    c = mk(BillingRule.MANUAL, date(2026, 1, 10), manual=[PeriodSpan(date(2026, 1, 10), date(2026, 9, 30))])
    c2 = append_manual_period(c, date(2027, 9, 30), date(2026, 12, 1))
    assert spans(generate_periods(c2, date(2027, 1, 1)))[-1] == (date(2026, 10, 1), date(2027, 9, 30), False, False)
    with pytest.raises(BillingError):
        append_manual_period(c, date(2026, 9, 1), date(2026, 12, 1))
    with pytest.raises(BillingError):
        append_manual_period(mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 1)), date(2026, 12, 31), date(2026, 12, 1))


def test_shifted_end_limits():
    from engine.billing import shifted_end

    spec = generate_periods(mk(BillingRule.CALENDAR_YEAR, date(2026, 1, 1)), date(2026, 5, 1))[0]
    assert shifted_end(spec, date(2027, 1, 5)) == date(2027, 1, 5)
    with pytest.raises(BillingError):
        shifted_end(spec, date(2027, 2, 1))
