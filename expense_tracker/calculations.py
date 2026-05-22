from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

import pandas as pd

KNOWN_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%m/%d/%y",
)

DEFAULT_CATEGORIES = [
    "Eating out",
    "Groceries",
    "Transport",
    "Bills",
    "Shopping",
    "Entertainment",
    "Health",
    "Other",
]

TRANSACTION_TYPES = ["Expense", "Income"]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date_value(value: Any) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return pd.to_datetime(value, errors="coerce")
    if not isinstance(value, str):
        return pd.to_datetime(value, errors="coerce")

    text = str(value).strip()
    if not text:
        return pd.NaT

    # Try YYYY-MM-DD format first (already-parsed dates)
    parsed = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
    if not pd.isna(parsed):
        return parsed

    # Then try DD/MM/YYYY format with 4-digit year
    parsed = pd.to_datetime(text, format="%d/%m/%Y", errors="coerce")
    if not pd.isna(parsed):
        # Fix obvious year typos
        if parsed.year == 2024:
            parsed = parsed.replace(year=2025)
        elif parsed.year == 2826:
            parsed = parsed.replace(year=2026)
        return parsed

    # Try DD/MM/YY format with 2-digit year
    parsed = pd.to_datetime(text, format="%d/%m/%y", errors="coerce")
    if not pd.isna(parsed):
        return parsed

    # Fallback to automatic parsing with dayfirst=True
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if not pd.isna(parsed):
        if parsed.year == 2024:
            parsed = parsed.replace(year=2025)
        elif parsed.year == 2826:
            parsed = parsed.replace(year=2026)

    return parsed


def month_name_from_date(value: Any) -> str:
    parsed = parse_date_value(value)
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%B")


def signed_amount(amount: Any, transaction_type: Any) -> float:
    numeric_amount = float(amount or 0)
    normalized_type = normalize_text(transaction_type)
    if normalized_type == "income":
        return abs(numeric_amount)
    return -abs(numeric_amount)


def display_amount(amount: Any) -> float:
    return abs(float(amount or 0))


