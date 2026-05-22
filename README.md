# Expense Tracker

A small local-first personal expense tracker built with Python, Streamlit, SQLite, pandas, and Plotly.

## Features

- Add transactions locally in a Streamlit form
- Browse, filter, edit, and delete transactions
- View dashboard summaries and charts
- Import and export CSV files
- Get simple history-based merchant category suggestions

## Setup

1. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
streamlit run expense_tracker/app.py
```

## Import sample data

The repository includes [sample_transactions.example.csv](sample_transactions.example.csv).
Use the Import / export page to upload it, or inspect it as a template for your own CSV files.

## CSV format

Required columns:

- date
- description
- category
- amount
- type

Optional calculated columns:

- month
- signed_amount
- running_month_total
- display_amount
- parsed_date

The importer will calculate missing optional columns automatically.

## Tests

Run the calculation tests with:

```bash
pytest
```

## Notes

- Everything runs locally with SQLite.
- There are no bank connections, paid APIs, or cloud databases.
- Version 1 focuses on a practical manual workflow replacement, not a full finance system.
