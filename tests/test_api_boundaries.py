"""HTTP boundary tests: endpoints fail closed without credentials, no network."""

import hashlib
import hmac
import json
import threading
import urllib.request
import urllib.error

from rift.api import Handler, serve
from http.server import ThreadingHTTPServer


SUPABASE_VARS = (
    "RIFT_SUPABASE_URL",
    "RIFT_SUPABASE_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_ANON_KEY",
)
BILLING_VARS = (
    "RIFT_LEMON_SQUEEZY_API_KEY",
    "RIFT_LEMON_SQUEEZY_STORE_ID",
    "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET",
    "RIFT_LEMON_SQUEEZY_VARIANT_ID",
    "LEMON_SQUEEZY_API_KEY",
    "LEMON_SQUEEZY_STORE_ID",
    "LEMON_SQUEEZY_WEBHOOK_SECRET",
    "LEMON_SQUEEZY_VARIANT_ID",
)


def _clear(monkeypatch):
    for name in SUPABASE_VARS + BILLING_VARS:
        monkeypatch.delenv(name, raising=False)


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


def _get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, json.loads(response.read().decode())


def _post(url, payload, headers=None):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def test_health_includes_status_without_secrets(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, payload = _get(server.url("/api/health"))
        assert status == 200
        assert payload["status"] == "ok"
        assert payload["persistence"] == {"configured": False}
        assert payload["billing"]["configured"] is False


def test_persistence_endpoints_503_when_unconfigured(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, payload = _post(
            server.url("/api/experiments"), {"name": "x", "scenario": {"a": 1}}
        )
        assert status == 503
        assert payload["error"] == "persistence_not_configured"

        status, _ = _get(server.url("/api/persistence/status"))
        assert status == 200


def test_billing_checkout_503_when_unconfigured(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, payload = _get(server.url("/api/billing/status"))
        assert status == 200 and payload["configured"] is False

        status, payload = _post(server.url("/api/billing/checkout"), {"variant_id": "1"})
        assert status == 503
        assert payload["error"] == "billing_not_configured"


def test_billing_webhook_requires_secret(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        status, payload = _post(
            server.url("/api/billing/webhook"),
            {"meta": {"event_name": "order_created"}},
        )
        assert status == 503
        assert payload["error"] == "billing_webhook_not_configured"


def test_billing_webhook_rejects_bad_signature(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "test-key")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "store-1")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh-secret")
    with _Server() as server:
        status, payload = _post(
            server.url("/api/billing/webhook"),
            {"meta": {"event_name": "order_created"}},
            headers={"X-Signature": "0" * 64},
        )
        assert status == 401
        assert payload["error"] == "invalid_signature"


def test_billing_webhook_accepts_valid_signature_without_supabase(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "test-key")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "store-1")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh-secret")
    payload = {"meta": {"event_name": "order_created"}, "data": {"id": "o-1"}}
    raw = json.dumps(payload).encode()
    signature = hmac.new(b"wh-secret", raw, hashlib.sha256).hexdigest()
    # Send the exact bytes we signed by using raw request to avoid key-order drift.
    import http.client

    with _Server() as server:
        from urllib.parse import urlparse

        parts = urlparse(server.url("/api/billing/webhook"))
        connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
        connection.request(
            "POST",
            parts.path,
            body=raw,
            headers={"Content-Type": "application/json", "X-Signature": signature},
        )
        response = connection.getresponse()
        assert response.status == 200
        body = json.loads(response.read().decode())
        assert body == {"received": True, "event": "order_created"}
        connection.close()
