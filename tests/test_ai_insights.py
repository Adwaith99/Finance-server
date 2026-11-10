import json
from datetime import date

import pandas as pd
import pytest

from expense_tracker.ai_insights import build_prompt, build_summary, percentage_change


def transactions(rows):
    return pd.DataFrame(rows, columns=["parsed_date", "category", "display_amount", "type", "description"])


def example():
    return transactions([
        ("2026-01-05", "Groceries", 400, "Expense", "Market"),
        ("2026-01-10", "Restaurants", 650, "Expense", "Cafe"),
        ("2026-02-05", "Groceries", 450, "Expense", "Market"),
        ("2026-02-10", "Restaurants", 520, "Expense", "Cafe"),
        ("2026-02-10", "Salary", 2000, "Income", "Employer"),
    ])


def summary(frame=None, period="Last 3 months", today=date(2026, 3, 20)):
    return build_summary(example() if frame is None else frame, period, today)


def test_authoritative_calculations_and_income_separation():
    result = summary()
    assert result["expense_total"] == 2020
    assert result["income"] == 2000
    assert result["net_cash_flow"] == -20
    assert result["average_recorded_month"] == 1010
    assert result["expense_count"] == 4
    assert result["transaction_count"] == 5
    latest = result["months"][-1]
    assert latest["expense_total"] == 970
    assert latest["vs_previous"] == {"change": -80, "change_pct": -7.62}
    assert latest["category_changes"]["Groceries"]["change_pct"] == 12.5
    assert latest["category_changes"]["Restaurants"]["change_pct"] == -20
    assert result["categories"][0] == {"name": "Restaurants", "amount": 1170, "count": 2, "share_pct": 57.92}
    assert result["merchants"][0]["name"] == "Cafe"
    assert "Salary" not in latest["categories"]
    prompt = build_prompt(result)
    assert '"change_pct":12.5' in prompt
    assert '"change_pct":-20.0' in prompt
    assert '"change_pct":-7.62' in prompt


def test_date_selection_and_no_comparison_outside_selection():
    result = summary(period="Latest available month")
    assert result["start"] == "2026-02-01"
    assert result["end"] == "2026-02-28"
    assert result["first_record"] == "2026-02-05"
    assert result["expense_total"] == 970
    assert result["months"][-1]["vs_previous"] is None
    assert "2026-01" not in build_prompt(result)


def test_partial_current_month_and_future_dates():
    result = summary(today=date(2026, 2, 7))
    assert result["end"] == "2026-02-07"
    assert result["expense_total"] == 1500
    assert result["months"][-1]["partial"]
    assert result["months"][-1]["vs_previous"] is None


def test_missing_month_not_zero_and_not_compared():
    frame = transactions([("2026-01-01", "A", 10, "Expense", "M"),
                          ("2026-03-01", "A", 20, "Expense", "M")])
    result = summary(frame, today=date(2026, 4, 1))
    assert result["months"][1]["expense_total"] is None
    assert result["months"][-1]["vs_previous"] is None
    assert result["average_recorded_month"] == 15


def test_zero_records_differ_from_missing_records():
    frame = transactions([("2026-01-01", "A", 0, "Expense", "M"),
                          ("2026-02-01", "A", 10, "Expense", "M")])
    result = summary(frame)
    assert result["months"][-2]["expense_total"] == 0
    assert result["months"][-1]["vs_previous"] == {"change": 10, "change_pct": None}
    assert percentage_change(0, 10) == {"change": -10, "change_pct": -100}


def test_empty_income_only_and_invalid_data():
    for frame in (pd.DataFrame(), transactions([("bad", "A", 10, "Expense", "M")]),
                  transactions([("2026-01-01", "A", float("inf"), "Expense", "M")])):
        result = summary(frame)
        assert result["expense_total"] is None
        assert result["transaction_count"] == 0
        assert build_prompt(result)
    result = summary(transactions([("2026-01-01", "Salary", 100, "Income", "M")]))
    assert result["expense_total"] is None
    assert result["net_cash_flow"] is None
    assert result["income"] == 100


def test_stable_bounded_prompt_and_no_mutation():
    frame = transactions([(f"2025-{month:02d}-01", "測試" * 100 + str(i), i, "Expense", "Merchant" * 100)
                          for month in range(1, 13) for i in range(30)])
    original = frame.copy(deep=True)
    result = summary(frame, "All available history")
    prompt = build_prompt(result)
    assert len(prompt.encode("utf-8")) <= 4200
    assert prompt == build_prompt(summary(frame.sample(frac=1, random_state=2), "All available history"))
    stats = json.loads(prompt.split("\nSTATS=")[1].split("\nQUESTION=")[0])
    assert stats["expense_total"] == result["expense_total"]
    pd.testing.assert_frame_equal(frame, original)
    assert len(result["categories"]) == 30
    with pytest.raises(ValueError):
        build_prompt(result, "x" * 401)


@pytest.mark.parametrize("label,start", [("Last 3 months", "2025-12-01"), ("Last 6 months", "2025-09-01"),
                                          ("Last 12 months", "2025-03-01"), ("All available history", "2026-01-01")])
def test_range_options(label, start):
    assert summary(period=label)["start"] == start
