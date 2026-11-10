"""UI checks use a temporary synthetic SQLite DB and a mocked Ollama boundary."""
from pathlib import Path
from unittest.mock import patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from expense_tracker import database as db
from expense_tracker.ollama_client import OllamaError


@pytest.fixture(autouse=True)
def clear_streamlit_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def app_with_data(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.db"
    monkeypatch.setenv("EXPENSE_TRACKER_DB", str(path))
    db.upsert_transaction({"date": "2026-01-05", "description": "Test Market", "category": "Groceries",
                           "amount": 100, "type": "Expense"}, path)
    return AppTest.from_file(Path(__file__).resolve().parents[1] / "expense_tracker/app.py", default_timeout=20)


def test_ai_buttons_reruns_and_read_only(tmp_path, monkeypatch):
    app = app_with_data(tmp_path, monkeypatch)
    path = tmp_path / "synthetic.db"
    before = db.fetch_transactions(path).to_json()
    with patch("expense_tracker.ollama_client.generate", return_value="Recorded grocery spending is CAD 100.") as generate:
        app.run()
        assert not app.exception
        assert len(app.tabs) == 7
        generate.assert_not_called()
        app.button(key="ai_analyze").click().run()
        assert not app.exception
        generate.assert_called_once()
        assert "Recorded grocery spending" in app.text[0].value
        app.run()
        generate.assert_called_once()
        app.selectbox(key="ai_period").select("Last 3 months").run()
        assert not app.exception
        assert len(app.text) == 0
        app.text_area[0].input("Which category is largest?")
        next(b for b in app.button if b.label == "Ask AI").click().run()
        assert generate.call_count == 2
        assert "Which category is largest?" in generate.call_args.args[0]
    assert db.fetch_transactions(path).to_json() == before


def test_unavailable_ai_keeps_statistics(tmp_path, monkeypatch):
    app = app_with_data(tmp_path, monkeypatch)
    with patch("expense_tracker.ollama_client.generate", side_effect=OllamaError("Local AI is not reachable.")):
        app.run()
        app.button(key="ai_analyze").click().run()
        assert not app.exception
        assert any("not reachable" in warning.value for warning in app.warning)
        assert any(metric.label == "Recorded expenses (CAD)" and metric.value == "100.00" for metric in app.metric)


def test_empty_app_does_not_call_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPENSE_TRACKER_DB", str(tmp_path / "empty.db"))
    with patch("expense_tracker.ollama_client.generate") as generate:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "expense_tracker/app.py", default_timeout=20).run()
        assert not app.exception
        generate.assert_not_called()
        assert any("No recorded transactions" in info.value for info in app.info)
