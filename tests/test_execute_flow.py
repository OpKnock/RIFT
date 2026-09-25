"""Execute-flow tests with a fake Supabase store (no network, no credentials).

Covers §3 of the hardening pass: correct experiment loading, deterministic
fingerprinted runs, persistence of the run, status transitions, and every
failure mode (missing/invalid/forbidden/offline).
"""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from rift import api as api_module
from rift.api import Handler
from rift.runner import run_spec
from rift.experiments import validate_spec_payload

EXP_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "33333333-3333-4333-8333-333333333333"

SUPABASE_VARS = (
    "RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY", "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY",
)
BILLING_VARS = (
    "RIFT_LEMON_SQUEEZY_API_KEY", "RIFT_LEMON_SQUEEZY_STORE_ID",
    "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "RIFT_LEMON_SQUEEZY_VARIANT_ID",
    "LEMON_SQUEEZY_API_KEY", "LEMON_SQUEEZY_STORE_ID",
    "LEMON_SQUEEZY_WEBHOOK_SECRET", "LEMON_SQUEEZY_VARIANT_ID",
)


def _clear(monkeypatch):
    for name in SUPABASE_VARS + BILLING_VARS + ("RIFT_API_TOKEN", "RIFT_REQUIRE_USER_ID"):
        monkeypatch.delenv(name, raising=False)


class _Result:
    def __init__(self, data):
        self.data = data


class FakeStore:
    """In-memory Supabase stand-in. Class-level registry reset per test."""

    configured = True
    rows: dict = {}
    runs: list = []
    run_rows: dict = {}
    get_error: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    def get_experiment(self, experiment_id):
        if FakeStore.get_error is not None:
            raise FakeStore.get_error
        row = FakeStore.rows.get(experiment_id)
        if row is None:
            raise Exception("PGRST116: JSON object requested, 0 rows returned")
        return _Result(dict(row))

    def get_run(self, run_id):
        if FakeStore.get_error is not None:
            raise FakeStore.get_error
        row = FakeStore.run_rows.get(run_id)
        if row is None:
            raise Exception("PGRST116: JSON object requested, 0 rows returned")
        return _Result(dict(row))

    def create_run(self, payload):
        FakeStore.runs.append(dict(payload))
        return _Result(dict(payload, id="22222222-2222-4222-8222-222222222222"))

    def update_experiment(self, experiment_id, patch):
        FakeStore.rows[experiment_id] = {**FakeStore.rows.get(experiment_id, {}), **patch}
        return _Result(dict(FakeStore.rows[experiment_id]))


def _experiment_row(**overrides):
    row = {
        "id": EXP_ID,
        "name": "flow-test",
        "description": "",
        "scenario": {"name": "smart-building-emergency", "initial_state": {"crowd": 430.0}},
        "perturbations": [{"smoke": 2.0}],
        "policy_variables": [],
        "optimizer_config": {"optimizer": "exact", "backend": "statevector-simulator", "seed": 7},
        "backend": "statevector-simulator",
        "seed": 7,
        "engine_version": (__import__("rift").__version__),
        "status": "created",
        "user_id": "user-a",
    }
    row.update(overrides)
    return row


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


def _post(url, payload, headers=None):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
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


def _get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _use_fake(monkeypatch):
    FakeStore.rows = {}
    FakeStore.runs = []
    FakeStore.run_rows = {}
    FakeStore.get_error = None
    monkeypatch.setattr(api_module, "SupabaseStore", FakeStore)


def test_execute_success_persists_deterministic_run(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    FakeStore.rows[EXP_ID] = _experiment_row()
    with _Server() as server:
        status, payload = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-a"})
        assert status == 201, payload
        assert payload["experiment_id"] == EXP_ID
        assert payload["engine_version"] == (__import__("rift").__version__)
        assert payload["fingerprint"] == payload["result"]["spec_fingerprint"]
        assert FakeStore.rows[EXP_ID]["status"] == "succeeded"
        # Independent local reproduction matches the persisted run.
        spec = validate_spec_payload({
            "name": "flow-test",
            "scenario_name": "smart-building-emergency",
            "initial_state": {"crowd": 430.0},
            "perturbations": [{"smoke": 2.0}],
            "optimizer": "exact",
            "seed": 7,
        })
        expected = run_spec(spec)
        assert payload["result"]["assignment"] == expected["assignment"]
        assert payload["result"]["robust_cost"] == expected["robust_cost"]
        assert payload["result"]["guardian"] == expected["guardian"]


def test_execute_repeat_is_reproducible(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    FakeStore.rows[EXP_ID] = _experiment_row()
    with _Server() as server:
        first_status, first = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-a"})
        second_status, second = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-a"})
        assert (first_status, second_status) == (201, 201)
        assert first["fingerprint"] == second["fingerprint"]
        assert first["result"]["assignment"] == second["result"]["assignment"]
        assert len(FakeStore.runs) == 2


def test_execute_forbidden_for_other_user(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    FakeStore.rows[EXP_ID] = _experiment_row()
    with _Server() as server:
        status, payload = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-b"})
        assert status == 403
        assert payload["error"] == "forbidden"
        assert FakeStore.runs == []
        assert FakeStore.rows[EXP_ID]["status"] == "created"


def test_execute_missing_experiment_404(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    with _Server() as server:
        status, payload = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-a"})
        assert status == 404
        assert payload["error"] == "not_found"


def test_execute_invalid_row_422_and_failed(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    row = _experiment_row(optimizer_config={"optimizer": "bogus", "backend": "x", "seed": None})
    FakeStore.rows[EXP_ID] = row
    with _Server() as server:
        status, payload = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-a"})
        assert status == 422
        assert FakeStore.rows[EXP_ID]["status"] == "failed"
        assert FakeStore.runs == []


def test_execute_genuine_db_failure_502(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    FakeStore.get_error = Exception("connection refused")
    with _Server() as server:
        status, payload = _post(server.url(f"/api/experiments/{EXP_ID}/execute"), {"user_id": "user-a"})
        assert status == 502
        assert payload["error"] == "persistence_error"
        assert "Traceback" not in json.dumps(payload)


def test_get_missing_experiment_404(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    with _Server() as server:
        status, payload = _get(server.url(f"/api/experiments/{EXP_ID}"))
        assert status == 404
        assert payload["error"] == "not_found"


def test_cross_user_reads_denied(monkeypatch):
    _clear(monkeypatch)
    _use_fake(monkeypatch)
    FakeStore.rows[EXP_ID] = _experiment_row()
    FakeStore.run_rows[RUN_ID] = {"id": RUN_ID, "experiment_id": EXP_ID, "user_id": "user-a"}
    with _Server() as server:
        status, payload = _get(server.url(f"/api/experiments/{EXP_ID}?user_id=user-b"))
        assert status == 403
        assert payload["error"] == "forbidden"
        status, payload = _get(server.url(f"/api/runs/{RUN_ID}?user_id=user-b"))
        assert status == 403
        assert payload["error"] == "forbidden"
        # Owners read their own objects.
        status, payload = _get(server.url(f"/api/experiments/{EXP_ID}?user_id=user-a"))
        assert status == 200
        assert payload["id"] == EXP_ID
        status, payload = _get(server.url(f"/api/runs/{RUN_ID}?user_id=user-a"))
        assert status == 200
        assert payload["id"] == RUN_ID


def test_checkout_rejects_non_string_variant(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "s")
    with _Server() as server:
        status, payload = _post(server.url("/api/billing/checkout"), {"variant_id": {"nested": "object"}})
        assert status == 400
