"""Central server-side configuration for optional external integrations.

All secrets are read from environment variables on the server only.
Nothing in this module exposes secret values; callers must never
serialize these dataclasses to HTTP responses or browser bundles.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _first_present(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return None


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    key: str
    key_source: str

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)


def get_supabase_config() -> SupabaseConfig | None:
    """Return server-side Supabase config, or None when not configured.

    Canonical variables are ``RIFT_SUPABASE_URL`` / ``RIFT_SUPABASE_KEY``.
    Legacy ``SUPABASE_URL`` / ``SUPABASE_*_KEY`` names are accepted as a
    fallback so existing deployments keep working. ``RIFT_`` prefixed
    values take precedence.
    """
    url = _first_present("RIFT_SUPABASE_URL", "SUPABASE_URL")
    key = _first_present(
        "RIFT_SUPABASE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
    )
    key_source = ""
    for candidate in (
        "RIFT_SUPABASE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
    ):
        value = os.getenv(candidate)
        if value is not None and value.strip() != "" and value.strip() == key:
            key_source = candidate
            break
    if not url or not key:
        return None
    return SupabaseConfig(url=url, key=key, key_source=key_source)


def supabase_status() -> dict:
    """Non-sensitive status payload safe to expose via /api/health."""
    config = get_supabase_config()
    if config is None:
        return {"configured": False}
    return {"configured": True, "url_present": True, "key_source": config.key_source}


@dataclass(frozen=True)
class BillingConfig:
    api_key: str
    store_id: str
    webhook_secret: str | None
    default_variant_id: str | None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.store_id)


def get_billing_config() -> BillingConfig | None:
    """Return Lemon Squeezy server config, or None when not configured.

    No credentials, store IDs, or variant IDs are hard-coded. Every value
    must come from the environment. Empty/absent values mean billing is
    intentionally disabled.
    """
    api_key = _first_present("RIFT_LEMON_SQUEEZY_API_KEY", "LEMON_SQUEEZY_API_KEY")
    store_id = _first_present("RIFT_LEMON_SQUEEZY_STORE_ID", "LEMON_SQUEEZY_STORE_ID")
    webhook_secret = _first_present(
        "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "LEMON_SQUEEZY_WEBHOOK_SECRET"
    )
    default_variant = _first_present(
        "RIFT_LEMON_SQUEEZY_VARIANT_ID", "LEMON_SQUEEZY_VARIANT_ID"
    )
    if not api_key or not store_id:
        return None
    return BillingConfig(
        api_key=api_key,
        store_id=store_id,
        webhook_secret=webhook_secret,
        default_variant_id=default_variant,
    )


def billing_status() -> dict:
    config = get_billing_config()
    if config is None:
        return {"configured": False, "provider": "lemon_squeezy"}
    return {
        "configured": True,
        "provider": "lemon_squeezy",
        "store_configured": True,
        "webhook_secret_configured": bool(config.webhook_secret),
        "default_variant_configured": bool(config.default_variant_id),
    }
