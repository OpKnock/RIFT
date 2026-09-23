"""Optional Supabase persistence adapter.

RIFT remains fully runnable without Supabase. The adapter only activates when
SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are configured and the supabase
Python client is installed.
"""
import os

class PersistenceUnavailable(RuntimeError):
    pass

class SupabasePersistence:
    def __init__(self, url=None, key=None):
        self.url=url or os.getenv("SUPABASE_URL")
        self.key=key or os.getenv("SUPABASE_PUBLISHABLE_KEY")
        if not self.url or not self.key:
            raise PersistenceUnavailable("Supabase is not configured")
        try:
            from supabase import create_client
        except ImportError as exc:
            raise PersistenceUnavailable("Install the optional Supabase client to enable persistence") from exc
        self.client=create_client(self.url,self.key)

    def create_experiment(self,name,scenario,description=""):
        return self.client.table("experiments").insert({"name":name,"description":description,"scenario":scenario,"status":"created"}).execute()

    def create_run(self,experiment_id,optimizer,result,metrics=None,seed=None):
        payload={"experiment_id":experiment_id,"optimizer":optimizer,"result":result,"metrics":metrics or {},"seed":seed}
        return self.client.table("experiment_runs").insert(payload).execute()
