from __future__ import annotations

import pandas as pd

from expense_tracker.import_export import prepare_import_dataframe


def test_prepare_import_dataframe_accepts_raw_csv_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "Date": "invalid date",
                "Description": "cafe ",
                "Envelope": "Eating out ",
                "Amount": "12.50",
                "Type (Income/Expense)": "Expense",
                "Month": "April",
                "Signed Amount": "-12.50",
                "Cumulative": "12.50",
                "Slope": "4.6",
                "ParsedDate": "4/1/2026",
            },
            {
                "Date": "",
                "Description": "",
                "Envelope": "",
                "Amount": "",
                "Type (Income/Expense)": "",
                "Month": "April total",
                "Signed Amount": "-12.50",
                "Cumulative": "",
                "Slope": "",
                "ParsedDate": "",
            },
        ]
    )

    cleaned = prepare_import_dataframe(frame)

    assert len(cleaned) == 1
    row = cleaned.iloc[0]
    assert row["description"] == "Example Cafe"
    assert row["category"] == "Eating out"
    assert row["month"] == "April"
    assert row["parsed_date"] == "2026-04-01"
    assert row["signed_amount"] == -12.50
