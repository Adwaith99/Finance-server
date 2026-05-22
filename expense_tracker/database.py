from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from expense_tracker.calculations import add_derived_columns, normalize_text

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PACKAGE_DIR / "expense_tracker.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL,
    month TEXT NOT NULL,
    signed_amount REAL NOT NULL,
    display_amount REAL NOT NULL,
    running_month_total REAL NOT NULL DEFAULT 0,
    parsed_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS merchant_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_key TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def database_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else DEFAULT_DB_PATH


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = database_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(path: str | Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _prepare_transaction_record(record: dict[str, Any]) -> dict[str, Any]:
    frame = add_derived_columns(pd.DataFrame([record]))
    prepared = frame.iloc[0].to_dict()
    prepared["parsed_date"] = str(prepared["parsed_date"])
    return prepared


def recompute_running_month_totals(conn: sqlite3.Connection, month: str) -> None:
    rows = conn.execute(
        """
        SELECT id, display_amount, parsed_date, description
        FROM transactions
        WHERE month = ?
        ORDER BY parsed_date ASC, id ASC
        """,
        (month,),
    ).fetchall()
    running_total = 0.0
    for row in rows:
        running_total += float(row["display_amount"])
        conn.execute(
            "UPDATE transactions SET running_month_total = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (running_total, row["id"]),
        )


def upsert_transaction(record: dict[str, Any], path: str | Path | None = None) -> int:
    initialize_database(path)
    prepared = _prepare_transaction_record(record)
    with connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO transactions (
                date, description, category, amount, type, month,
                signed_amount, display_amount, running_month_total, parsed_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                prepared["date"],
                prepared["description"],
                prepared["category"],
                float(prepared["amount"]),
                prepared["type"],
                prepared["month"],
                float(prepared["signed_amount"]),
                float(prepared["display_amount"]),
                prepared["parsed_date"],
            ),
        )
        transaction_id = int(cursor.lastrowid)
        recompute_running_month_totals(conn, prepared["month"])
        conn.commit()
        return transaction_id


def bulk_upsert_transactions(
    records: pd.DataFrame | list[dict[str, Any]],
    path: str | Path | None = None,
    replace_existing: bool = False,
) -> int:
    initialize_database(path)
    frame = (
        records.copy()
        if isinstance(records, pd.DataFrame)
        else pd.DataFrame(list(records))
    )
    if frame.empty:
        return 0

    prepared = add_derived_columns(frame)
    if prepared.empty:
        return 0

    rows = prepared[
        [
            "date",
            "description",
            "category",
            "amount",
            "type",
            "month",
            "signed_amount",
            "display_amount",
            "parsed_date",
        ]
    ].copy()
    rows["parsed_date"] = rows["parsed_date"].astype(str)

    with connect(path) as conn:
        if replace_existing:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM merchant_categories")
        conn.executemany(
            """
            INSERT INTO transactions (
                date, description, category, amount, type, month,
                signed_amount, display_amount, running_month_total, parsed_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            [
                (
                    row["date"],
                    row["description"],
                    row["category"],
                    float(row["amount"]),
                    row["type"],
                    row["month"],
                    float(row["signed_amount"]),
                    float(row["display_amount"]),
                    row["parsed_date"],
                )
                for row in rows.to_dict("records")
            ],
        )
        for month in sorted(rows["month"].dropna().astype(str).unique().tolist()):
            recompute_running_month_totals(conn, month)
        conn.commit()
    return len(rows)


def update_transaction(
    transaction_id: int, record: dict[str, Any], path: str | Path | None = None
) -> None:
    initialize_database(path)
    prepared = _prepare_transaction_record(record)
    with connect(path) as conn:
        existing = conn.execute(
            "SELECT month FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if existing is None:
            raise ValueError(f"Transaction {transaction_id} does not exist.")
        conn.execute(
            """
            UPDATE transactions
            SET date = ?, description = ?, category = ?, amount = ?, type = ?,
                month = ?, signed_amount = ?, display_amount = ?, parsed_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                prepared["date"],
                prepared["description"],
                prepared["category"],
                float(prepared["amount"]),
                prepared["type"],
                prepared["month"],
                float(prepared["signed_amount"]),
                float(prepared["display_amount"]),
                prepared["parsed_date"],
                transaction_id,
            ),
        )
        recompute_running_month_totals(conn, prepared["month"])
        if existing["month"] != prepared["month"]:
            recompute_running_month_totals(conn, existing["month"])
        conn.commit()


