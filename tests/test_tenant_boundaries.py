"""Tenant-boundary tests: archive fallback, sub-resources, ops ownership.

Covers the audit follow-ups: archive mirrors carry user_id and enforce it,
every experiment sub-resource gates ownership, compare never serves stale
mirrors on outage, incidents/decisions bind owner at create and enforce on
mutate, imports persist authoritatively with re-assigned ownership.
"""
import json
import threading
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer

from rift import api as api_module
from rift.api import Handler
from rift.experiments import experiment_archive
from rift.routes import routes_billing, routes_experiments

SUPABASE_VARS = (
    "RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY", "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY",
)
AUTH_VARS = ("RIFT_API_TOKEN", "RIFT_SUPABASE_JWT_SECRET", "RIFT_REQUIRE_USER_ID")


def _clear(monkeypatch):
    for name in SUPABASE_VARS + AUTH_VARS:
        monkeypatch.delenv(name, raising=False)


def _new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class _Result:
    def __init__(self, data):
        self.data = data


class FakeStore:
    """In-memory Supabase stand-in with the full write API."""

    configured = True
    rows: dict = {}
    run_rows: dict = {}
    runs: list = []
    get_error: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    def _maybe_fail(self):
        if FakeStore.get_error is not None:
            raise FakeStore.get_error

    def get_experiment(self, experiment_id):
        self._maybe_fail()
        row = FakeStore.rows.get(experiment_id)
        if row is None:
            raise Exception("PGRST116: JSON object requested, 0 rows returned")
        return _Result(dict(row))

    def get_run(self, run_id):
        self._maybe_fail()
        row = FakeStore.run_rows.get(run_id)
        if row is None:
            raise Exception("PGRST116: JSON object requested, 0 rows returned")
        return _Result(dict(row))

    def create_experiment(self, payload):
        self._maybe_fail()
        row = dict(payload, id=str(uuid.uuid4()))
        FakeStore.rows[row["id"]] = row
        return _Result(dict(row))

    def create_run(self, payload):
        self._maybe_fail()
        row = dict(payload, id=str(uuid.uuid4()))
        FakeStore.run_rows[row["id"]] = row
        FakeStore.runs.append(row)
        return _Result(dict(row))

    def update_experiment(self, experiment_id, patch):
        self._maybe_fail()
        FakeStore.rows[experiment_id] = {**FakeStore.rows.get(experiment_id, {}), **patch}
        return _Result(dict(FakeStore.rows[experiment_id]))

    def list_runs(self, experiment_id):
        self._maybe_fail()
        rows = [r for r in FakeStore.run_rows.values()
                if r.get("experiment_id") == experiment_id]

        class R:
            data = [dict(r) for r in rows]
        return R()


def _reset_fake():
    FakeStore.rows = {}
    FakeStore.run_rows = {}
    FakeStore.runs = []
    FakeStore.get_error = None


def _patch_store(monkeypatch, cls=FakeStore):
    for mod in (api_module, routes_experiments, routes_billing):
        monkeypatch.setattr(mod, "SupabaseStore", cls)


def _exp_row(exp_id, user_id="user-a", **overrides):
    row = {
        "id": exp_id,
        "name": "tenant-test",
        "description": "",
        "scenario": {"name": "smart-building-emergency", "initial_state": {}},
        "perturbations": [],
        "policy_variables": [],
        "optimizer_config": {"optimizer": "exact", "backend": "statevector-simulator", "seed": 7},
        "backend": "statevector-simulator",
        "seed": 7,
        "engine_version": (__import__("rift").__version__),
        "status": "created",
        "user_id": user_id,
    }
    row.update(overrides)
    return row


def _spec_dict(name="tenant-spec"):
    return {"name": name, "optimizer": "exact"}


class _Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"


def _get(url):
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _post(url, payload):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw}


# --- archive fallback ownership ---

