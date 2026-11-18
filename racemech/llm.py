"""
Minimal Ollama chat client (standard library only).

When Ollama is not reachable (PC off, service stopped) every call raises
``ModelUnavailable`` so callers can answer "unavailable" instead of guessing.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class ModelUnavailable(RuntimeError):
    """The local model server could not be reached or did not answer in time."""


@dataclass
class Reply:
    text: str
    model: str
    seconds: float
    prompt_tokens: int
    output_tokens: int


class OllamaClient:
    def __init__(self, url: str, model: str, timeout_s: float = 120.0, keep_alive: str = "5m",
                 temperature: float = 0.2, num_ctx: int = 8192):
        self.url = url.rstrip("/")
        self.num_ctx = num_ctx
        self.model = model
        self.timeout_s = timeout_s
        self.keep_alive = keep_alive
        self.temperature = temperature

    def _post(self, path: str, payload: dict, timeout: float) -> dict:
        req = urllib.request.Request(self.url + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ModelUnavailable(f"Local model server unreachable at {self.url}: {exc}") from exc

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(self.url + "/api/version", timeout=3) as resp:
                return resp.status == 200
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return False

    def chat(self, system: str, user: str) -> Reply:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,               # Qwen3.5 thinking adds latency; the context already has the maths
            "keep_alive": self.keep_alive,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        start = time.perf_counter()
        data = self._post("/api/chat", payload, self.timeout_s)
        if "error" in data:
            raise ModelUnavailable(f"Model error: {data['error']}")
        return Reply(
            text=data.get("message", {}).get("content", "").strip(),
            model=data.get("model", self.model),
            seconds=time.perf_counter() - start,
            prompt_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )
