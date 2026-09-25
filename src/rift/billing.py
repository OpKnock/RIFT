"""Lemon Squeezy monetization boundary.

Production-ready provider interface with no hard-coded credentials,
store IDs, variant IDs, or products. Everything comes from server-side
environment variables (see :mod:`rift.settings`).

When credentials are absent the provider reports ``configured is False``
and HTTP endpoints return ``503 billing_not_configured`` instead of
inventing a checkout. This keeps billing outside the simulation core
until a provider is intentionally configured.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from .settings import BillingConfig, get_billing_config

LEMON_SQUEEZY_API_BASE = "https://api.lemonsqueezy.com/v1"
ALLOWED_EVENT_PREFIXES = ("order_", "subscription_")

# Subscription states that grant entitlement. Everything else (cancelled,
# expired, unpaid, paused) is fail-closed: no access.
ENTITLED_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing", "past_due", "on_trial"})


@dataclass(frozen=True)
class CheckoutRequest:
    variant_id: str
    email: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] | None = None


def verify_webhook_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    """Verify a Lemon Squeezy ``X-Signature`` header.

    Lemon Squeezy signs the raw request body with HMAC-SHA256 using the
    webhook secret and sends the hex digest as ``X-Signature``. Returns
    ``False`` when any input is missing so callers fail closed.
    """
    if not raw_body or not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def parse_webhook_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the shape of a Lemon Squeezy webhook payload.

    Raises ``ValueError`` on malformed payloads. Unknown event names are
    passed through with ``supported=False`` so new Lemon Squeezy event
    types do not crash the endpoint.
    """
    if not isinstance(payload, dict):
        raise ValueError("webhook payload must be a JSON object")
    meta = payload.get("meta")
    if not isinstance(meta, dict) or not meta.get("event_name"):
        raise ValueError("webhook payload is missing meta.event_name")
    event_name = str(meta["event_name"])
    supported = event_name.startswith(ALLOWED_EVENT_PREFIXES)
    data = payload.get("data") or {}
    return {
        "event_name": event_name,
        "supported": supported,
        "custom_data": meta.get("custom_data") or {},
        "data": data,
        "provider_event_id": webhook_event_id(payload),
        "idempotency_key": idempotency_key(payload),
    }


def webhook_event_id(payload: dict[str, Any]) -> str | None:
    """Extract a stable provider event id for idempotent processing.

    Prefers ``data.id`` (Lemon Squeezy resource id), falling back to the
    webhook ``meta.webhook_id`` when present. Returns None when neither
    exists — callers must then refuse to dedup blindly.
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("webhook_id", "event_id", "id"):
            if meta.get(key):
                return str(meta[key])
    return None


def idempotency_key(payload: dict[str, Any]) -> str | None:
    try:
        event = payload.get("meta", {}).get("event_name") if isinstance(payload, dict) else None
    except AttributeError:
        return None
    provider_id = webhook_event_id(payload)
    if not event or not provider_id:
        return None
    return f"{event}:{provider_id}"


def is_entitled(subscription_status: str | None) -> bool:
    """Derive entitlement from verified server-side subscription state.

    Never trust browser-supplied status; callers must pass the status read
    from the server-side subscription mirror.
    """
    if not subscription_status or not isinstance(subscription_status, str):
        return False
    return subscription_status.strip().lower() in ENTITLED_SUBSCRIPTION_STATUSES


def subscription_update_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map a validated webhook event onto a subscription-mirror update.

    Returns None for non-subscription events (orders etc. are audit-logged
    only). Pure function — fully unit-testable without network or DB.
    Handles creation, update, cancellation, expiration, and payment
    recovery via the status field; unknown shapes return None rather than
    corrupting state.
    """
    name = event.get("event_name", "")
    if not isinstance(name, str) or not name.startswith("subscription_"):
        return None
    data = event.get("data") or {}
    attributes = data.get("attributes") or {} if isinstance(data, dict) else {}
    subscription_id = (data.get("id") if isinstance(data, dict) else None) or attributes.get("first_subscription_item") or attributes.get("subscription_id")
    status = attributes.get("status") if isinstance(attributes, dict) else None
    if not subscription_id or not status:
        # Fall back to explicit custom mapping fields some setups send.
        custom = event.get("custom_data") or {}
        subscription_id = subscription_id or custom.get("subscription_id")
        status = status or custom.get("status")
    if not subscription_id or not status:
        return None
    return {
        "lemon_subscription_id": str(subscription_id),
        "status": str(status).strip().lower(),
        "variant_id": str(attributes.get("variant_id") or (event.get("custom_data") or {}).get("variant_id") or "") or None,
        "renews_at": attributes.get("renews_at") if isinstance(attributes, dict) else None,
        "ends_at": attributes.get("ends_at") if isinstance(attributes, dict) else None,
        "raw": data,
    }


