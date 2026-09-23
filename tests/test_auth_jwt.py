"""JWT verification tests: forged/expired/alg-swapped tokens must fail closed."""
import base64
import hashlib
import hmac
import json
import time

import pytest

from rift.auth_jwt import AuthError, jwt_mode_enabled, verify_bearer_token

SECRET = "test-jwt-secret"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _token(secret=SECRET, alg="HS256", payload=None):
    header = {"alg": alg, "typ": "JWT"}
    body = {"sub": "user-1", "exp": time.time() + 300}
    body.update(payload or {})
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(body).encode())}"
    if alg == "none":
        return signing_input + "."
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(sig)}"


def _auth(monkeypatch, secret=SECRET, **extra):
    monkeypatch.setenv("RIFT_SUPABASE_JWT_SECRET", secret)
    for key, value in extra.items():
        monkeypatch.setenv(key, value)


def test_valid_token_returns_sub(monkeypatch):
    _auth(monkeypatch)
    assert verify_bearer_token(f"Bearer {_token()}") == "user-1"


def test_missing_and_malformed_headers_rejected(monkeypatch):
    _auth(monkeypatch)
    for bad in (None, "", "Token abc", "Bearer", "Bearer a.b", "Bearer a.b.c.d"):
        with pytest.raises(AuthError):
            verify_bearer_token(bad)


def test_wrong_signature_rejected(monkeypatch):
    _auth(monkeypatch)
    with pytest.raises(AuthError):
        verify_bearer_token(f"Bearer {_token(secret='other-secret')}")


def test_none_algorithm_rejected(monkeypatch):
    _auth(monkeypatch)
    with pytest.raises(AuthError):
        verify_bearer_token(f"Bearer {_token(alg='none')}")


def test_foreign_algorithm_rejected(monkeypatch):
    _auth(monkeypatch)
    with pytest.raises(AuthError):
        verify_bearer_token(f"Bearer {_token(alg='RS256')}")


def test_expired_token_rejected(monkeypatch):
    _auth(monkeypatch)
    with pytest.raises(AuthError):
        verify_bearer_token(f"Bearer {_token(payload={'exp': time.time() - 3600})}")


def test_expiry_leeway_configurable(monkeypatch):
    _auth(monkeypatch, **{"RIFT_JWT_LEEWAY_S": "3600"})
    assert verify_bearer_token(f"Bearer {_token(payload={'exp': time.time() - 60})}") == "user-1"


def test_missing_sub_rejected(monkeypatch):
    _auth(monkeypatch)
    payload = {"exp": time.time() + 300}
    header = _b64(json.dumps({"alg": "HS256"}).encode())
    body = _b64(json.dumps(payload).encode())
    signing_input = f"{header}.{body}"
    sig = _b64(hmac.new(SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
    with pytest.raises(AuthError):
        verify_bearer_token(f"Bearer {signing_input}.{sig}")


def test_audience_and_issuer_enforced_when_configured(monkeypatch):
    _auth(monkeypatch, RIFT_SUPABASE_JWT_AUD="authenticated", RIFT_JWT_ISSUER="https://x.supabase.co/auth/v1")
    good = _token(payload={"aud": "authenticated", "iss": "https://x.supabase.co/auth/v1"})
    assert verify_bearer_token(f"Bearer {good}") == "user-1"
    with pytest.raises(AuthError):
        verify_bearer_token(f"Bearer {_token()}")


def test_jwt_mode_flag(monkeypatch):
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    assert jwt_mode_enabled() is False
    _auth(monkeypatch)
    assert jwt_mode_enabled() is True
