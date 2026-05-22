from __future__ import annotations

import pandas as pd

from expense_tracker.calculations import (
    month_name_from_date,
    signed_amount,
    spending_total_for_range,
    suggest_category_from_history,
    week_options,
    week_bounds,
)


def test_signed_amount_expense_is_negative() -> None:
    assert signed_amount(12.5, "Expense") == -12.5


def test_signed_amount_income_is_positive() -> None:
    assert signed_amount(12.5, "Income") == 12.5


def test_month_name_is_parsed_correctly() -> None:
    assert month_name_from_date("23/4/2026") == "April"


def test_weekly_totals_are_calculated_correctly() -> None:
    frame = pd.DataFrame(
        {
            "parsed_date": ["2026-04-21", "2026-04-22", "2026-04-28"],
            "type": ["Expense", "Expense", "Expense"],
            "display_amount": [10.0, 15.0, 20.0],
        }
    )
    start, end = week_bounds("2026-04-21")
    total = spending_total_for_range(frame, start, end)
    assert total == 25.0


def test_week_bounds_start_on_sunday() -> None:
    start, end = week_bounds("2026-04-21")
    assert start.strftime("%Y-%m-%d") == "2026-04-19"
    assert end.strftime("%Y-%m-%d") == "2026-04-25"


def test_week_options_start_on_sunday() -> None:
    frame = pd.DataFrame(
        {
            "parsed_date": ["2026-04-21", "2026-04-27"],
            "type": ["Expense", "Expense"],
            "display_amount": [10.0, 15.0],
        }
    )
    assert week_options(frame) == ["2026-04-19", "2026-04-26"]


def test_merchant_category_suggestion_works() -> None:
    mapping = {"dominos": "Eating out", "metro": "Groceries"}
    assert suggest_category_from_history("Dominos", mapping) == "Eating out"
    assert suggest_category_from_history("Metro", mapping) == "Groceries"
