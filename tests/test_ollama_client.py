from unittest.mock import MagicMock, patch

import pytest
import requests

from expense_tracker.ollama_client import OllamaConfig, OllamaError, generate


def session_response(body=None, status=200):
    session = MagicMock()
    session.__enter__.return_value = session
    response = session.post.return_value
    response.status_code = status
    response.json.return_value = body if body is not None else {"done": True, "response": "A useful answer."}
    return session


def test_request_defaults_and_local_transport():
    session = session_response()
    with patch("expense_tracker.ollama_client.requests.Session", return_value=session):
        assert generate("facts", OllamaConfig()) == "A useful answer."
    session.post.assert_called_once_with("http://127.0.0.1:11434/api/generate", json={
        "model": "qwen3.5:2b-q4_K_M", "prompt": "facts", "stream": False, "think": False,
        "options": {"num_gpu": 25, "num_ctx": 2048, "num_predict": 400, "temperature": 0.2}},
        timeout=(5, 120), allow_redirects=False)
    assert session.trust_env is False


def test_environment_configuration(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_GPU", "12")
    monkeypatch.setenv("OLLAMA_MODEL", "local-test")
    monkeypatch.setenv("OLLAMA_RESPONSE_TIMEOUT", "180")
    config = OllamaConfig.from_env()
    assert (config.num_gpu, config.model, config.response_timeout) == (12, "local-test", 180)
    monkeypatch.setenv("OLLAMA_NUM_GPU", "bad")
    with pytest.raises(OllamaError, match="numeric"):
        OllamaConfig.from_env()


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.1.3:11434", "http://127.0.0.1@evil.com", "http://localhost/redirect", "http://localhost:bad"])
def test_reject_nonlocal_or_invalid_endpoints(url):
    with pytest.raises(OllamaError):
        OllamaConfig(url=url)


@pytest.mark.parametrize("options", [{"num_gpu": -1}, {"temperature": float("nan")},
                                    {"num_predict": 1000}, {"response_timeout": 0}, {"model": "test:cloud"}])
def test_invalid_config(options):
    with pytest.raises(OllamaError):
        OllamaConfig(**options)


@pytest.mark.parametrize("error,message", [(requests.ConnectionError(), "not reachable"), (requests.Timeout(), "timed out")])
def test_connection_errors(error, message):
    session = session_response()
    session.post.side_effect = error
    with patch("expense_tracker.ollama_client.requests.Session", return_value=session):
        with pytest.raises(OllamaError, match=message):
            generate("facts")


@pytest.mark.parametrize("body,status,message", [
    ([], 200, "malformed"), ({"response": ""}, 200, "empty or incomplete"),
    ({"done": False, "response": "partial"}, 200, "incomplete"),
    ({"done": True, "response": "cut", "done_reason": "length"}, 200, "limit"),
    ({"done": True, "response": "<think>reason</think>"}, 200, "thinking"),
    ({"error": "model not found"}, 404, "model not found"),
    ({"error": "CUDA out of memory"}, 500, "memory"),
    ({"error": "failure"}, 500, "could not complete"),
    ({}, 302, "could not complete")])
def test_api_failures(body, status, message):
    with patch("expense_tracker.ollama_client.requests.Session", return_value=session_response(body, status)):
        with pytest.raises(OllamaError, match=message):
            generate("facts")


def test_malformed_json():
    session = session_response()
    session.post.return_value.json.side_effect = ValueError("bad json")
    with patch("expense_tracker.ollama_client.requests.Session", return_value=session):
        with pytest.raises(OllamaError, match="malformed"):
            generate("facts")
