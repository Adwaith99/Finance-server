from __future__ import annotations

import pandas as pd

from expense_tracker.import_export import prepare_import_dataframe


def test_prepare_import_dataframe_accepts_raw_csv_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "Date": "invalid date",
                "Description": "Dominos dinner ",
                "Envelope": "Eating out ",
                "Amount": "23.19",
                "Type (Income/Expense)": "Expense",
                "Month": "July",
                "Signed Amount": "-23.19",
                "Cumulative": "23.19",
                "Slope": "4.6",
                "ParsedDate": "7/28/2025",
            },
            {
                "Date": "",
                "Description": "",
                "Envelope": "",
                "Amount": "",
                "Type (Income/Expense)": "",
                "Month": "July total",
                "Signed Amount": "-23.19",
                "Cumulative": "",
                "Slope": "",
                "ParsedDate": "",
            },
        ]
    )

    cleaned = prepare_import_dataframe(frame)

    assert len(cleaned) == 1
    row = cleaned.iloc[0]
    assert row["description"] == "Dominos dinner"
    assert row["category"] == "Eating out"
    assert row["month"] == "July"
    assert row["parsed_date"] == "2025-07-28"
    assert row["signed_amount"] == -23.19
