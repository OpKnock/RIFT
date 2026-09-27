"""Route handlers (split verbatim from api.py; see package README)."""
from __future__ import annotations

from .support import _apply_subscription_update, _remember_webhook_key, _seen_webhook_key
from rift.billing import (BillingNotConfigured, CheckoutRequest, LemonSqueezyProvider, idempotency_key as billing_idempotency_key, is_entitled, parse_webhook_event, subscription_update_from_event, verify_webhook_signature, webhook_event_id)
from rift.supabase_store import SupabaseStore
from rift.settings import billing_status, get_billing_config, supabase_status
import json
from rift.observability import log_event


def get_api_billing_status(h, request_id, timer, path, query):
    """Route if path == "/api/billing/status": (moved verbatim from api.py do_GET)."""
    h._send(200, json.dumps(billing_status()), request_id=request_id)
    h._finish(timer, request_id, "GET", path, 200)
    return True
    return False


def get_api_billing_entitlement(h, request_id, timer, path, query):
    """Route if path == "/api/billing/entitlement": (moved verbatim from api.py do_GET)."""
    caller, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    store = SupabaseStore()
    if not store.configured:
        h._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 503, "persistence_not_configured")
        return True
    if not caller:
        h._send(400, json.dumps({"error": "user_id is required"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 400, "validation")
        return True
    try:
        result = store.latest_subscription_for_user(caller)
        rows = result.data or []
        status = rows[0].get("status") if rows else "none"
        entitled = is_entitled(status) if rows else False
        h._send(200, json.dumps({"entitled": entitled, "status": status}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        log_event("dependency_failure", request_id=request_id, dependency="supabase")
        h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 502, "persistence_error")
    return True
    return False


def post_api_billing_checkout(h, request_id, timer, path, query):
    """Route if path == "/api/billing/checkout": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    _, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    provider = LemonSqueezyProvider()
    if not provider.configured:
        h._send(503, json.dumps({
            "error": "billing_not_configured",
            "provider": "lemon_squeezy",
            "detail": "Set RIFT_LEMON_SQUEEZY_API_KEY and RIFT_LEMON_SQUEEZY_STORE_ID on the server.",
        }), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 503, "billing_not_configured")
        return True
    variant_id = (body.get("variant_id") if isinstance(body, dict) else None) or (
        provider.config.default_variant_id if provider.config else None)
    if isinstance(variant_id, int):
        variant_id = str(variant_id)
    if not isinstance(variant_id, str) or not variant_id.strip():
        h._send(400, json.dumps({"error": "variant_id is required"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    variant_id = variant_id.strip()
    email = body.get("email") if isinstance(body, dict) else None
    if email is not None and (not isinstance(email, str) or len(email) > 320 or "@" not in email):
        h._send(400, json.dumps({"error": "invalid email"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    try:
        checkout = provider.create_checkout(CheckoutRequest(
            variant_id=str(variant_id),
            email=email,
            user_id=(body.get("user_id") if isinstance(body, dict) else None),
            metadata=(body.get("metadata") if isinstance(body, dict) else None),
        ))
        h._send(201, json.dumps(checkout), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except BillingNotConfigured:
        h._send(503, json.dumps({"error": "billing_not_configured"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 503, "billing_not_configured")
    except ValueError as exc:
        h._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
    except Exception:
        log_event("dependency_failure", request_id=request_id, dependency="lemon_squeezy")
        h._send(502, json.dumps({"error": "billing_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 502, "billing_error")
    return True

    return False


def post_api_billing_webhook(h, request_id, timer, path, query):
    """Route if path == "/api/billing/webhook": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    config = get_billing_config()
    if config is None or not config.webhook_secret:
        h._send(503, json.dumps({
            "error": "billing_webhook_not_configured",
            "detail": "Set RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET on the server before receiving webhooks.",
        }), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 503, "billing_not_configured")
        return True
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    signature = h.headers.get("X-Signature")
    if not verify_webhook_signature(raw, signature, config.webhook_secret):
        h._send(401, json.dumps({"error": "invalid_signature"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    try:
        event = parse_webhook_event(body)
    except ValueError as exc:
        h._send(400, json.dumps({"error": "invalid_webhook", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    key = billing_idempotency_key(body) or event.get("idempotency_key")
    if _seen_webhook_key(key):
        h._send(200, json.dumps({"received": True, "event": event["event_name"], "duplicate": True}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 200)
        return True
    try:
        store = SupabaseStore()
        if store.configured:
            if key:
                try:
                    existing = store.find_billing_event(key).data or []
                    if existing:
                        # Resume, don't short-circuit: the event row may
                        # have been recorded while the subscription
                        # side effect below failed (502). Re-apply the
                        # update idempotently before acknowledging.
                        if not _apply_subscription_update(store, event, request_id):
                            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                            h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                            return True
                        _remember_webhook_key(key)
                        h._send(200, json.dumps({"received": True, "event": event["event_name"], "duplicate": True}), request_id=request_id)
                        h._finish(timer, request_id, "POST", path, 200)
                        return True
                except Exception:
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
            try:
                store.record_billing_event({
                    "event_name": event["event_name"],
                    "supported": event["supported"],
                    "provider_event_id": webhook_event_id(body),
                    "idempotency_key": key,
                    "lemon_customer_id": (event.get("data") or {}).get("id") if event["event_name"].startswith("order_") else None,
                    "payload": body,
                })
            except Exception as exc:
                # The billing_events table carries a UNIQUE constraint
                # on idempotency_key (migration 004): a concurrent
                # duplicate delivery surfaces here as a constraint
                # violation. Like the durable-duplicate path above, the
                # subscription side effect must be resumed (not skipped)
                # before acknowledging: the conflicting row proves the
                # event was recorded, not that it was processed.
                if "duplicate" in str(exc).lower() or "unique" in str(exc).lower() or "23505" in str(exc):
                    if not _apply_subscription_update(store, event, request_id):
                        h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                        h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                        return True
                    _remember_webhook_key(key)
                    h._send(200, json.dumps({"received": True, "event": event["event_name"], "duplicate": True}), request_id=request_id)
                    h._finish(timer, request_id, "POST", path, 200)
                    return True
                # Durable processing failed: return 502 so Lemon Squeezy
                # retries instead of believing the event was recorded.
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
                h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                return True
            if not _apply_subscription_update(store, event, request_id):
                h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                return True
    except Exception:
        # Unconfigured store: no durability possible; accept as
        # best-effort dev-mode receipt (documented). Any configured-
        # store failure above already returned 502.
        log_event("dependency_failure", request_id=request_id, dependency="supabase")
    _remember_webhook_key(key)
    h._send(200, json.dumps({"received": True, "event": event["event_name"]}), request_id=request_id)
    h._finish(timer, request_id, "POST", path, 200)
    return True

# POST endpoints for Phase 10
    return False
