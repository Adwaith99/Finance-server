from __future__ import annotations

from datetime import date
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from expense_tracker import calculations as calc
from expense_tracker import database as db
from expense_tracker import import_export, plots

st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="wide")

DB_PATH = Path(os.environ.get("EXPENSE_TRACKER_DB", str(db.DEFAULT_DB_PATH)))

# Initialize merchant suggestions from existing transactions (one-time)
if "merchants_populated" not in st.session_state:
    db.populate_merchant_categories_from_transactions(DB_PATH)
    st.session_state.merchants_populated = True


def format_currency(value: float) -> str:
    return f"{value:,.2f}"


@st.cache_data(ttl=10)
def load_transactions() -> pd.DataFrame:
    return db.fetch_transactions(DB_PATH)


@st.cache_data(ttl=10)
def load_mappings() -> pd.DataFrame:
    return db.list_merchant_category_mappings(DB_PATH)


def refresh_data() -> None:
    load_transactions.clear()
    load_mappings.clear()


def current_week_window() -> tuple[pd.Timestamp, pd.Timestamp]:
    today = pd.Timestamp.today().normalize()
    week_start = today - pd.Timedelta(days=(today.weekday() + 1) % 7)
    week_end = week_start + pd.Timedelta(days=6)
    return week_start, week_end


def current_month_period() -> str:
    return pd.Timestamp.today().to_period("M").strftime("%Y-%m")


