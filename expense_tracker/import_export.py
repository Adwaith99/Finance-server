from __future__ import annotations

from io import BytesIO, StringIO
from typing import Any

import pandas as pd

from expense_tracker.calculations import add_derived_columns, normalize_text

REQUIRED_COLUMNS = ["date", "description", "category", "amount", "type"]
OPTIONAL_CALCULATED_COLUMNS = [
    "month",
    "signed_amount",
    "running_month_total",
    "display_amount",
    "parsed_date",
]
CANONICAL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_CALCULATED_COLUMNS
COLUMN_ALIASES = {
    "date": "date",
    "description": "description",
    "merchant": "description",
    "merchantdescription": "description",
    "envelope": "category",
    "category": "category",
    "amount": "amount",
    "type": "type",
    "typeincomeexpense": "type",
    "month": "month",
    "signedamount": "signed_amount",
    "signed_amount": "signed_amount",
    "cumulative": "running_month_total",
    "runningmonthtotal": "running_month_total",
    "running_month_total": "running_month_total",
    "displayamount": "display_amount",
    "display_amount": "display_amount",
    "parseddate": "parsed_date",
    "parsed_date": "parsed_date",
}


def normalize_column_name(value: Any) -> str:
    return normalize_text(value).replace(" ", "")


def rename_import_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    for column in frame.columns:
        canonical_name = COLUMN_ALIASES.get(normalize_column_name(column))
        if canonical_name:
            rename_map[column] = canonical_name
    return frame.rename(columns=rename_map)


def _prepare_optional_columns(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    for column in CANONICAL_COLUMNS:
        if column not in prepared.columns:
            prepared[column] = pd.NA
    return prepared[CANONICAL_COLUMNS]


def _drop_empty_rows(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    for column in ["date", "description", "category", "amount", "type", "parsed_date"]:
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("string").str.strip()
            prepared[column] = prepared[column].replace(
                {"": pd.NA, "nan": pd.NA, "None": pd.NA}
            )
    required_mask = (
        prepared["description"].notna()
        & prepared["category"].notna()
        & prepared["amount"].notna()
        & prepared["type"].notna()
    )
    date_mask = prepared["date"].notna() | prepared["parsed_date"].notna()
    return prepared.loc[required_mask & date_mask].copy()


def read_transactions_csv(source: Any) -> pd.DataFrame:
    return pd.read_csv(source)


def prepare_import_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = rename_import_columns(frame)
    cleaned = _prepare_optional_columns(cleaned)
    cleaned = _drop_empty_rows(cleaned)
    cleaned = add_derived_columns(cleaned)
    cleaned = cleaned.loc[cleaned["parsed_date"].notna()].copy()
    return cleaned.reset_index(drop=True)


def import_csv_bytes(csv_bytes: bytes) -> pd.DataFrame:
    return prepare_import_dataframe(pd.read_csv(BytesIO(csv_bytes)))


def export_transactions_csv(frame: pd.DataFrame) -> str:
    export_frame = frame.copy()
    if not export_frame.empty and "parsed_date" in export_frame.columns:
        export_frame["parsed_date"] = pd.to_datetime(
            export_frame["parsed_date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    buffer = StringIO()
    export_frame.to_csv(buffer, index=False)
    return buffer.getvalue()
