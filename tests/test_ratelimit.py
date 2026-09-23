"""Rate limiter tests: budgets, scopes, windows, and the disabled default."""
from rift import ratelimit
from rift.ratelimit import RateLimiter


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RIFT_RATE_LIMIT_ENABLED", raising=False)
    assert ratelimit.enabled() is False


def test_fixed_window_budget_and_retry_after():
    limiter = RateLimiter()
    for _ in range(3):
        allowed, retry = limiter.check("client", "default", 3, 60, now=1000.0)
        assert allowed and retry == 0
    allowed, retry = limiter.check("client", "default", 3, 60, now=1000.0)
    assert not allowed and retry > 0


def test_window_resets():
    limiter = RateLimiter()
    assert limiter.check("c", "default", 1, 60, now=1000.0)[0] is True
    assert limiter.check("c", "default", 1, 60, now=1000.0)[0] is False
    assert limiter.check("c", "default", 1, 60, now=1070.0)[0] is True


def test_scopes_are_independent():
    limiter = RateLimiter()
    assert limiter.check("c", "default", 1, 60, now=1000.0)[0] is True
    assert limiter.check("c", "default", 1, 60, now=1000.0)[0] is False
    assert limiter.check("c", "execute", 1, 60, now=1000.0)[0] is True


def test_clients_are_independent():
    limiter = RateLimiter()
    assert limiter.check("a", "default", 1, 60, now=1000.0)[0] is True
    assert limiter.check("b", "default", 1, 60, now=1000.0)[0] is True


def test_scope_routing():
    assert ratelimit.scope_for_path("/api/experiments/123/execute") == "execute"
    assert ratelimit.scope_for_path("/api/demo") == "default"
    assert ratelimit.scope_for_path("/index.html") is None
    assert ratelimit.scope_for_path("/") is None


def test_env_budgets(monkeypatch):
    monkeypatch.setenv("RIFT_RATE_LIMIT_DEFAULT_N", "5")
    monkeypatch.setenv("RIFT_RATE_LIMIT_EXECUTE_N", "2")
    assert ratelimit.default_budget()[0] == 5
    assert ratelimit.execute_budget()[0] == 2
