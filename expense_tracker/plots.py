from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PLOT_TEMPLATE = "plotly_white"


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, showarrow=False, xref="paper", yref="paper"
    )
    fig.update_layout(
        template=PLOT_TEMPLATE, height=380, margin=dict(l=30, r=30, t=50, b=30)
    )
    return fig


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    data = frame.copy()
    data["parsed_date"] = pd.to_datetime(data["parsed_date"], errors="coerce")
    data = data.dropna(subset=["parsed_date"])
    data["spend_amount"] = data["display_amount"].abs()
    data["month_period"] = data["parsed_date"].dt.to_period("M").astype(str)
    data["day_of_month"] = data["parsed_date"].dt.day
    data["week_start"] = (
        (
            data["parsed_date"]
            - pd.to_timedelta((data["parsed_date"].dt.weekday + 1) % 7, unit="D")
        )
        .dt.normalize()
        .dt.strftime("%Y-%m-%d")
    )
    return data


def cumulative_daily_spending_by_month(frame: pd.DataFrame) -> go.Figure:
    data = _prepare(frame)
    if data.empty:
        return _empty_figure("No transactions available")
    expenses = data.loc[data["type"].astype(str).str.lower() == "expense"].copy()
    if expenses.empty:
        return _empty_figure("No expense transactions available")
    grouped = expenses.groupby(["month_period", "day_of_month"], as_index=False)[
        "spend_amount"
    ].sum()
    grouped = grouped.sort_values(["month_period", "day_of_month"])
    grouped["cumulative_spend"] = grouped.groupby("month_period")[
        "spend_amount"
    ].cumsum()

    current_month = str(pd.Timestamp.today().to_period("M"))
    fig = px.line(
        grouped,
        x="day_of_month",
        y="cumulative_spend",
        color="month_period",
        markers=False,
        labels={
            "day_of_month": "Day of month",
            "cumulative_spend": "Cumulative spending",
            "month_period": "Month",
        },
        title="Cumulative daily spending per month",
    )
    # Update traces: markers only on current month, varied styling
    for trace in fig.data:
        if trace.name == current_month:
            trace.line.width = 3
            trace.marker.size = 6
            trace.mode = "lines+markers"
            trace.opacity = 1
        else:
            trace.line.width = 1
            trace.opacity = 0.3
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=420,
        legend_title_text="Month",
        font=dict(size=12),
    )
    fig.update_xaxes(dtick=1)
    return fig


def monthly_category_spending(frame: pd.DataFrame) -> go.Figure:
    data = _prepare(frame)
    if data.empty:
        return _empty_figure("No transactions available")
    expenses = data.loc[data["type"].astype(str).str.lower() == "expense"].copy()
    if expenses.empty:
        return _empty_figure("No expense transactions available")
    grouped = expenses.groupby(["month_period", "category"], as_index=False)[
        "spend_amount"
    ].sum()
    grouped = grouped.sort_values("month_period")

    current_month = str(pd.Timestamp.today().to_period("M"))
    fig = px.bar(
        grouped,
        x="month_period",
        y="spend_amount",
        color="category",
        barmode="group",
        labels={
            "month_period": "Month",
            "spend_amount": "Spending",
            "category": "Category",
        },
        title="Monthly category spending",
    )
    # Highlight current month with full opacity, fade out other months
    for trace in fig.data:
        current_month_data = grouped[
            (grouped["month_period"] == current_month)
            & (grouped["category"] == trace.name)
        ]
        if not current_month_data.empty:
            trace.opacity = 1.0
        else:
            trace.opacity = 0.35
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=420,
        font=dict(size=12),
        xaxis_tickangle=-45,
        showlegend=True,
    )
    fig.update_yaxes(tickformat=".2f")
    return fig


def weekly_category_spending(frame: pd.DataFrame) -> go.Figure:
    data = _prepare(frame)
    if data.empty:
        return _empty_figure("No transactions available")
    expenses = data.loc[data["type"].astype(str).str.lower() == "expense"].copy()
    if expenses.empty:
        return _empty_figure("No expense transactions available")
    grouped = expenses.groupby(["week_start", "category"], as_index=False)[
        "spend_amount"
    ].sum()
    grouped = grouped.sort_values("week_start")

    today = pd.Timestamp.today().normalize()
    current_week_start = today - pd.Timedelta(days=(today.weekday() + 1) % 7)
    current_week_str = current_week_start.strftime("%Y-%m-%d")

    fig = px.bar(
        grouped,
        x="week_start",
        y="spend_amount",
        color="category",
        barmode="group",
        labels={
            "week_start": "Week starting",
            "spend_amount": "Spending",
            "category": "Category",
        },
        title="Weekly category spending",
    )
    # Highlight current week with full opacity, fade out other weeks
    for trace in fig.data:
        current_week_data = grouped[
            (grouped["week_start"] == current_week_str)
            & (grouped["category"] == trace.name)
        ]
        if not current_week_data.empty:
            trace.opacity = 1.0
        else:
            trace.opacity = 0.35
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=420,
        font=dict(size=12),
        xaxis_tickangle=-45,
        showlegend=True,
    )
    fig.update_yaxes(tickformat=".2f")
    return fig


def daily_spending_trend_for_month(
    frame: pd.DataFrame, month_period: str | None = None
) -> go.Figure:
    data = _prepare(frame)
    if data.empty:
        return _empty_figure("No transactions available")
    expenses = data.loc[data["type"].astype(str).str.lower() == "expense"].copy()
    if expenses.empty:
        return _empty_figure("No expense transactions available")
    if month_period:
        expenses = expenses.loc[expenses["month_period"] == month_period]
    if expenses.empty:
        return _empty_figure("No expense transactions for the selected month")
    grouped = expenses.groupby(expenses["parsed_date"].dt.date, as_index=False)[
        "spend_amount"
    ].sum()
    grouped.columns = ["date", "spend_amount"]
    fig = px.line(
        grouped,
        x="date",
        y="spend_amount",
        markers=True,
        labels={"date": "Date", "spend_amount": "Daily spending"},
        title="Daily spending trend",
    )
    fig.update_layout(template=PLOT_TEMPLATE, height=380)
    return fig
