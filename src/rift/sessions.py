"""Cookie session store for service-token deployments (stdlib only).

Problem: the browser SPA kept the service token in localStorage, where any
XSS exfiltrates it. Sessions move the secret server-side: the browser holds
only a random session id in an HttpOnly cookie, and the server maps it to
the authenticated principal.

Scope: service-token mode only (RIFT_API_TOKEN). JWT mode keeps using
Authorization headers managed by Supabase Auth client-side. Open dev mode
needs no sessions. Sessions are in-process memory: they do not survive
restarts and are not shared across processes — documented, single-process
dev/small-deploy posture, matching the rest of the in-process platform
(rate limiter, scheduler, event bus).
"""
from __future__ import annotations

import hmac
import os
import secrets
import threading
import time

COOKIE_NAME = "rift_session"
SESSION_TTL_S = 30 * 60


def _now() -> float:
    return time.time()


class SessionStore:
    """Thread-safe in-memory session map: id -> {user_id, expires}."""

    def __init__(self, ttl_s: int = SESSION_TTL_S, max_sessions: int = 1000) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}
        self._ttl_s = ttl_s
        self._max = max_sessions

    def create(self, user_id: str | None) -> tuple[str, float]:
        """Create a session. Returns (session_id, expires_at_epoch)."""
        session_id = secrets.token_urlsafe(32)
        expires = _now() + self._ttl_s
        with self._lock:
            if len(self._sessions) >= self._max:
                # Evict the most expired entries first.
                ordered = sorted(self._sessions.items(), key=lambda kv: kv[1]["expires"])
                for key, _ in ordered[: max(1, len(self._sessions) - self._max + 1)]:
                    del self._sessions[key]
            self._sessions[session_id] = {
                "user_id": user_id,
                "created": _now(),
                "expires": expires,
            }
        return session_id, expires

    def validate(self, session_id: str | None) -> str | None:
        """Return the bound user_id (possibly None) or None when invalid.

        Expired and unknown ids both yield None (the caller cannot tell
        them apart — deliberate, to avoid an oracle). Valid use slides
        the expiry (sliding 30-minute sessions).
        """
        if not session_id or not isinstance(session_id, str):
            return None
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if record["expires"] < _now():
                del self._sessions[session_id]
                return None
            record["expires"] = _now() + self._ttl_s
            return record["user_id"]

    def has(self, session_id: str | None) -> bool:
        """Whether a live session exists (for tests/diagnostics)."""
        with self._lock:
            record = self._sessions.get(session_id or "")
            return record is not None and record["expires"] >= _now()

    def destroy(self, session_id: str | None) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def stats(self) -> dict:
        with self._lock:
            now = _now()
            live = sum(1 for r in self._sessions.values() if r["expires"] >= now)
            return {"sessions": len(self._sessions), "live": live}


def parse_session_cookie(cookie_header: str | None) -> str | None:
    """Extract the rift_session value from a Cookie header (or None)."""
    if not cookie_header or not isinstance(cookie_header, str):
        return None
    for part in cookie_header.split(";"):
        name, _, value = part.partition("=")
        if name.strip() == COOKIE_NAME and value.strip():
            return value.strip()
    return None


def verify_service_token(token: str | None) -> bool:
    """Constant-time comparison against the configured service token."""
    from .auth import service_token_configured
    expected = service_token_configured()
    if expected is None or not token:
        return False
    return hmac.compare_digest(token, expected)


def session_cookie_header(session_id: str, expires_at: float, secure: bool) -> str:
    """Build the Set-Cookie value (HttpOnly always; Secure when configured)."""
    from datetime import datetime, timezone
    parts = [
        f"{COOKIE_NAME}={session_id}",
        "Path=/api/",
        "HttpOnly",
        "SameSite=Lax",
        f"Expires={datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_session_cookie_header(secure: bool) -> str:
    parts = [f"{COOKIE_NAME}=", "Path=/api/", "HttpOnly", "SameSite=Lax",
             "Expires=Thu, 01 Jan 1970 00:00:00 GMT", "Max-Age=0"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def cookie_secure() -> bool:
    return os.getenv("RIFT_COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes")


# Canonical process-wide store.
sessions = SessionStore()
