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

## Local AI Insights

The **AI Insights** tab explains recorded expenses and answers questions about the
selected period using local Ollama. Python computes category/merchant shares,
monthly totals and changes, recorded income and net cash flow, transaction counts,
and average spending per month with expense records. The model only explains these
statistics; it has no SQL, database write, shell, or file tools.

Choose the latest recorded month, last 3/6/12 calendar months, or all history.
Windows end at today or the end of the latest recorded month. Future transactions
are excluded. Missing expense records mean unknown spending, not zero spending.
Current partial months have no full-month comparison; category changes require
records in both months. Completeness of recorded history cannot be established.
Choose at least 3 months for comparisons within the selected period.

Statistics remain available without Ollama. AI requests happen only after pressing
**Analyze my spending** or **Ask AI**. Results persist across reruns in the current
session, and clear when the source summary, period, or AI configuration changes.
Questions are independent; there is no persistent chat history.

The AI receives aggregated statistics, including top merchant names from the
existing merchant/description field, never transaction rows. Do not store personal
identifiers in merchant names. Inputs are compacted to a 4,200-byte prompt budget;
only top categories/merchants and recent months are sent, and larger breakdowns
may be omitted. Both the full calculations and exact analysis prompt are viewable
in expanders. Questions requiring omitted details or dates outside this scope
must acknowledge the limitation. AI prose can still be wrong: verify it against
the Python statistics.

Install Python dependencies with `python -m pip install -r requirements.txt`.
The only added dependency is `requests`. pandas is constrained to `>=2.2,<3`
to preserve the existing CSV date handling. No model installation is required on a
Windows development laptop. On the Ubuntu server with Ollama already installed:

```bash
ollama pull qwen3.5:2b-q4_K_M
export OLLAMA_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen3.5:2b-q4_K_M
python -m streamlit run expense_tracker/app.py
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Loopback HTTP endpoint only |
| `OLLAMA_MODEL` | `qwen3.5:2b-q4_K_M` | Installed local model; cloud model names rejected |
| `OLLAMA_NUM_GPU` | `25` | GPU layers; reduce if memory is exhausted |
| `OLLAMA_NUM_CTX` | `2048` | Context tokens, minimum 2048 |
| `OLLAMA_NUM_PREDICT` | `400` | Maximum output tokens; reserve at least 1600 context tokens for input |
| `OLLAMA_TEMPERATURE` | `0.2` | Sampling temperature (0–2) |
| `OLLAMA_CONNECT_TIMEOUT` | `5` | Connection timeout in seconds |
| `OLLAMA_RESPONSE_TIMEOUT` | `120` | Response timeout in seconds, including model loading |

`think` and `stream` are always false. No automatic retries or model preloading.
Proxy environment variables and HTTP redirects are disabled. Keep Ollama bound to
loopback; do not expose port 11434 publicly. Use installed local models only.
Configuration is read from process environment; `.env` files are **not loaded
automatically**. `.env.example` is a template, not an active configuration file.
Leave `EXPENSE_TRACKER_DB` pointing to your existing private database.

If AI fails, the tab displays an actionable connection, timeout, model, memory,
or malformed-response error. Other features and deterministic summaries keep
working. Truncated output is reported as a failure rather than a complete answer.

Verify and test (no Ollama or GPU needed for tests):

```bash
python -m pytest -q
python -m compileall -q expense_tracker tests
```

See [DEPLOY.md](DEPLOY.md) for updates and GPU verification. Ollama request fields
follow its [official API reference](https://github.com/ollama/ollama/blob/main/docs/api.md).
