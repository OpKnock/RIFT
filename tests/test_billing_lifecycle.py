from rift.billing import (
    idempotency_key,
    is_entitled,
    subscription_update_from_event,
    webhook_event_id,
)


def test_event_id_and_idempotency():
    payload = {"meta": {"event_name": "subscription_created"}, "data": {"id": "sub-1"}}
    assert webhook_event_id(payload) == "sub-1"
    assert idempotency_key(payload) == "subscription_created:sub-1"
    assert webhook_event_id({}) is None
    assert idempotency_key({}) is None


def test_entitlement_mapping():
    assert is_entitled("active") is True
    assert is_entitled("trialing") is True
    assert is_entitled("past_due") is True
    assert is_entitled("cancelled") is False
    assert is_entitled("expired") is False
    assert is_entitled("unpaid") is False
    assert is_entitled(None) is False
    assert is_entitled("") is False


def test_subscription_lifecycle_mapping():
    event = {
        "event_name": "subscription_cancelled",
        "custom_data": {},
        "data": {"id": "sub-9", "attributes": {"status": "cancelled"}},
    }
    update = subscription_update_from_event(event)
    assert update is not None
    assert update["lemon_subscription_id"] == "sub-9"
    assert update["status"] == "cancelled"
    assert is_entitled(update["status"]) is False

    active = {
        "event_name": "subscription_created",
        "custom_data": {"user_id": "u-1"},
        "data": {"id": "sub-1", "attributes": {"status": "active"}},
    }
    update = subscription_update_from_event(active)
    assert update is not None and is_entitled(update["status"]) is True


def test_non_subscription_events_return_none():
    assert subscription_update_from_event({"event_name": "order_created", "data": {}}) is None
    assert subscription_update_from_event({"event_name": "subscription_created", "data": {}}) is None
