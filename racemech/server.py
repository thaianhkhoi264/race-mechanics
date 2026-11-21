"""
``racemech serve``: answer questions for bot_repo over the network.

The bot (on the remote host) posts a question; this process (on the PC, next to Ollama) builds the context
and asks the model. Answers are computed one at a time because the GPU is the bottleneck; when too
many questions are already waiting the service answers 503 "busy" instead of queueing forever.

    GET  /health  -> {"ok", "model", "model_ready", "waiting", "data_synced"}
    POST /ask     {"question", "asker"} -> {"answer", "seconds", "notes"}

Every request needs the header ``Authorization: Bearer <serve_token>``. Errors come back as
``{"error": <code>}`` with 400 (bad_request / too_long), 401 (unauthorized), 503 (busy /
model_unavailable) or 500 (internal).
"""
from __future__ import annotations

import hmac
import json
import logging
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from racemech.llm import ModelUnavailable

log = logging.getLogger("racemech.serve")

MAX_QUESTION = 500          # characters
MAX_BODY = 8192             # bytes


class Service:
    """The part of the server that doesn't know about HTTP (tested directly)."""

    def __init__(self, assistant, token: str, max_waiting: int = 3, log_path: Path | None = None,
                 data_dir: Path | None = None):
        if not token:
            raise ValueError("serve_token is empty: set it in racemech.toml or RACEMECH_SERVE_TOKEN")
        self.assistant = assistant
        self.token = token
        self.max_waiting = max_waiting
        self.log_path = log_path
        self.data_dir = data_dir
        self._lock = threading.Lock()           # one answer at a time
        self._count = threading.Lock()
        self.waiting = 0                        # questions queued or being answered

    def authorized(self, header: str | None) -> bool:
        given = (header or "").removeprefix("Bearer ").strip()
        return hmac.compare_digest(given.encode(), self.token.encode())

    def health(self) -> dict:
        synced = None
        if self.data_dir is not None:
            master = self.data_dir / "game" / "global_master.mdb"
            if master.is_file():
                synced = datetime.fromtimestamp(master.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        return {"ok": True, "model": self.assistant.client.model,
                "model_ready": self.assistant.client.available(), "waiting": self.waiting,
                "data_synced": synced}

    def ask(self, question: str, asker: str = "") -> tuple[int, dict]:
        question = (question or "").strip()
        if not question:
            return 400, {"error": "bad_request"}
        if len(question) > MAX_QUESTION:
            return 400, {"error": "too_long", "max": MAX_QUESTION}
        with self._count:
            if self.waiting > self.max_waiting:
                return 503, {"error": "busy", "waiting": self.waiting}
            self.waiting += 1
        try:
            with self._lock:
                start = time.monotonic()
                try:
                    ans = self.assistant.ask(question)
                except ModelUnavailable as exc:
                    log.warning("model unavailable: %s", exc)
                    return 503, {"error": "model_unavailable"}
                seconds = round(time.monotonic() - start, 1)
            out = {"answer": ans.reply.text, "seconds": seconds, "notes": list(ans.context.notes)}
            self._log(question, asker, out)
            return 200, out
        except Exception:                   # noqa: BLE001 - a bad question must not kill the server
            log.exception("failed to answer %r", question)
            return 500, {"error": "internal"}
        finally:
            with self._count:
                self.waiting -= 1

    def _log(self, question: str, asker: str, out: dict) -> None:
        if self.log_path is None:
            return
        row = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "asker": asker,
               "question": question, **out}
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("could not write the Q&A log: %s", exc)


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "racemech"

        def _send(self, status: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _auth(self) -> bool:
            if service.authorized(self.headers.get("Authorization")):
                return True
            self._send(401, {"error": "unauthorized"})
            return False

        def do_GET(self):  # noqa: N802 - http.server naming
            if self.path != "/health":
                return self._send(404, {"error": "not_found"})
            if self._auth():
                self._send(200, service.health())

        def do_POST(self):  # noqa: N802
            if self.path != "/ask":
                return self._send(404, {"error": "not_found"})
            if not self._auth():
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                return self._send(400, {"error": "bad_request"})
            try:
                body = json.loads(self.rfile.read(length))
                question, asker = str(body.get("question", "")), str(body.get("asker", ""))
            except (ValueError, AttributeError):
                return self._send(400, {"error": "bad_request"})
            self._send(*service.ask(question, asker))

        def log_message(self, fmt, *args):      # route http.server's access log through logging
            log.info("%s %s", self.address_string(), fmt % args)

    return Handler


def serve(service: Service, host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    log.info("racemech serve listening on %s:%d (model %s)", host, port, service.assistant.client.model)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