def month_window(period: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Period(period).start_time.normalize()
    end = pd.Period(period).end_time.normalize()
    return start, end


def available_category_options(frame: pd.DataFrame) -> list[str]:
    categories = set(calc.DEFAULT_CATEGORIES)
    if not frame.empty and "category" in frame.columns:
        categories.update(frame["category"].dropna().astype(str).tolist())
    options = sorted(categories)
    return options


def show_summary_card(label: str, value: float) -> None:
    st.metric(label, format_currency(value))


def transaction_payload_from_form(
    transaction_date: date,
    description: str,
    category: str,
    amount: float,
    transaction_type: str,
) -> dict[str, object]:
    formatted_date = transaction_date.strftime("%d/%m/%Y")
    return {
        "date": formatted_date,
        "description": description.strip(),
        "category": category.strip(),
        "amount": float(amount),
        "type": transaction_type,
    }


def render_add_transaction_page() -> None:
    st.header("Add transaction")
    category_options = ["Eating out", "Groceries"]

    # Get available merchants for autocomplete
    available_merchants = db.get_all_merchants(DB_PATH)
    merchant_options = sorted(available_merchants)

    with st.form("add_transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            transaction_date = st.date_input("Date", value=date.today())
            description = st.text_input(
                "Merchant name",
                placeholder="Type merchant name or select from recent below",
            )
            if merchant_options:
                quick_select = st.selectbox(
                    "Or quick-select from recent:",
                    options=[""] + merchant_options,
                    format_func=lambda x: x if x else "-- Select merchant --",
                    key="merchant_quick_select",
                )
                # If user selected from dropdown, use that value
                if quick_select:
                    description = quick_select
        with col2:
            suggested_category = db.get_category_suggestion(description, DB_PATH)
            category_default_index = (
                category_options.index(suggested_category)
                if suggested_category in category_options
                else 0
            )
            category_choice = st.selectbox(
                "Category", options=category_options, index=category_default_index
            )
            amount_str = st.text_input(
                "Amount", placeholder="0.00", key="add_amount_input"
            )
            try:
                amount = float(amount_str) if amount_str else 0.0
            except ValueError:
                amount = 0.0
        if suggested_category:
            st.info(f"Suggested category: {suggested_category}")
        submitted = st.form_submit_button("Add transaction")

    if submitted:
        if not description.strip():
            st.error("Description is required.")
            return
        payload = transaction_payload_from_form(
            transaction_date, description, category_choice, amount, "Expense"
        )
        transaction_id = db.upsert_transaction(payload, DB_PATH)
        db.upsert_merchant_category(description, category_choice, DB_PATH)
        refresh_data()
        st.success(f"Transaction #{transaction_id} added.")
        st.rerun()


def render_transactions_page(frame: pd.DataFrame) -> None:
    st.header("Transactions")
    if frame.empty:
        st.info("No transactions yet.")
        return

    month_options = ["All"] + calc.month_options(frame)
    week_options = ["All"] + calc.week_options(frame)
    category_options = ["All"] + sorted(
        frame["category"].dropna().astype(str).unique().tolist()
    )
    type_options = ["All"] + calc.TRANSACTION_TYPES

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        selected_month = st.selectbox("Month", options=month_options)
    with filter_col2:
        selected_week = st.selectbox("Week starting", options=week_options)
    with filter_col3:
        selected_category = st.selectbox("Category", options=category_options)
    with filter_col4:
        selected_type = st.selectbox("Type", options=type_options)

    filtered = frame.copy()
    if selected_month != "All":
        filtered = filtered.loc[
            filtered["parsed_date"].dt.to_period("M").astype(str) == selected_month
        ]
    if selected_week != "All":
        week_start = pd.Timestamp(selected_week)
        week_end = week_start + pd.Timedelta(days=6)
        filtered = filtered.loc[
            (filtered["parsed_date"] >= week_start)
            & (filtered["parsed_date"] <= week_end)
        ]
    if selected_category != "All":
        filtered = filtered.loc[filtered["category"] == selected_category]
    if selected_type != "All":
        filtered = filtered.loc[filtered["type"] == selected_type]

    filtered = filtered.sort_values(["parsed_date", "id"], ascending=[False, False])
    display_frame = filtered.copy()
    display_frame["parsed_date"] = display_frame["parsed_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(display_frame, use_container_width=True, hide_index=True)

    if filtered.empty:
        return

    options = {
        f"#{int(row.id)} | {row.parsed_date.strftime('%Y-%m-%d')} | {row.description} | {row.category} | {row.amount:.2f}": int(
            row.id
        )
        for row in filtered.itertuples()
    }
    selected_label = st.selectbox(
        "Edit or delete a transaction", options=list(options.keys())
    )
    transaction_id = options[selected_label]
    selected_row = db.fetch_transaction(transaction_id, DB_PATH)
    if not selected_row:
        return

    st.subheader("Edit transaction")
    selected_date = pd.to_datetime(selected_row["parsed_date"]).date()
    edit_categories = available_category_options(frame)

    with st.form("edit_transaction_form"):
        edit_col1, edit_col2, edit_col3 = st.columns(3)
        with edit_col1:
            edit_date = st.date_input("Date", value=selected_date, key="edit_date")
            edit_description = st.text_input(
                "Merchant name",
                value=selected_row["description"],
                key="edit_description",
            )
        with edit_col2:
            suggestion = db.get_category_suggestion(edit_description, DB_PATH)
            edit_default_index = (
                edit_categories.index(selected_row["category"])
                if selected_row["category"] in edit_categories
                else 0
            )
            edit_category = st.selectbox(
                "Category",
                options=edit_categories,
                index=edit_default_index,
                key="edit_category",
            )
            edit_type = st.selectbox(
                "Type",
                options=calc.TRANSACTION_TYPES,
                index=0 if selected_row["type"] == "Expense" else 1,
                key="edit_type",
            )
        with edit_col3:
            edit_amount_str = st.text_input(
                "Amount",
                value=f"{float(selected_row['amount']):.2f}",
                key="edit_amount",
            )
            try:
                edit_amount = float(edit_amount_str) if edit_amount_str else 0.0
            except ValueError:
                edit_amount = 0.0
            if suggestion:
                st.info(f"Suggested category: {suggestion}")
        save_col, delete_col = st.columns(2)
        with save_col:
            save_pressed = st.form_submit_button("Save changes")
        with delete_col:
            delete_pressed = st.form_submit_button("Delete transaction")

    if save_pressed:
        payload = transaction_payload_from_form(
            edit_date, edit_description, edit_category, edit_amount, edit_type
        )
        db.update_transaction(transaction_id, payload, DB_PATH)
        db.upsert_merchant_category(edit_description, edit_category, DB_PATH)
        refresh_data()
        st.success("Transaction updated.")
        st.rerun()
    if delete_pressed:
        db.delete_transaction(transaction_id, DB_PATH)
        refresh_data()
        st.success("Transaction deleted.")
        st.rerun()


def render_dashboard_page(frame: pd.DataFrame) -> None:
    st.header("Dashboard")
    if frame.empty:
        st.info("No transactions yet. Add a transaction to see summaries.")
        return

    now = pd.Timestamp.today().normalize()
    month_start, month_end = month_window(now.strftime("%Y-%m"))

    # If current month has no data, use the latest month available
    current_month_data = calc.spending_total_for_range(frame, month_start, month_end)
    if current_month_data == 0:
        # Get the latest month with data
        latest_period = frame["parsed_date"].dt.to_period("M").max()
        if pd.notna(latest_period):
            month_start, month_end = month_window(str(latest_period))

    week_start, week_end = current_week_window()

    # If current week has no data, use the latest week available
    week_total_check = calc.spending_total_for_range(frame, week_start, week_end)
    if week_total_check == 0:
        # Get the latest week with data
        latest_week_start = frame["parsed_date"].min()
        if pd.notna(latest_week_start):
            latest_week_start = latest_week_start - pd.Timedelta(
                days=(latest_week_start.weekday() + 1) % 7
            )
            latest_week_end = latest_week_start + pd.Timedelta(days=6)
            # Find actual latest week with data
            for day_offset in range(0, 365, 7):
                check_start = frame["parsed_date"].max() - pd.Timedelta(days=day_offset)
                check_start = check_start - pd.Timedelta(
                    days=(check_start.weekday() + 1) % 7
                )
                check_end = check_start + pd.Timedelta(days=6)
                if calc.spending_total_for_range(frame, check_start, check_end) > 0:
                    week_start, week_end = check_start, check_end
                    break

    month_total = calc.spending_total_for_range(frame, month_start, month_end)
    week_total = calc.spending_total_for_range(frame, week_start, week_end)
    month_eating_out = calc.category_spending_total(
        frame, "Eating out", month_start, month_end
    )
    month_groceries = calc.category_spending_total(
        frame, "Groceries", month_start, month_end
    )
    week_eating_out = calc.category_spending_total(
        frame, "Eating out", week_start, week_end
    )
    week_groceries = calc.category_spending_total(
        frame, "Groceries", week_start, week_end
    )

    st.subheader("📅 This Month")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "💰 Total Spending",
            format_currency(month_total),
            delta=None,
            label_visibility="visible",
        )
    with col2:
        st.metric(
            "🍽️ Eating Out",
            format_currency(month_eating_out),
            delta=None,
            label_visibility="visible",
        )
    with col3:
        st.metric(
            "🛒 Groceries",
            format_currency(month_groceries),
            delta=None,
            label_visibility="visible",
        )

    st.divider()
    st.subheader("📆 This Week")
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric(
            "💰 Total Spending",
            format_currency(week_total),
            delta=None,
            label_visibility="visible",
        )
    with col5:
        st.metric(
            "🍽️ Eating Out",
            format_currency(week_eating_out),
            delta=None,
            label_visibility="visible",
        )
    with col6:
        st.metric(
            "🛒 Groceries",
            format_currency(week_groceries),
            delta=None,
            label_visibility="visible",
        )


def render_plots_page(frame: pd.DataFrame) -> None:
    st.header("Plots")
    if frame.empty:
        st.info("No transactions yet.")
        return

    month_periods = sorted(
        frame["parsed_date"].dt.to_period("M").astype(str).unique().tolist()
    )
    selected_month = st.selectbox(
        "Month for daily trend", options=["All"] + month_periods
    )
    selected_period = None if selected_month == "All" else selected_month

    st.plotly_chart(
        plots.cumulative_daily_spending_by_month(frame), use_container_width=True
    )
    st.plotly_chart(plots.monthly_category_spending(frame), use_container_width=True)
    st.plotly_chart(plots.weekly_category_spending(frame), use_container_width=True)
    st.plotly_chart(
        plots.daily_spending_trend_for_month(frame, selected_period),
        use_container_width=True,
    )


def render_import_export_page(frame: pd.DataFrame) -> None:
    st.header("Import / export")
    uploaded = st.file_uploader("Import transactions from CSV", type=["csv"])
    replace_existing = st.checkbox("Replace existing transactions", value=False)
    if uploaded is not None:
        try:
            imported = import_export.import_csv_bytes(uploaded.getvalue())
            st.dataframe(imported, use_container_width=True, hide_index=True)
            if st.button("Import CSV now"):
                count = db.bulk_upsert_transactions(
                    imported, DB_PATH, replace_existing=replace_existing
                )
                for description, category in (
                    imported[["description", "category"]]
                    .drop_duplicates()
                    .itertuples(index=False)
                ):
                    db.upsert_merchant_category(description, category, DB_PATH)
                refresh_data()
                st.success(f"Imported {count} transactions.")
                st.rerun()
        except ValueError as exc:
            st.error(f"Could not import CSV: {exc}")

    st.divider()
    export_frame = frame.copy()
    if not export_frame.empty:
        export_frame["parsed_date"] = export_frame["parsed_date"].dt.strftime(
            "%Y-%m-%d"
        )
        csv_text = import_export.export_transactions_csv(export_frame)
        st.download_button(
            label="Export all transactions as CSV",
            data=csv_text,
            file_name="expense_tracker_transactions.csv",
            mime="text/csv",
        )
    else:
        st.info("Add some transactions first to enable export.")


def render_settings_page(frame: pd.DataFrame) -> None:
    st.header("Settings")
    st.write(f"Database location: {DB_PATH}")
    st.write(f"Transactions stored: {len(frame)}")
    mappings = load_mappings()
    if mappings.empty:
        st.info(
            "💡 **Merchant suggestions:** No suggestions stored yet. These are automatically created when you "
            "manually add transactions through the 'Add transaction' page. As you add more transactions, "
            "the app will learn your favorite merchants and automatically suggest categories!"
        )
    else:
        st.subheader("Merchant suggestions")
        st.dataframe(mappings, use_container_width=True, hide_index=True)

    if st.button("Reset suggestion cache"):
        with db.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM merchant_categories")
            conn.commit()
        refresh_data()
        st.success("Suggestion mappings cleared.")
        st.rerun()


def main() -> None:
    db.initialize_database(DB_PATH)
    st.title("Expense Tracker 💸")
    
    frame = load_transactions()
    
    # Create tabs for navigation
    tab_dashboard, tab_add, tab_transactions, tab_plots, tab_import, tab_settings = st.tabs(
        [
            "📊 Dashboard",
            "➕ Add transaction",
            "📋 Transactions",
            "📈 Plots",
            "⬆️ Import/export",
            "⚙️ Settings",
        ]
    )
    
    with tab_dashboard:
        render_dashboard_page(frame)
    with tab_add:
        render_add_transaction_page()
    with tab_transactions:
        render_transactions_page(frame)
    with tab_plots:
        render_plots_page(frame)
    with tab_import:
        render_import_export_page(frame)
    with tab_settings:
        render_settings_page(frame)


if __name__ == "__main__":
    main()
