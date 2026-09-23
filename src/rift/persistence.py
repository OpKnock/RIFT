"""Optional Supabase persistence adapter (legacy import path).

Canonical configuration lives in :mod:`rift.settings` and
:mod:`rift.supabase_store`:

- ``RIFT_SUPABASE_URL`` (fallback: ``SUPABASE_URL``)
- ``RIFT_SUPABASE_KEY`` (fallback: ``SUPABASE_SERVICE_KEY``,
  ``SUPABASE_PUBLISHABLE_KEY``, ``SUPABASE_ANON_KEY``)

This module is kept for backward compatibility and delegates to
``SupabaseStore``. New code should import from ``rift.supabase_store``.
"""
from .supabase_store import SupabaseStore

__all__ = ["PersistenceUnavailable", "SupabasePersistence", "SupabaseStore"]


class PersistenceUnavailable(RuntimeError):
    pass


class SupabasePersistence(SupabaseStore):
    def __init__(self, url=None, key=None):
        try:
            super().__init__(url=url, key=key)
        except TypeError:
            super().__init__()
        if not self.configured:
            raise PersistenceUnavailable(
                "Supabase is not configured. Set RIFT_SUPABASE_URL and "
                "RIFT_SUPABASE_KEY in a trusted server environment."
            )

    def create_experiment(self, name, scenario, description=""):
        return super().create_experiment(
            {
                "name": name,
                "description": description,
                "scenario": scenario,
                "status": "created",
            }
        )

    def create_run(self, experiment_id, optimizer, result, metrics=None, seed=None):
        payload = {
            "experiment_id": experiment_id,
            "optimizer": optimizer,
            "result": result,
            "metrics": metrics or {},
            "seed": seed,
        }
        return super().create_run(payload)