class BillingNotConfigured(RuntimeError):
    pass


class LemonSqueezyProvider:
    """Server-side Lemon Squeezy provider. Dependency-free (stdlib HTTP)."""

    def __init__(self, config: BillingConfig | None = None):
        self.config = config if config is not None else get_billing_config()

    @property
    def configured(self) -> bool:
        return self.config is not None and self.config.configured

    def _require_config(self) -> BillingConfig:
        if not self.configured or self.config is None:
            raise BillingNotConfigured(
                "Billing is not configured. Set RIFT_LEMON_SQUEEZY_API_KEY "
                "and RIFT_LEMON_SQUEEZY_STORE_ID on the server."
            )
        return self.config

    def checkout_payload(self, request: CheckoutRequest) -> dict[str, Any]:
        config = self._require_config()
        if not request.variant_id or not request.variant_id.strip():
            raise ValueError("variant_id is required to create a checkout")
        attributes: dict[str, Any] = {
            "checkout_data": {
                "custom": {
                    "user_id": request.user_id,
                    "variant_id": request.variant_id,
                    **(request.metadata or {}),
                }
            }
        }
        if request.email:
            attributes["checkout_data"]["email"] = request.email
        if request.user_id and not request.email:
            attributes["checkout_data"]["custom"]["buyer_user_id"] = request.user_id
        return {
            "data": {
                "type": "checkouts",
                "attributes": attributes,
                "relationships": {
                    "store": {"data": {"type": "stores", "id": config.store_id}},
                    "variant": {
                        "data": {"type": "variants", "id": request.variant_id}
                    },
                },
            }
        }

    def create_checkout(self, request: CheckoutRequest, timeout_s: int = 15) -> dict[str, Any]:
        """Create a hosted checkout via the Lemon Squeezy API.

        Returns ``{"checkout_url": ..., "checkout_id": ...}``. Performs a
        live HTTPS call and therefore requires real credentials; unit
        tests cover ``checkout_payload`` without network access.
        """
        config = self._require_config()
        body = json.dumps(self.checkout_payload(request)).encode("utf-8")
        url = f"{LEMON_SQUEEZY_API_BASE}/checkouts"
        if not url.startswith("https://api.lemonsqueezy.com/"):
            raise RuntimeError("refusing to call an unexpected billing endpoint")
        http_request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
                "Authorization": f"Bearer {config.api_key}",
            },
        )
        with urllib.request.urlopen(http_request, timeout=timeout_s) as response:  # nosec B310 -- module-constant endpoint; nosemgrep -- allowlisted constant endpoint
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") or {}
        attributes = data.get("attributes") or {}
        url = attributes.get("url")
        if not url:
            raise RuntimeError("Lemon Squeezy did not return a checkout URL")
        return {"checkout_url": url, "checkout_id": data.get("id")}

    def verify_signature(self, raw_body: bytes, signature: str | None) -> bool:
        config = self._require_config()
        return verify_webhook_signature(raw_body, signature, config.webhook_secret)
