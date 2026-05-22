Deployment and first-time setup

Goal: deploy the app to your home server (over WireGuard). Keep personal DB off GitHub.

Options and recommended approach

1) Recommended (safe, simple):
- Keep the repo in GitHub (or a private remote) without the DB file.
- On your home server: clone the repo, create a Python venv, install requirements, then copy the DB file from this laptop to the home server (scp over WireGuard). The app will use the local DB path you copied.

2) Alternative (no DB copy):
- Keep only CSVs in the repo and import on the home server using the app's Import page or a small import script.
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

4. Set `EXPENSE_TRACKER_DB` env var on the home server so the app uses the copied DB (systemd unit, environ, or .env)

```bash
export EXPENSE_TRACKER_DB=/var/data/expense_tracker.db
# or create a .env or write it into systemd service file
```

5. Run the app

```bash
source .venv/bin/activate
streamlit run expense_tracker/app.py
# or use your normal deployment command
```

6. First-time import alternative
- If you prefer to place a CSV on the home server and let the app import, copy the CSV to the home server and use the Import page in the Streamlit UI to run the import. That will create/import into the DB located at `EXPENSE_TRACKER_DB`.

Notes about git history and private data
- `.gitignore` will prevent new DB files from being added, but it does not remove the DB from prior commits. If the DB is already present in Git history (it was in an earlier commit), remove it from the index now and consider running a history rewrite (BFG or git filter-branch) if you plan to push the repo to a public remote and must purge the DB from history.
- To remove the DB from the index (leaves it on disk, untracked):

```bash
git rm --cached expense_tracker/expense_tracker.db
git commit -m "Remove DB from repo and ignore it"
```

If you want me to rewrite history to strip the DB from all commits, I can provide commands (note: destructive to history; coordinate carefully).

Workflow for future updates
- Make code changes locally, commit, and push to your remote (or copy the updated repo to the home server).
- On home server: `git pull` to get changes, then restart the app/service. The local DB remains untouched.

If you want, I can:
- Remove the tracked DB from git index and commit that change now.
- Add a small helper script to import a CSV automatically if placed at `/var/data/import.csv` on the home server.

Which of the two actions would you like me to do now?
- A) Remove the DB from git index now and commit, or
- B) Also add an auto-import script that runs once if `/var/data/import.csv` exists.