def delete_transaction(transaction_id: int, path: str | Path | None = None) -> None:
    initialize_database(path)
    with connect(path) as conn:
        existing = conn.execute(
            "SELECT month FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if existing is None:
            return
        month = existing["month"]
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        recompute_running_month_totals(conn, month)
        conn.commit()


def fetch_transactions(
    path: str | Path | None = None,
    month: str | None = None,
    week_start: str | None = None,
    category: str | None = None,
    transaction_type: str | None = None,
) -> pd.DataFrame:
    initialize_database(path)
    query = "SELECT * FROM transactions WHERE 1 = 1"
    params: list[Any] = []

    if month and month != "All":
        query += " AND month = ?"
        params.append(month)
    if week_start and week_start != "All":
        start = pd.to_datetime(week_start).normalize()
        end = start + pd.Timedelta(days=6)
        query += " AND parsed_date >= ? AND parsed_date <= ?"
        params.extend([start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")])
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if transaction_type and transaction_type != "All":
        query += " AND type = ?"
        params.append(transaction_type)

    query += " ORDER BY parsed_date ASC, id ASC"
    with connect(path) as conn:
        rows = conn.execute(query, params).fetchall()
    if not rows:
        return pd.DataFrame(
            columns=[
                "id",
                "date",
                "description",
                "category",
                "amount",
                "type",
                "month",
                "signed_amount",
                "display_amount",
                "running_month_total",
                "parsed_date",
            ]
        )
    frame = pd.DataFrame([dict(row) for row in rows])
    frame["parsed_date"] = pd.to_datetime(frame["parsed_date"], errors="coerce")
    return frame


def fetch_transaction(
    transaction_id: int, path: str | Path | None = None
) -> dict[str, Any] | None:
    initialize_database(path)
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_months(path: str | Path | None = None) -> list[str]:
    frame = fetch_transactions(path)
    if frame.empty:
        return []
    months = frame["month"].dropna().astype(str).unique().tolist()
    months.sort()
    return months


def list_categories(path: str | Path | None = None) -> list[str]:
    frame = fetch_transactions(path)
    if frame.empty:
        return []
    categories = frame["category"].dropna().astype(str).unique().tolist()
    categories.sort()
    return categories


def list_week_starts(path: str | Path | None = None) -> list[str]:
    frame = fetch_transactions(path)
    if frame.empty:
        return []
    parsed = pd.to_datetime(frame["parsed_date"], errors="coerce")
    week_starts = (
        (parsed - pd.to_timedelta((parsed.dt.weekday + 1) % 7, unit="D"))
        .dt.normalize()
        .dropna()
        .dt.strftime("%Y-%m-%d")
        .unique()
        .tolist()
    )
    week_starts.sort()
    return week_starts


def upsert_merchant_category(
    merchant: str, category: str, path: str | Path | None = None
) -> None:
    initialize_database(path)
    merchant_key = normalize_text(merchant)
    if not merchant_key or not category:
        return
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO merchant_categories (merchant_key, category, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(merchant_key) DO UPDATE SET
                category = excluded.category,
                updated_at = CURRENT_TIMESTAMP
            """,
            (merchant_key, category),
        )
        conn.commit()


def get_category_suggestion(merchant: str, path: str | Path | None = None) -> str:
    initialize_database(path)
    merchant_key = normalize_text(merchant)
    if not merchant_key:
        return ""
    with connect(path) as conn:
        row = conn.execute(
            "SELECT category FROM merchant_categories WHERE merchant_key = ?",
            (merchant_key,),
        ).fetchone()
    return str(row["category"]) if row else ""


def list_merchant_category_mappings(path: str | Path | None = None) -> pd.DataFrame:
    initialize_database(path)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT merchant_key, category, updated_at FROM merchant_categories ORDER BY updated_at DESC, merchant_key ASC"
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["merchant_key", "category", "updated_at"])
    return pd.DataFrame([dict(row) for row in rows])


def get_all_merchants(path: str | Path | None = None) -> list[str]:
    """Get all unique merchants from merchant_categories table, sorted alphabetically."""
    initialize_database(path)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT merchant_key FROM merchant_categories ORDER BY merchant_key ASC"
        ).fetchall()
    return [row["merchant_key"] for row in rows]


def populate_merchant_categories_from_transactions(
    path: str | Path | None = None,
) -> int:
    """Pre-populate merchant_categories from existing transactions. Returns count of new mappings added."""
    initialize_database(path)
    with connect(path) as conn:
        # Get unique merchant-category pairs from transactions
        rows = conn.execute("""
            SELECT DISTINCT description, category FROM transactions
            ORDER BY description ASC
        """).fetchall()

        count = 0
        for row in rows:
            merchant = row["description"]
            category = row["category"]
            merchant_key = normalize_text(merchant)

            if not merchant_key or not category:
                continue

            # Check if this merchant_key already exists
            existing = conn.execute(
                "SELECT id FROM merchant_categories WHERE merchant_key = ?",
                (merchant_key,),
            ).fetchone()

            if not existing:
                conn.execute(
                    """
                    INSERT INTO merchant_categories (merchant_key, category, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (merchant_key, category),
                )
                count += 1

        conn.commit()
    return count
