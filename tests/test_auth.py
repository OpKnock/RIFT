from rift import auth


def test_open_mode_without_token(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    assert auth.is_authorized({}) is True


def test_bearer_gate(monkeypatch):
    monkeypatch.setenv("RIFT_API_TOKEN", "secret-token")
    assert auth.is_authorized({"Authorization": "Bearer secret-token"}) is True
    assert auth.is_authorized({"Authorization": "Bearer wrong"}) is False
    assert auth.is_authorized({}) is False


def test_owner_mismatch_rules():
    assert auth.owner_mismatch(None, None) is False
    assert auth.owner_mismatch(None, "a") is False
    assert auth.owner_mismatch("a", "a") is False
    assert auth.owner_mismatch("a", "b") is True
    # Fail closed: owned row + anonymous caller.
    assert auth.owner_mismatch("a", None) is True


def test_extract_user_id_shapes():
    assert auth.extract_user_id({"user_id": "u-1"}) == "u-1"
    assert auth.extract_user_id(None, {"user_id": ["u-2"]}) is None
    assert auth.extract_user_id(None, {"user_id": "u-2"}) == "u-2"
    assert auth.extract_user_id({"user": {"id": "u-3"}}) == "u-3"
