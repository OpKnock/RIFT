import hashlib
import hmac

import pytest

from rift.billing import (
    BillingNotConfigured,
    CheckoutRequest,
    LemonSqueezyProvider,
    parse_webhook_event,
    verify_webhook_signature,
)
from rift.settings import BillingConfig


def test_verify_webhook_signature_known_vector():
    secret = "whsec_test"
    body = b'{"meta":{"event_name":"order_created"}}'
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, expected, secret) is True
    assert verify_webhook_signature(body, expected.upper(), secret) is True
    assert verify_webhook_signature(body, "0" * 64, secret) is False


def test_verify_webhook_signature_fails_closed():
    assert verify_webhook_signature(b"body", "sig", None) is False
    assert verify_webhook_signature(b"body", None, "secret") is False
    assert verify_webhook_signature(b"", "sig", "secret") is False


def test_parse_webhook_event_supported_and_unknown():
    supported = parse_webhook_event({"meta": {"event_name": "subscription_created"}, "data": {"id": "1"}})
    assert supported["event_name"] == "subscription_created"
    assert supported["supported"] is True

    unknown = parse_webhook_event({"meta": {"event_name": "custom_thing"}, "data": {}})
    assert unknown["supported"] is False


def test_parse_webhook_event_rejects_malformed():
    with pytest.raises(ValueError):
        parse_webhook_event({"meta": {}})
    with pytest.raises(ValueError):
        parse_webhook_event({"data": {}})
    with pytest.raises(ValueError):
        parse_webhook_event([])


def test_provider_not_configured_raises(monkeypatch):
    for name in (
        "RIFT_LEMON_SQUEEZY_API_KEY",
        "RIFT_LEMON_SQUEEZY_STORE_ID",
        "LEMON_SQUEEZY_API_KEY",
        "LEMON_SQUEEZY_STORE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    provider = LemonSqueezyProvider(config=None)
    assert provider.configured is False
    with pytest.raises(BillingNotConfigured):
        provider.checkout_payload(CheckoutRequest(variant_id="1"))


def test_checkout_payload_shape_no_secrets_inside():
    config = BillingConfig(
        api_key="api-key-value",
        store_id="store-1",
        webhook_secret="wh",
        default_variant_id=None,
    )
    provider = LemonSqueezyProvider(config=config)
    payload = provider.checkout_payload(
        CheckoutRequest(variant_id="var-9", email="buyer@example.com", user_id="u-1")
    )
    assert payload["data"]["type"] == "checkouts"
    assert payload["data"]["relationships"]["store"]["data"]["id"] == "store-1"
    assert payload["data"]["relationships"]["variant"]["data"]["id"] == "var-9"
    assert "api-key-value" not in str(payload)


def test_checkout_payload_requires_variant():
    config = BillingConfig(api_key="k", store_id="s", webhook_secret=None, default_variant_id=None)
    provider = LemonSqueezyProvider(config=config)
    with pytest.raises(ValueError):
        provider.checkout_payload(CheckoutRequest(variant_id="  "))
