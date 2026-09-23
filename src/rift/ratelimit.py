"""In-process fixed-window rate limiter (stdlib only, thread-safe).

Defense-in-depth behind edge rate limiting (e.g. Cloudflare): the edge
absorbs distributed abuse; this module stops a single client from
monopolizing the simulator loop. Disabled unless
``RIFT_RATE_LIMIT_ENABLED=true`` so local development and the test suite
stay frictionless; production deployments should enable it AND set edge
rules (see docs/deployment.md).

Scopes: ``default`` for general ``/api/*`` traffic, ``execute`` with a
deliberately lower budget for the expensive server-side execution
endpoint. Static assets are never counted.
"""
from __future__ import annotations

import os
import threading
import time


def enabled() -> bool:
    return os.getenv("RIFT_RATE_LIMIT_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (ValueError, AttributeError):
        return default
    return value if value > 0 else default


def default_budget() -> tuple[int, int]:
    """(max_requests, window_seconds) for general API traffic."""
    return (_int_env("RIFT_RATE_LIMIT_DEFAULT_N", 120), _int_env("RIFT_RATE_LIMIT_DEFAULT_WINDOW_S", 60))


def execute_budget() -> tuple[int, int]:
    """(max_requests, window_seconds) for the expensive execute endpoint."""
    return (_int_env("RIFT_RATE_LIMIT_EXECUTE_N", 20), _int_env("RIFT_RATE_LIMIT_EXECUTE_WINDOW_S", 60))


def scope_for_path(path: str) -> str | None:
    """Map a request path to a limit scope, or None when uncounted."""
    route = path.split("?")[0]
    if not route.startswith("/api/"):
        return None
    if route.endswith("/execute"):
        return "execute"
    return "default"


class RateLimiter:
    """Fixed-window counters keyed by (scope, client). Thread-safe."""

    _MAX_BUCKETS = 20000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}

    def check(self, key: str, scope: str, limit: int, window_s: int, *, now: float | None = None) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)``.

        ``retry_after_seconds`` is 0 when allowed, otherwise the seconds
        until the current window resets (at least 1).
        """
        current = time.monotonic() if now is None else now
        bucket = (scope, key)
        with self._lock:
            self._purge_locked(current)
            start, count = self._buckets.get(bucket, (current, 0))
            if current - start >= window_s:
                start, count = current, 0
            if count < limit:
                self._buckets[bucket] = (start, count + 1)
                return True, 0
            retry_after = max(1, int(start + window_s - current))
            # Count the rejected hit too so sustained abuse keeps backing off.
            self._buckets[bucket] = (start, count + 1)
            return False, retry_after

    def _purge_locked(self, current: float) -> None:
        # Windows are caller-supplied per scope, so expiry must be generous:
        # drop buckets idle for over an hour, then enforce the hard cap.
        stale = [k for k, (start, _) in self._buckets.items() if current - start > 3600]
        for key in stale:
            del self._buckets[key]
        if len(self._buckets) > self._MAX_BUCKETS:
            oldest = sorted(self._buckets, key=lambda k: self._buckets[k][0])
            for key in oldest[: len(self._buckets) - self._MAX_BUCKETS]:
                del self._buckets[key]

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


_limiter = RateLimiter()


def reset() -> None:
    """Clear all buckets (tests + operator reset)."""
    _limiter.reset()


def check_request(client: str, path: str) -> tuple[bool, int, str | None]:
    """Rate-limit one request. Returns ``(allowed, retry_after_s, scope)``."""
    scope = scope_for_path(path)
    if scope is None:
        return True, 0, None
    if scope == "execute":
        limit, window = execute_budget()
    else:
        limit, window = default_budget()
    allowed, retry_after = _limiter.check(client, scope, limit, window)
    return allowed, retry_after, scope
