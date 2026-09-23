"""Authentication + multi-tenancy boundary.

Current product shape (honest, no fake auth):

- The lab engine itself is anonymous and offline.
- Persistence/billing endpoints are server-side. If ``RIFT_API_TOKEN`` is
  set, those endpoints require ``Authorization: Bearer <token>`` (service
  credential for a single-tenant deployment or a fronting proxy).
- If ``RIFT_API_TOKEN`` is unset, the server runs in documented
  single-tenant dev mode (no gate) so local development stays frictionless.
- Per-user isolation: rows carry ``user_id``. When a caller supplies
  ``user_id`` (body or ``?user_id=``), the server writes it and enforces
  equality on reads. Full unforgeable multi-tenancy requires Supabase Auth
  JWT verification in front of this server — documented as an external
  blocker in docs/security.md, not claimed here.

Never rely on frontend route hiding as security: every check below runs
server-side, and authorization tests cover cross-user denial.
"""
from __future__ import annotations

import os


def service_token_configured() -> str | None:
    token = os.getenv("RIFT_API_TOKEN")
    if token is not None and token.strip() != "":
        return token.strip()
    return None


def require_user_id_enforced() -> bool:
    """True when callers must assert user_id (RIFT_REQUIRE_USER_ID=true)."""
    return os.getenv("RIFT_REQUIRE_USER_ID", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def extract_bearer(headers) -> str | None:
    """Accept real HTTPMessage headers or a plain dict (tests)."""
    if headers is None:
        return None
    get = getattr(headers, "get", None)
    value = get("Authorization") if callable(get) else headers.get("Authorization")
    if not value or not isinstance(value, str):
        return None
    scheme, _, credential = value.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        return None
    return credential.strip()


def is_authorized(headers) -> bool:
    expected = service_token_configured()
    if expected is None:
        return True  # dev mode: no gate configured
    return extract_bearer(headers) == expected


def extract_user_id(body: dict | None, query: dict | None = None) -> str | None:
    for source in (body, query):
        if isinstance(source, dict):
            for key in ("user_id", "owner_id"):
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    candidate = value.strip()
                    if len(candidate) <= 128:
                        return candidate
                # Accept a nested {"user": {"id": ...}} shape too.
                if isinstance(source.get("user"), dict):
                    nested = source["user"].get("id")
                    if isinstance(nested, str) and nested.strip() and len(nested) <= 128:
                        return nested.strip()
    return None


def owner_mismatch(stored_user_id: str | None, caller_user_id: str | None) -> bool:
    """True when a row owned by someone else is requested by this caller.

    When the caller asserts no user_id, we cannot prove ownership — the
    server then refuses to return rows that carry an owner (fail closed).
    Rows without an owner remain readable so legacy ownerless experiments
    keep working in dev mode.
    """
    if not stored_user_id:
        return False
    return caller_user_id != stored_user_id
