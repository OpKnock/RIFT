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
ALLOWED_EVENT_PREFIXES = ("order_", "subscription_", "license_")


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
    return {
        "event_name": event_name,
        "supported": supported,
        "custom_data": meta.get("custom_data") or {},
        "data": payload.get("data") or {},
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
        http_request = urllib.request.Request(
            f"{LEMON_SQUEEZY_API_BASE}/checkouts",
            data=body,
            method="POST",
            headers={
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
                "Authorization": f"Bearer {config.api_key}",
            },
        )
        with urllib.request.urlopen(http_request, timeout=timeout_s) as response:
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
