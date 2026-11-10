Deployment and first-time setup

Goal: deploy the app to your home server (over WireGuard). Keep personal DB off GitHub.

Options and recommended approach

1) Recommended (safe, simple):
- Keep the repo in GitHub (or a private remote) without the DB file.
- On your home server: clone the repo, create a Python venv, install requirements, then copy the DB file from this laptop to the home server (scp over WireGuard). The app will use the local DB path you copied.

2) Alternative (no DB copy):
- Keep private CSV backups outside the repo and import on the home server using the app's Import page.
- This requires your CSV to be up-to-date before first run; merchant suggestions will be generated from the imported data.

Files changed to support deployment
- .gitignore: prevents `expense_tracker/expense_tracker.db`, `.env`, venv and other artifacts from being committed.
- .env.example: example env var `EXPENSE_TRACKER_DB` to point the app to a DB outside the repo.
- `app.py` now reads the DB path from the `EXPENSE_TRACKER_DB` env var (falls back to bundled default path).

First-time deploy steps (recommended)

On home server (over WireGuard):

1. Copy repo (use git or scp). Example via git:

```bash
# on home server
git clone <your-repo-url> expense_tracker_app
cd expense_tracker_app
```

or copy from laptop via scp (if you prefer):

```bash
# on laptop
scp -r ./My_finance_Server user@home-server:/home/user/
```

2. Create venv and install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Copy the DB from your laptop to the home server (only first time). Example:

```bash
# on laptop
scp /path/to/expense_tracker/expense_tracker.db user@home-server:/var/data/expense_tracker.db

# on home server
mkdir -p /var/data
# (file is already copied)
```

4. Set `EXPENSE_TRACKER_DB` env var on the home server so the app uses the copied DB (systemd unit, exported environment, or service EnvironmentFile)

```bash
export EXPENSE_TRACKER_DB=/var/data/expense_tracker.db
# or configure an EnvironmentFile in your systemd service
```

5. Run the app

```bash
source .venv/bin/activate
streamlit run expense_tracker/app.py
# or use your normal deployment command
```

6. First-time import alternative
- If you prefer to place a CSV on the home server and let the app import, copy the CSV to the home server and use the Import page in the Streamlit UI to run the import. That will create/import into the DB located at `EXPENSE_TRACKER_DB`.



Workflow for future updates
- Make code changes locally, commit, and push to your remote (or copy the updated repo to the home server).
- On home server: `git pull` to get changes, then restart the app/service. The local DB remains untouched.



## Updating the existing server for AI Insights

Develop and test in VS Code, then review the diff before committing. Do not stage
private databases, transaction exports, or `.env` files. No database migration or
replacement is needed for AI Insights.

Local verification (Windows PowerShell, using your existing virtual environment):

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m compileall -q expense_tracker tests
python -m streamlit run expense_tracker/app.py
```

For Linux/WSL use `source .venv/bin/activate`. Keep `EXPENSE_TRACKER_DB` set to your
existing local database, or point it to a disposable file for manual testing.
With no Ollama on the laptop, statistics work and pressing an AI button shows a
connection message.

After reviewing, stage only the feature files:

```bash
git diff --check
git diff
git add expense_tracker/ai_insights.py expense_tracker/ollama_client.py expense_tracker/app.py expense_tracker/plots.py tests/test_ai_insights.py tests/test_ollama_client.py tests/test_ai_ui.py tests/test_import_export.py requirements.txt .env.example README.md DEPLOY.md
git diff --cached --stat
git diff --cached
git commit -m "Add local Ollama financial insights"
git push
```

Then on the Ubuntu home server, from the existing checkout:

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
ollama list
# Only needed if the exact local model is absent:
ollama pull qwen3.5:2b-q4_K_M
curl --fail http://127.0.0.1:11434/api/tags
```

Add the `OLLAMA_*` settings listed in README.md to the existing Streamlit service's
process environment or its `EnvironmentFile`. Preserve `EXPENSE_TRACKER_DB`.
The app does not load `.env` automatically. For an interactive launch, export the
variables in the shell before running Streamlit. The defaults already match the
MX450 / Qwen 2B setup. Do not switch to the 4B model by default.

No Streamlit service name is specified in this repository. Identify yours:

```bash
systemctl list-units --type=service --all | rg -i 'streamlit|expense|finance'
# If rg is not installed, use grep -Ei instead.
# Inspect the matching service, then replace YOUR_SERVICE below with its real name:
systemctl cat YOUR_SERVICE
sudo systemctl restart YOUR_SERVICE
systemctl status YOUR_SERVICE --no-pager
journalctl -u YOUR_SERVICE -n 50 --no-pager
```

Use `systemctl --user` for a user service. If you edited the unit itself, run
`sudo systemctl daemon-reload` before restarting (not needed for changes only to
an existing EnvironmentFile). Do these operations on the server, not the laptop.
Do not change the Ollama bind address or open firewall ports.

While generating an analysis, run on the server:

```bash
ollama ps
nvidia-smi
# Inspect Ollama diagnostics if necessary (for a system Ollama service):
journalctl -u ollama -n 100 --no-pager
```

`ollama ps` reports the loaded model and CPU/GPU allocation; `nvidia-smi` shows GPU
memory/use while inference runs. Verify GPU allocation rather than assuming the
requested 25 layers guarantees offloading. For GPU memory failures, close other
GPU workloads or lower `OLLAMA_NUM_GPU`; restart Streamlit after changing its
environment. For timeouts allow model loading with a larger response timeout.

Manual checklist:

- Open the existing tabs and verify add/edit, merchant suggestions, charts and
  import/export still behave normally (use disposable synthetic data for writes).
- Select AI periods and check exact dates, totals, category shares and source JSON.
- Check an incomplete current month has no full-month comparison; missing months
  show unknown expenses rather than confirmed zero.
- Analyze spending, then ask about groceries or top merchants; verify the prose
  against the calculated statistics and inspect the supplied prompt.
- Ask about an account balance or dates outside the selected period: expect an
  explicit limitation, no invented figures.
- Change the period or transaction data; old AI results should clear. Ordinary
  reruns must not generate new Ollama requests.
- On the laptop without Ollama, confirm an actionable error and usable statistics.
- On the server, inspect GPU use during inference and confirm the 2B model is used.
