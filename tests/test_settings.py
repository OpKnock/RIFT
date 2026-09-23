import os

from rift import settings


def _clear_env(monkeypatch, *names):
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_supabase_missing_means_not_configured(monkeypatch):
    _clear_env(
        monkeypatch,
        "RIFT_SUPABASE_URL",
        "RIFT_SUPABASE_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
    )
    assert settings.get_supabase_config() is None
    assert settings.supabase_status() == {"configured": False}


def test_supabase_canonical_precedence_and_fallback(monkeypatch):
    _clear_env(
        monkeypatch,
        "RIFT_SUPABASE_URL",
        "RIFT_SUPABASE_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://legacy.example.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "legacy-key")
    config = settings.get_supabase_config()
    assert config is not None and config.url == "https://legacy.example.co"

    monkeypatch.setenv("RIFT_SUPABASE_URL", "https://canonical.example.co")
    monkeypatch.setenv("RIFT_SUPABASE_KEY", "canonical-key")
    config = settings.get_supabase_config()
    assert config is not None
    assert config.url == "https://canonical.example.co"
    assert config.key == "canonical-key"
    assert config.key_source == "RIFT_SUPABASE_KEY"


def test_supabase_status_never_leaks_key(monkeypatch):
    _clear_env(
        monkeypatch,
        "RIFT_SUPABASE_URL",
        "RIFT_SUPABASE_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
    )
    monkeypatch.setenv("RIFT_SUPABASE_URL", "https://x.example.co")
    monkeypatch.setenv("RIFT_SUPABASE_KEY", "super-secret-value")
    status = settings.supabase_status()
    assert status["configured"] is True
    assert "super-secret-value" not in str(status)


def test_billing_missing_means_not_configured(monkeypatch):
    _clear_env(
        monkeypatch,
        "RIFT_LEMON_SQUEEZY_API_KEY",
        "RIFT_LEMON_SQUEEZY_STORE_ID",
        "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET",
        "RIFT_LEMON_SQUEEZY_VARIANT_ID",
        "LEMON_SQUEEZY_API_KEY",
        "LEMON_SQUEEZY_STORE_ID",
        "LEMON_SQUEEZY_WEBHOOK_SECRET",
        "LEMON_SQUEEZY_VARIANT_ID",
    )
    assert settings.get_billing_config() is None
    assert settings.billing_status()["configured"] is False


def test_billing_status_never_leaks_secret(monkeypatch):
    _clear_env(
        monkeypatch,
        "RIFT_LEMON_SQUEEZY_API_KEY",
        "RIFT_LEMON_SQUEEZY_STORE_ID",
        "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET",
        "RIFT_LEMON_SQUEEZY_VARIANT_ID",
        "LEMON_SQUEEZY_API_KEY",
        "LEMON_SQUEEZY_STORE_ID",
        "LEMON_SQUEEZY_WEBHOOK_SECRET",
        "LEMON_SQUEEZY_VARIANT_ID",
    )
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "live-secret-key")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "12345")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh-secret")
    status = settings.billing_status()
    assert status["configured"] is True
    assert "live-secret-key" not in str(status)
    assert "wh-secret" not in str(status)
