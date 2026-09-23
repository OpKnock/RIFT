"""API identity + rate-limit integration: JWT mode and 429 behavior over HTTP."""
import base64
import hashlib
import hmac
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from rift import api as api_module
from rift import ratelimit
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
JWT_VARS = ("RIFT_SUPABASE_JWT_SECRET", "RIFT_JWT_LEEWAY_S", "RIFT_SUPABASE_JWT_AUD", "RIFT_JWT_ISSUER")
LIMIT_VARS = (
    "RIFT_RATE_LIMIT_ENABLED", "RIFT_RATE_LIMIT_DEFAULT_N",
    "RIFT_RATE_LIMIT_DEFAULT_WINDOW_S", "RIFT_RATE_LIMIT_EXECUTE_N",
    "RIFT_RATE_LIMIT_EXECUTE_WINDOW_S", "RIFT_TRUST_PROXY",
)

JWT_SECRET = "integration-jwt-secret"


def _clear(monkeypatch):
    for name in SUPABASE_VARS + BILLING_VARS + JWT_VARS + LIMIT_VARS + ("RIFT_API_TOKEN", "RIFT_REQUIRE_USER_ID"):
        monkeypatch.delenv(name, raising=False)
    ratelimit.reset()
    api_module._SEEN_WEBHOOK_KEYS.clear()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _jwt(sub="user-jwt", secret=JWT_SECRET, exp_offset=300, alg="HS256"):
    header = {"alg": alg, "typ": "JWT"}
    body = {"sub": sub, "exp": time.time() + exp_offset}
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(body).encode())}"
    if alg == "none":
        return signing_input + "."
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(sig)}"


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
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_jwt_mode_requires_token(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_SUPABASE_JWT_SECRET", JWT_SECRET)
    with _Server() as server:
        status, _, raw = _get(server.url("/api/billing/entitlement?user_id=x"))
        assert status == 401
        status, _, raw = _get(
            server.url("/api/billing/entitlement?user_id=x"),
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert status == 401


def test_jwt_mode_rejects_forged_and_expired(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_SUPABASE_JWT_SECRET", JWT_SECRET)
    with _Server() as server:
        forged = _jwt(sub="user-a", secret="wrong-secret")
        status, _, _ = _get(
            server.url("/api/billing/entitlement?user_id=user-a"),
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert status == 401
        expired = _jwt(sub="user-a", exp_offset=-3600)
        status, _, _ = _get(
            server.url("/api/billing/entitlement?user_id=user-a"),
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert status == 401


def test_jwt_identity_ignores_spoofed_user_id(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_SUPABASE_JWT_SECRET", JWT_SECRET)
    token = _jwt(sub="user-real")
    with _Server() as server:
        # Attacker holds a valid token for user-real but asks for victim data.
        # Without Supabase configured the endpoint 503s, but it must NOT 403:
        # the spoofed query id is ignored and identity resolves to user-real.
        status, _, raw = _get(
            server.url("/api/billing/entitlement?user_id=victim"),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 503  # persistence offline, not forbidden
        assert json.loads(raw)["error"] == "persistence_not_configured"


def test_rate_limit_429_with_retry_after(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RIFT_RATE_LIMIT_DEFAULT_N", "2")
    monkeypatch.setenv("RIFT_RATE_LIMIT_DEFAULT_WINDOW_S", "60")
    with _Server() as server:
        assert _get(server.url("/api/health"))[0] == 200
        assert _get(server.url("/api/health"))[0] == 200
        status, headers, raw = _get(server.url("/api/health"))
        assert status == 429
        assert json.loads(raw)["error"] == "rate_limited"
        assert "Retry-After" in headers


def test_rate_limit_disabled_by_default(monkeypatch):
    _clear(monkeypatch)
    with _Server() as server:
        for _ in range(5):
            assert _get(server.url("/api/health"))[0] == 200
