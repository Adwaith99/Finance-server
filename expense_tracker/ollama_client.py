"""Small local-only Ollama HTTP boundary; no retries or executable model output."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import math
import os
from urllib.parse import urlsplit

import requests


class OllamaError(RuntimeError):
    """Safe, actionable error that can be shown directly in Streamlit."""


@dataclass(frozen=True)
class OllamaConfig:
    url: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:2b-q4_K_M"
    num_gpu: int = 25
    num_ctx: int = 2048
    num_predict: int = 400
    temperature: float = 0.2
    connect_timeout: float = 5
    response_timeout: float = 120

    def __post_init__(self) -> None:
        try:
            url = urlsplit(self.url)
            local = url.hostname == "localhost" or ipaddress.ip_address(url.hostname or "").is_loopback
            valid_port = url.port is None or 0 < url.port < 65536
        except ValueError:
            local, valid_port = False, False
        if (not local or not valid_port or url.scheme != "http" or url.username or url.password
                or url.path not in ("", "/") or url.query or url.fragment):
            raise OllamaError("OLLAMA_URL must be a local loopback HTTP URL, e.g. http://127.0.0.1:11434.")
        if not self.model.strip() or "cloud" in self.model.lower():
            raise OllamaError("Choose an installed local Ollama model, not a cloud model.")
        if (self.num_gpu < 0 or self.num_ctx < 2048 or not 1 <= self.num_predict <= self.num_ctx - 1600
                or not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2
                or not all(math.isfinite(v) and v > 0 for v in (self.connect_timeout, self.response_timeout))):
            raise OllamaError("Invalid Ollama settings: context >=2048, positive timeouts, GPU layers >=0, "
                              "temperature 0–2; reserve at least 1600 context tokens for input.")

    @classmethod
    def from_env(cls) -> OllamaConfig:
        try:
            return cls(**{name: convert(os.environ.get("OLLAMA_" + name.upper(), str(default)))
                          for name, convert, default in [
                              ("url", str, cls.url), ("model", str, cls.model),
                              ("num_gpu", int, cls.num_gpu), ("num_ctx", int, cls.num_ctx),
                              ("num_predict", int, cls.num_predict), ("temperature", float, cls.temperature),
                              ("connect_timeout", float, cls.connect_timeout),
                              ("response_timeout", float, cls.response_timeout)]})
        except ValueError as exc:
            raise OllamaError("Invalid numeric OLLAMA configuration; check the environment variables.") from exc


def generate(prompt: str, config: OllamaConfig | None = None) -> str:
    config = config or OllamaConfig.from_env()
    payload = {"model": config.model, "prompt": prompt, "stream": False, "think": False,
               "options": {"num_gpu": config.num_gpu, "num_ctx": config.num_ctx,
                           "num_predict": config.num_predict, "temperature": config.temperature}}
    try:
        # Ignore proxy environment variables and redirects to keep financial data local.
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(config.url.rstrip("/") + "/api/generate", json=payload,
                                    timeout=(config.connect_timeout, config.response_timeout),
                                    allow_redirects=False)
    except requests.Timeout as exc:
        raise OllamaError("Local AI timed out. Try again after the model loads, or increase OLLAMA_RESPONSE_TIMEOUT.") from exc
    except requests.RequestException as exc:
        raise OllamaError("Local AI is not reachable. Check that Ollama is running on this server and OLLAMA_URL is correct. Your statistics remain available.") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise OllamaError("Ollama returned a malformed response. Check the local Ollama service logs.") from exc
    if not isinstance(body, dict):
        raise OllamaError("Ollama returned a malformed response (expected a JSON object).")
    if response.status_code != 200 or body.get("error"):
        error = str(body.get("error", "")).lower()
        if response.status_code == 404 or "not found" in error:
            raise OllamaError(f"Local model not found. Run ollama pull {config.model} on the home server.")
        if any(word in error for word in ("memory", "cuda", "buffer", "gpu")):
            raise OllamaError("Ollama could not load the model into memory. Close other GPU workloads, use the 2B model, or reduce OLLAMA_NUM_GPU.")
        raise OllamaError("Ollama could not complete the request. Check its local service logs and configuration.")
    answer = body.get("response")
    if body.get("done") is not True or not isinstance(answer, str) or not answer.strip():
        raise OllamaError("Ollama returned an empty or incomplete answer. Check the model and service logs.")
    if body.get("done_reason") == "length":
        raise OllamaError("Ollama reached the response limit. Try a narrower question or increase OLLAMA_NUM_PREDICT and OLLAMA_NUM_CTX together.")
    if "<think>" in answer.lower() or "</think>" in answer.lower():
        raise OllamaError("The model returned thinking text despite think=false. Check local model/Ollama compatibility.")
    return answer.strip()
