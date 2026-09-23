from __future__ import annotations
import os
from typing import Any

class SupabaseStore:
    """Optional persistence adapter.

    RIFT remains fully local when Supabase variables are absent. The service key,
    if used, must remain server-side; browser clients should use publishable keys
    with Auth/RLS.
    """
    def __init__(self):
        self.url=os.getenv("RIFT_SUPABASE_URL")
        self.key=os.getenv("RIFT_SUPABASE_KEY")
        self._client=None

    @property
    def configured(self)->bool:
        return bool(self.url and self.key)

    def client(self):
        if not self.configured:
            raise RuntimeError("Supabase is not configured. Set RIFT_SUPABASE_URL and RIFT_SUPABASE_KEY.")
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise RuntimeError("Install the optional supabase dependency: pip install -e '.[supabase]'") from exc
            self._client=create_client(self.url,self.key)
        return self._client

    def create_experiment(self, payload: dict[str,Any]):
        return self.client().table("experiments").insert(payload).execute()

    def create_run(self, payload: dict[str,Any]):
        return self.client().table("experiment_runs").insert(payload).execute()

    def get_experiment(self, experiment_id: str):
        return self.client().table("experiments").select("*").eq("id",experiment_id).single().execute()

    def list_runs(self, experiment_id: str):
        return self.client().table("experiment_runs").select("*").eq("experiment_id",experiment_id).order("created_at",desc=True).execute()
