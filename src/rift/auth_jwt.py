"""Supabase Auth JWT verification (stdlib only, HS256).

Trust chain this module enforces:

    Authorization: Bearer <jwt>
      -> signature verified with RIFT_SUPABASE_JWT_SECRET (HS256 only)
      -> exp/nbf enforced (configurable leeway)
      -> optional aud/iss enforced when configured
      -> sub becomes the RIFT user_id

When JWT mode is active (secret configured), caller-supplied ``user_id``
values in bodies or query strings are IGNORED entirely — the server
determines identity from the verified token. This closes the
``?user_id=user-a`` → ``?user_id=user-b`` forgery class.

Supabase Auth issues HS256 JWTs signed with the project's JWT secret; that
secret goes in RIFT_SUPABASE_JWT_SECRET on the server only. Asymmetric
(JWKS) project setups must verify at the edge or extend this module —
never fall back to trusting unverified claims.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


class AuthError(Exception):
    """Raised when a bearer token is missing, malformed, or untrusted."""


def jwt_mode_enabled() -> bool:
    return bool(os.getenv("RIFT_SUPABASE_JWT_SECRET", "").strip())


def _secret() -> str:
    return os.getenv("RIFT_SUPABASE_JWT_SECRET", "").strip()


def _leeway_s() -> float:
    try:
        return max(0.0, float(os.getenv("RIFT_JWT_LEEWAY_S", "30")))
    except ValueError:
        return 30.0


def _b64url_decode(segment: str) -> bytes:
    try:
        padded = segment + "=" * (-len(segment) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise AuthError("malformed token encoding") from exc


def verify_bearer_token(authorization: str | None, *, now: float | None = None) -> str:
    """Verify ``Authorization: Bearer <jwt>``; return the ``sub`` claim.

    Raises AuthError on any failure (missing header, bad shape, non-HS256
    ``alg`` — including ``none`` — bad signature, missing/expired/invalid
    claims). Callers map AuthError to HTTP 401 without echoing details.
    """
    secret = _secret()
    if not secret:
        raise AuthError("jwt verification not configured")
    if not authorization or not isinstance(authorization, str):
        raise AuthError("missing authorization")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("malformed authorization")
    token = token.strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    header_segment, payload_segment, signature_segment = parts
    try:
        header = json.loads(_b64url_decode(header_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AuthError("malformed token header") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        # Explicitly rejects "none" and asymmetric algs: this verifier only
        # speaks HS256 with the configured project secret.
        raise AuthError("unsupported token algorithm")
    try:
        signature = _b64url_decode(signature_segment)
    except AuthError as exc:
        raise AuthError("malformed token signature") from exc
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise AuthError("untrusted token signature")
    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AuthError("malformed token claims") from exc
    if not isinstance(payload, dict):
        raise AuthError("malformed token claims")
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise AuthError("missing subject")
    current = time.time() if now is None else now
    leeway = _leeway_s()
    exp = payload.get("exp")
    if exp is not None:
        try:
            exp_f = float(exp)
        except (TypeError, ValueError) as exc:
            raise AuthError("invalid expiry") from exc
        if current > exp_f + leeway:
            raise AuthError("expired token")
    nbf = payload.get("nbf")
    if nbf is not None:
        try:
            nbf_f = float(nbf)
        except (TypeError, ValueError) as exc:
            raise AuthError("invalid not-before") from exc
        if current < nbf_f - leeway:
            raise AuthError("token not yet valid")
    expected_aud = os.getenv("RIFT_SUPABASE_JWT_AUD", "").strip()
    if expected_aud and payload.get("aud") != expected_aud:
        raise AuthError("unexpected audience")
    expected_iss = os.getenv("RIFT_JWT_ISSUER", "").strip()
    if expected_iss and payload.get("iss") != expected_iss:
        raise AuthError("unexpected issuer")
    return sub
