"""API hardening tests: validation, limits, headers, auth gate, webhook replay."""

import hashlib
import hmac
import http.client
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

from rift import api as api_module
from rift.api import Handler

SUPABASE_VARS = (
    "RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY", "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY",
)
BILLING_VARS = (
    "RIFT_LEMON_SQUEEZY_API_KEY", "RIFT_LEMON_SQUEEZY_STORE_ID",
    "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "RIFT_LEMON_SQUEEZY_VARIANT_ID",
    "LEMON_SQUEEZY_API_KEY", "LEMON_SQUEEZY_STORE_ID",
    "LEMON_SQUEEZY_WEBHOOK_SECRET", "LEMON_SQUEEZY_VARIANT_ID",
)


def _clear(monkeypatch):
    for name in SUPABASE_VARS + BILLING_VARS + ("RIFT_API_TOKEN",):
        monkeypatch.delenv(name, raising=False)
    api_module._SEEN_WEBHOOK_KEYS.clear()


class _Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"


def _get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def _post(url, payload, headers=None, raw_bytes=None):
    body = raw_bytes if raw_bytes is not None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_security_headers_and_request_id(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, headers, _ = _get(server.url("/api/health"))
        assert status == 200
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-Request-ID")


def test_demo_rejects_out_of_range(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, _, raw = _get(server.url("/api/demo?crowd=999999"))
        assert status == 422
        assert json.loads(raw)["error"] == "invalid scenario"


def test_invalid_uuid_rejected(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, _, raw = _get(server.url("/api/experiments/not-a-uuid"))
        # Unconfigured persistence would be 503, but invalid IDs are 400 first.
        # Auth is open in dev mode so we reach validation.
        assert status in (400, 503)
        if status == 400:
            assert json.loads(raw)["error"] == "invalid_id"


def test_oversized_payload_413(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        big = "x" * (api_module.MAX_PAYLOAD_BYTES + 100)
        parts = urlparse(server.url("/api/experiments"))
        connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
        connection.request("POST", parts.path, body=big.encode(),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        assert response.status == 413
        connection.close()


def test_malformed_json_400(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, _, raw = _post(server.url("/api/experiments"), None, raw_bytes=b"{nope")
        assert status == 400


def test_upstream_errors_do_not_leak(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_SUPABASE_URL", "https://x.example.co")
    monkeypatch.setenv("RIFT_SUPABASE_KEY", "k")
    with _Server() as server:
        # No supabase package installed in CI-less env? Either 502 generic or
        # install-hint; neither may echo tracebacks.
        status, _, raw = _post(server.url("/api/experiments"),
                               {"name": "t", "scenario": {"crowd": 10}})
        assert status in (502, 503)
        body = raw.decode()
        assert "Traceback" not in body


def test_service_token_gate(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_API_TOKEN", "tok-123")
    with _Server() as server:
        status, _, _ = _get(server.url("/api/experiments/00000000-0000-4000-8000-000000000000"))
        assert status == 401
        status, _, raw = _get(
            server.url("/api/experiments/00000000-0000-4000-8000-000000000000"),
            headers={"Authorization": "Bearer tok-123"},
        )
        # Authed: now reaches persistence layer (503 offline).
        assert status == 503


def test_webhook_replay_duplicate_flag(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "s")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh")
    payload = {"meta": {"event_name": "order_created"}, "data": {"id": "o-dup"}}
    raw = json.dumps(payload).encode()
    signature = hmac.new(b"wh", raw, hashlib.sha256).hexdigest()
    with _Server() as server:
        first, _, raw1 = _post(server.url("/api/billing/webhook"), None,
                               headers={"X-Signature": signature}, raw_bytes=raw)
        second, _, raw2 = _post(server.url("/api/billing/webhook"), None,
                                headers={"X-Signature": signature}, raw_bytes=raw)
        assert first == 200
        assert second == 200
        assert json.loads(raw1) == {"received": True, "event": "order_created"}
        assert json.loads(raw2)["duplicate"] is True


def test_meta_endpoint_lists_limits(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, _, raw = _get(server.url("/api/meta"))
        assert status == 200
        payload = json.loads(raw)
        assert payload["engine_version"] == (__import__("rift").__version__)
        assert "max_policy_variables" in payload["limits"]


def test_demo_endpoint_serializes(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, _, raw = _get(server.url("/api/demo?crowd=430&smoke=3"))
        assert status == 200
        payload = json.loads(raw)
        assert len(payload["futures"]) == 8
        quadratic = payload["robust_optimization"]["qubo"]["quadratic"]
        assert all(isinstance(key, str) for key in quadratic)


def test_execute_503_when_unconfigured(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, _, raw = _post(
            server.url("/api/experiments/00000000-0000-4000-8000-000000000000/execute"), {}
        )
        assert status == 503
        assert json.loads(raw)["error"] == "persistence_not_configured"


def test_require_user_id_gate(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_REQUIRE_USER_ID", "true")
    with _Server() as server:
        status, _, raw = _post(
            server.url("/api/experiments"), {"name": "x", "scenario": {"crowd": 10}}
        )
        assert status == 400
        assert json.loads(raw)["error"] == "missing_user_id"