def test_archive_mirror_enforces_owner(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    exp_id = str(uuid.uuid4())
    experiment_archive.store_experiment({
        "id": exp_id, "name": "m", "spec": _spec_dict(),
        "status": "created", "versions": [], "user_id": "user-a",
    })
    with _Server() as server:
        # No Supabase configured: archive is the only source, still gated.
        status, _ = _get(server.url(f"/api/experiments/{exp_id}?user_id=user-a"))
        assert status == 200
        status, payload = _get(server.url(f"/api/experiments/{exp_id}?user_id=user-b"))
        assert status == 403, payload
        status, _ = _get(server.url(f"/api/experiments/{str(uuid.uuid4())}?user_id=user-a"))
        assert status == 404


def test_archive_run_enforces_owner(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    from rift.experiments import ExperimentRun, validate_spec_payload
    spec = validate_spec_payload(_spec_dict())
    exp_id, run_id = str(uuid.uuid4()), _new_id("run")
    experiment_archive.store_experiment({"id": exp_id, "user_id": "user-a", "versions": []})
    experiment_archive.store_run(ExperimentRun(
        id=run_id, experiment_id=exp_id, experiment_version=1, spec=spec,
        optimizer="exact", metrics={}, result=None, seed=7,
        engine_version="1.0.0", started_at="now", completed_at=None,
        status="succeeded", user_id="user-a",
    ))
    with _Server() as server:
        status, _ = _get(server.url(f"/api/experiments/{exp_id}/runs/{run_id}?user_id=user-a"))
        assert status == 200
        status, payload = _get(server.url(f"/api/experiments/{exp_id}/runs/{run_id}?user_id=user-b"))
        assert status == 403, payload


# --- sub-resource gating (Supabase-backed) ---

def _seed_supabase(exp_id, user_id="user-a"):
    FakeStore.rows[exp_id] = _exp_row(exp_id, user_id=user_id)


def test_versions_cross_user_403_and_durable_write(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    _patch_store(monkeypatch)
    exp_id = str(uuid.uuid4())
    _seed_supabase(exp_id)
    with _Server() as server:
        status, payload = _get(server.url(f"/api/experiments/{exp_id}/versions?user_id=user-b"))
        assert status == 403, payload
        status, payload = _post(
            server.url(f"/api/experiments/{exp_id}/versions"),
            {"user_id": "user-a", "spec": _spec_dict()},
        )
        assert status == 201, payload
        assert payload["durable"] is True
        assert FakeStore.rows[exp_id]["versions"][0]["spec"]["name"] == "tenant-spec"
        status, payload = _get(server.url(f"/api/experiments/{exp_id}/versions?user_id=user-a"))
        assert status == 200 and len(payload["versions"]) == 1


def test_runs_list_and_detail_gate_owner(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    _patch_store(monkeypatch)
    exp_id = str(uuid.uuid4())
    _seed_supabase(exp_id)
    run_id = str(uuid.uuid4())
    FakeStore.run_rows[run_id] = {
        "id": run_id, "experiment_id": exp_id, "experiment_version": 1,
        "optimizer": "exact", "metrics": {}, "result": None, "seed": 7,
        "engine_version": "1.0.0", "created_at": "now",
        "completed_at": None, "status": "succeeded", "user_id": "user-a",
    }
    with _Server() as server:
        status, _ = _get(server.url(f"/api/experiments/{exp_id}/runs?user_id=user-b"))
        assert status == 403
        status, payload = _get(server.url(f"/api/experiments/{exp_id}/runs?user_id=user-a"))
        assert status == 200 and len(payload) == 1
        status, _ = _get(server.url(f"/api/experiments/{exp_id}/runs/{run_id}?user_id=user-b"))
        assert status == 403
        status, payload = _get(server.url(f"/api/experiments/{exp_id}/runs/{run_id}?user_id=user-a"))
        assert status == 200 and payload["id"] == run_id


def test_snapshots_evidence_export_replay_gate_owner(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    exp_id = str(uuid.uuid4())
    experiment_archive.store_experiment({
        "id": exp_id, "name": "m", "spec": _spec_dict(), "status": "created",
        "versions": [], "user_id": "user-a",
        "snapshot": {"id": "snap-1", "experiment_id": exp_id},
    })
    with _Server() as server:
        for path in ("snapshots", "evidence", "export", "replay"):
            status, payload = _get(server.url(f"/api/experiments/{exp_id}/{path}?user_id=user-b"))
            assert status == 403, (path, payload)
        status, _ = _get(server.url(f"/api/experiments/{exp_id}/snapshots?user_id=user-a"))
        assert status == 200


def test_templates_private_hidden(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    with _Server() as server:
        status, payload = _post(server.url("/api/experiments/templates"), {
            "user_id": "user-a", "name": "private-t", "spec": _spec_dict(),
        })
        assert status == 201, payload
        tmpl_id = payload["id"]
        status, payload = _post(server.url("/api/experiments/templates"), {
            "user_id": "user-b", "name": "public-t", "spec": _spec_dict(),
            "is_public": True,
        })
        assert status == 201, payload
        status, payload = _get(server.url("/api/experiments/templates?user_id=user-b"))
        names = [t["name"] for t in payload["templates"]]
        assert "public-t" in names and "private-t" not in names
        status, _ = _get(server.url(f"/api/experiments/templates/{tmpl_id}?user_id=user-b"))
        assert status == 403
        status, _ = _get(server.url(f"/api/experiments/templates/{tmpl_id}?user_id=user-a"))
        assert status == 200


# --- compare safety ---

def test_compare_outage_is_502_not_stale_mirror(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    _patch_store(monkeypatch)
    FakeStore.get_error = Exception("connection refused")
    with _Server() as server:
        status, payload = _post(server.url("/api/experiments/compare"), {
            "user_id": "user-a", "baseline_id": "r1", "candidate_ids": ["r2"],
        })
        assert status == 502, payload
        assert payload["error"] == "persistence_error"


def test_compare_archive_run_enforces_owner(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    from rift.experiments import ExperimentRun, validate_spec_payload
    spec = validate_spec_payload(_spec_dict())
    exp_id = _new_id("exp")
    experiment_archive.store_experiment({"id": exp_id, "user_id": "user-a", "versions": []})
    base_id, cand_id = _new_id("run"), _new_id("run")

    def _run(rid):
        return ExperimentRun(
            id=rid, experiment_id=exp_id, experiment_version=1, spec=spec,
            optimizer="exact", metrics={"energy": 1.0}, result={"x": 1}, seed=7,
            engine_version="1.0.0", started_at="now", completed_at="now",
            status="succeeded", user_id="user-a",
        )

    experiment_archive.store_run(_run(base_id))
    experiment_archive.store_run(_run(cand_id))
    with _Server() as server:
        status, payload = _post(server.url("/api/experiments/compare"), {
            "user_id": "user-b", "baseline_id": base_id, "candidate_ids": [cand_id],
        })
        assert status == 403, payload
        status, payload = _post(server.url("/api/experiments/compare"), {
            "user_id": "user-a", "baseline_id": base_id, "candidate_ids": [cand_id],
        })
        assert status == 201, payload


# --- import ---

def test_import_persists_with_reassigned_owner(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    _patch_store(monkeypatch)
    package = {
        "experiment": {"name": "orig", "spec": _spec_dict(), "user_id": "attacker"},
        "runs": [],
    }
    with _Server() as server:
        status, payload = _post(server.url("/api/experiments/import"), {
            "user_id": "user-a", "package": package,
        })
        assert status == 201, payload
        assert payload["durable"] is True
        sup_id = payload["experiment_id"]
        assert FakeStore.rows[sup_id]["user_id"] == "user-a"
        status, payload = _get(server.url(f"/api/experiments/{sup_id}?user_id=user-b"))
        assert status == 403, payload


def test_import_rejects_invalid_package(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    _patch_store(monkeypatch)
    with _Server() as server:
        status, payload = _post(server.url("/api/experiments/import"), {
            "user_id": "user-a",
            "package": {"experiment": {"name": "x", "spec": {"name": "x", "optimizer": "bogus"}}},
        })
        assert status == 400, payload
        assert payload["error"] == "invalid_package"


# --- operations ownership ---

def test_incident_owner_flow(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    with _Server() as server:
        status, payload = _post(server.url("/api/operations/incidents"), {
            "user_id": "user-a", "type": "manual", "title": "t",
        })
        assert status == 201, payload
        inc_id = payload["id"]
        assert payload["owner"] == "user-a"
        status, payload = _get(server.url("/api/operations/incidents?mine=true&user_id=user-a"))
        assert status == 200 and any(i["id"] == inc_id for i in payload)
        status, payload = _post(
            server.url(f"/api/operations/incidents/{inc_id}/action"),
            {"user_id": "user-b", "action": "acknowledge"},
        )
        assert status == 403, payload
        status, payload = _post(
            server.url(f"/api/operations/incidents/{inc_id}/action"),
            {"user_id": "user-a", "action": "acknowledge"},
        )
        assert status == 200, payload


def test_decision_action_enforces_proposer(monkeypatch):
    _clear(monkeypatch)
    _reset_fake()
    from rift.operations import decision_store
    decision = decision_store.create(
        scenario_id="s", policy={}, proposed_by="user-a",
    )
    with _Server() as server:
        status, payload = _post(
            server.url(f"/api/operations/decisions/{decision.id}/action"),
            {"user_id": "user-b", "action": "accept"},
        )
        assert status == 403, payload
        status, payload = _post(
            server.url(f"/api/operations/decisions/{decision.id}/action"),
            {"user_id": "user-a", "action": "accept"},
        )
        assert status == 200, payload