def calculate_running_month_total(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    month_keys = frame["parsed_date"].dt.to_period("M")
    totals = []
    for _, group in frame.groupby(month_keys, sort=False):
        running = group["display_amount"].cumsum()
        totals.extend(running.tolist())
    return pd.Series(totals, index=frame.index, dtype=float)


def add_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    if data.empty:
        return data

    if "date" not in data.columns:
        raise ValueError("Input data must include a date column.")
    if "description" not in data.columns:
        raise ValueError("Input data must include a description column.")
    if "category" not in data.columns:
        raise ValueError("Input data must include a category column.")
    if "amount" not in data.columns:
        raise ValueError("Input data must include an amount column.")
    if "type" not in data.columns:
        raise ValueError("Input data must include a type column.")

    data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
    data["type"] = (
        data["type"]
        .astype(str)
        .str.strip()
        .str.title()
        .replace({"Expense": "Expense", "Income": "Income"})
    )

    parsed_from_date = data["date"].map(parse_date_value)
    if "parsed_date" in data.columns:
        parsed_from_parsed_date = data["parsed_date"].map(parse_date_value)
        data["parsed_date"] = parsed_from_parsed_date.fillna(parsed_from_date)
    else:
        data["parsed_date"] = parsed_from_date

    data = data.dropna(subset=["parsed_date", "amount"])
    data["amount"] = data["amount"].astype(float)
    data["month"] = data["parsed_date"].dt.strftime("%B").fillna("")
    data["signed_amount"] = [
        signed_amount(amount, txn_type)
        for amount, txn_type in zip(data["amount"], data["type"], strict=False)
    ]
    data["display_amount"] = data["amount"].abs()
    data = data.sort_values(["parsed_date", "description"], kind="stable").reset_index(
        drop=True
    )
    data["running_month_total"] = (
        data.groupby(data["parsed_date"].dt.to_period("M"))["display_amount"]
        .cumsum()
        .to_numpy()
    )
    data["parsed_date"] = data["parsed_date"].dt.strftime("%Y-%m-%d")
    return data


def week_bounds(value: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    parsed = parse_date_value(value)
    if pd.isna(parsed):
        raise ValueError("Cannot calculate week bounds for an invalid date.")
    days_since_sunday = (parsed.weekday() + 1) % 7
    start = parsed.normalize() - pd.Timedelta(days=days_since_sunday)
    end = start + pd.Timedelta(days=6)
    return start, end


def within_week(frame: pd.DataFrame, week_start: Any) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    parsed = parse_date_value(week_start)
    if pd.isna(parsed):
        return frame.iloc[0:0].copy()
    start, _ = week_bounds(parsed)
    end = start + pd.Timedelta(days=6)
    parsed_dates = pd.to_datetime(frame["parsed_date"], errors="coerce")
    mask = (parsed_dates >= start) & (parsed_dates <= end)
    return frame.loc[mask].copy()


def spending_total(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    mask = frame["type"].astype(str).str.strip().str.lower() == "expense"
    return float(frame.loc[mask, "display_amount"].sum())


def spending_total_for_range(frame: pd.DataFrame, start: Any, end: Any) -> float:
    if frame.empty:
        return 0.0
    parsed_dates = pd.to_datetime(frame["parsed_date"], errors="coerce")
    start_ts = parse_date_value(start).normalize()
    end_ts = parse_date_value(end).normalize()
    if pd.isna(start_ts) or pd.isna(end_ts):
        return 0.0
    mask = (parsed_dates >= start_ts) & (parsed_dates <= end_ts)
    subset = frame.loc[mask].copy()
    return spending_total(subset)


def category_spending_total(
    frame: pd.DataFrame, category: str, start: Any | None = None, end: Any | None = None
) -> float:
    if frame.empty:
        return 0.0
    subset = frame.copy()
    if start is not None and end is not None:
        parsed_dates = pd.to_datetime(subset["parsed_date"], errors="coerce")
        start_ts = parse_date_value(start).normalize()
        end_ts = parse_date_value(end).normalize()
        subset = subset.loc[(parsed_dates >= start_ts) & (parsed_dates <= end_ts)]
    mask = subset["type"].astype(str).str.strip().str.lower() == "expense"
    subset = subset.loc[mask]
    return float(
        subset.loc[
            subset["category"].astype(str).str.strip() == category, "display_amount"
        ].sum()
    )


def suggestion_map_from_transactions(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty:
        return {}
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for _, row in frame.iterrows():
        key = normalize_text(row.get("description"))
        category = str(row.get("category", "")).strip()
        if key and category:
            grouped[key][category] += 1
    suggestions: dict[str, str] = {}
    for key, counter in grouped.items():
        suggestions[key] = counter.most_common(1)[0][0]
    return suggestions


def suggest_category_from_history(
    merchant_or_description: Any, mapping: dict[str, str]
) -> str:
    key = normalize_text(merchant_or_description)
    if not key:
        return ""
    return mapping.get(key, "")


def update_suggestion_map(
    mapping: dict[str, str], merchant_or_description: Any, category: str
) -> dict[str, str]:
    updated = dict(mapping)
    key = normalize_text(merchant_or_description)
    if key and category:
        updated[key] = category
    return updated


def month_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "parsed_date" not in frame.columns:
        return []
    parsed = pd.to_datetime(frame["parsed_date"], errors="coerce")
    months = parsed.dt.to_period("M").dropna().astype(str).unique().tolist()
    months.sort()
    return months


def week_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "parsed_date" not in frame.columns:
        return []
    parsed = pd.to_datetime(frame["parsed_date"], errors="coerce")
    week_starts = (
        (parsed - pd.to_timedelta((parsed.dt.weekday + 1) % 7, unit="D"))
        .dt.normalize()
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    week_starts.sort()
    return week_starts
