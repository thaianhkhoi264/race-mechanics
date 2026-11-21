"""racemech serve with a fake assistant: auth, validation, busy, model down, and real HTTP."""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from racemech.llm import ModelUnavailable
from racemech.server import MAX_QUESTION, Service, make_handler


class FakeAssistant:
    def __init__(self, delay=0.0, fail=None):
        self.client = SimpleNamespace(model="fake:1b", available=lambda: True)
        self.delay, self.fail, self.calls = delay, fail, 0

    def ask(self, question):
        self.calls += 1
        if self.fail:
            raise self.fail
        time.sleep(self.delay)
        return SimpleNamespace(reply=SimpleNamespace(text=f"answer to {question}"),
                               context=SimpleNamespace(notes=["assumed CM22"]))


def test_needs_a_token():
    with pytest.raises(ValueError):
        Service(FakeAssistant(), "")


def test_auth():
    s = Service(FakeAssistant(), "secret")
    assert s.authorized("Bearer secret")
    assert not s.authorized("Bearer nope") and not s.authorized(None)


def test_ask_and_log(tmp_path):
    log = tmp_path / "qa.jsonl"
    s = Service(FakeAssistant(), "t", log_path=log)
    status, body = s.ask("  is wit good?  ", "user#1")
    assert status == 200 and body["answer"] == "answer to is wit good?" and body["notes"] == ["assumed CM22"]
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["asker"] == "user#1" and row["question"] == "is wit good?"


def test_validation():
    s = Service(FakeAssistant(), "t")
    assert s.ask("   ")[0] == 400
    assert s.ask("x" * (MAX_QUESTION + 1))[1]["error"] == "too_long"


def test_model_down_and_crash():
    assert Service(FakeAssistant(fail=ModelUnavailable("off")), "t").ask("q") == (503, {"error": "model_unavailable"})
    assert Service(FakeAssistant(fail=KeyError("x")), "t").ask("q") == (500, {"error": "internal"})


def test_busy_when_queue_is_full():
    s = Service(FakeAssistant(delay=0.3), "t", max_waiting=1)
    results = []
    threads = [threading.Thread(target=lambda: results.append(s.ask("q")[0])) for _ in range(2)]
    for t in threads:
        t.start()
    time.sleep(0.05)                     # one answering, one waiting
    assert s.ask("q") == (503, {"error": "busy", "waiting": 2})
    for t in threads:
        t.join()
    assert results == [200, 200] and s.waiting == 0


def test_http_round_trip():
    s = Service(FakeAssistant(), "tok")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(s))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, body=None, token="tok"):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    try:
        assert call("/health")[1]["model"] == "fake:1b"
        assert call("/health", token="bad")[0] == 401
        assert call("/ask", {"question": "hi", "asker": "u"}) == (
            200, {"answer": "answer to hi", "seconds": 0.0, "notes": ["assumed CM22"]})
        assert call("/nope")[0] == 404
    finally:
        httpd.shutdown()
