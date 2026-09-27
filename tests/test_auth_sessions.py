"""Cookie session auth: establish, use, logout (service-token mode)."""

import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from rift.api import Handler


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


def _post(url, payload, headers=None):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode()), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode()), dict(exc.headers)


def _get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def _service_mode(monkeypatch):
    monkeypatch.setenv("RIFT_API_TOKEN", "tok-123")
    for name in ("RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY", "RIFT_SUPABASE_JWT_SECRET"):
        monkeypatch.delenv(name, raising=False)


def test_session_establish_use_logout(monkeypatch):
    _service_mode(monkeypatch)
    with _Server() as server:
        # Wrong token: 401, no cookie.
        status, _, headers = _post(server.url("/api/auth/session"), {"token": "wrong"})
        assert status == 401
        assert "Set-Cookie" not in headers

        # Correct token: 200 + HttpOnly cookie.
        status, payload, headers = _post(
            server.url("/api/auth/session"), {"token": "tok-123", "user_id": "op-1"})
        assert status == 200
        assert payload["user_id"] == "op-1"
        cookie = headers.get("Set-Cookie", "")
        assert "rift_session=" in cookie and "HttpOnly" in cookie

        session_cookie = cookie.split(";")[0]
        # Cookie alone (no Authorization header) passes a gated endpoint.
        status, _, _ = _get(server.url("/api/ops/monitor"), {"Cookie": session_cookie})
        assert status == 200

        # session-info reports the mechanism honestly.
        status, raw, _ = _get(server.url("/api/auth/session-info"), {"Cookie": session_cookie})
        assert status == 200
        info = json.loads(raw.decode())
        assert info["user_id"] == "op-1" and info["mechanism"] == "session-cookie"

        # Logout destroys it: same cookie now 401s.
        status, _, _ = _post(server.url("/api/auth/logout"), {}, {"Cookie": session_cookie})
        assert status == 200
        status, _, _ = _get(server.url("/api/ops/monitor"), {"Cookie": session_cookie})
        assert status == 401


def test_session_binds_owner_for_enforcement(monkeypatch):
    _service_mode(monkeypatch)
    with _Server() as server:
        status, _, headers = _post(
            server.url("/api/auth/session"), {"token": "tok-123", "user_id": "alice"})
        assert status == 200
        cookie = headers["Set-Cookie"].split(";")[0]
        # Spoofed reviewer under a bound session is rejected.
        status, payload, _ = _post(server.url("/api/twin/reviews"), {
            "action": "ACCEPT", "evidence_id": "ev-s", "reviewer_id": "mallory",
            "rationale": "x",
        }, {"Cookie": cookie})
        assert status == 400
        assert payload["error"] == "identity_mismatch"
        # Matching reviewer is accepted and verified.
        status, payload, _ = _post(server.url("/api/twin/reviews"), {
            "action": "ACCEPT", "evidence_id": "ev-s", "reviewer_id": "alice",
            "rationale": "x",
        }, {"Cookie": cookie})
        assert status == 201
        assert payload["identity_verified"] is True


def test_session_endpoints_need_service_token_mode(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    with _Server() as server:
        status, _, _ = _post(server.url("/api/auth/session"), {"token": "anything"})
        assert status == 401
