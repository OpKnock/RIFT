from __future__ import annotations

import os
from typing import Any

from .settings import get_supabase_config


class SupabaseStore:
    """Optional server-side persistence adapter.

    RIFT remains fully local when Supabase variables are absent. Any key
    (service-role or publishable) must remain server-side; browser clients
    must never receive it. RLS policies in
    ``backend/supabase/migrations/`` enforce per-user access.
    """

    def __init__(self, url: str | None = None, key: str | None = None):
        if url is not None or key is not None:
            self.url = url or os.getenv("RIFT_SUPABASE_URL")
            self.key = key or os.getenv("RIFT_SUPABASE_KEY")
        else:
            config = get_supabase_config()
            self.url = config.url if config else None
            self.key = config.key if config else None
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)

    def client(self):
        if not self.configured:
            raise RuntimeError(
                "Supabase is not configured. "
                "Set RIFT_SUPABASE_URL and RIFT_SUPABASE_KEY in a trusted "
                "server environment."
            )
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise RuntimeError(
                    "Install the optional supabase dependency: "
                    "pip install -e '.[supabase]'"
                ) from exc
            self._client = create_client(self.url, self.key)
        return self._client

    def create_experiment(self, payload: dict[str, Any]):
        return self.client().table("experiments").insert(payload).execute()

    def create_run(self, payload: dict[str, Any]):
        return self.client().table("experiment_runs").insert(payload).execute()

    def get_experiment(self, experiment_id: str):
        return (
            self.client()
            .table("experiments")
            .select("*")
            .eq("id", experiment_id)
            .single()
            .execute()
        )

    def get_run(self, run_id: str):
        return (
            self.client()
            .table("experiment_runs")
            .select("*")
            .eq("id", run_id)
            .single()
            .execute()
        )

    def list_runs(self, experiment_id: str):
        return (
            self.client()
            .table("experiment_runs")
            .select("*")
            .eq("experiment_id", experiment_id)
            .order("created_at", desc=True)
            .execute()
        )

    def record_billing_event(self, payload: dict[str, Any]):
        """Best-effort billing webhook audit log (migration 003/004)."""
        return self.client().table("billing_events").insert(payload).execute()

    def find_billing_event(self, idempotency_key: str):
        return (
            self.client()
            .table("billing_events")
            .select("id,event_name")
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )

    def upsert_subscription(self, payload: dict[str, Any]):
        return (
            self.client()
            .table("billing_subscriptions")
            .upsert(payload, on_conflict="lemon_subscription_id")
            .execute()
        )

    def latest_subscription_for_user(self, user_id: str):
        return (
            self.client()
            .table("billing_subscriptions")
            .select("status,lemon_subscription_id,variant_id,renews_at,ends_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
