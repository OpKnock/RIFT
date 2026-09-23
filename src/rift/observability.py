"""Minimal production observability: request IDs + structured logs, no secrets.

Logs go to stderr as one JSON object per line. Secret-looking values are
redacted before emission. Nothing here stores tokens, API keys, or
payment secrets.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

_REDACT_KEYS = ("key", "secret", "token", "authorization", "api_key", "webhook")


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            str(key): ("[redacted]" if any(s in str(key).lower() for s in _REDACT_KEYS) else redact(value))
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact(item) for item in obj]
    if isinstance(obj, str) and len(obj) > 64:
        # Avoid dumping huge blobs into logs.
        return obj[:64] + "…[truncated]"
    return obj


def log_event(event: str, **fields: Any) -> None:
    record = {"event": event, **redact(fields)}
    try:
        sys.stderr.write(json.dumps(record, sort_keys=True) + "\n")
        sys.stderr.flush()
    except Exception:  # nosec B110 -- logging must never raise; loss is acceptable
        pass


class Timer:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.start) * 1000.0
