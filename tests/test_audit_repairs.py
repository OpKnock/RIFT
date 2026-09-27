"""Regression tests for audit repair batches (frozen import, identity, scheduler, CORS)."""

import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from rift.api import Handler


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
        url, data=body, method="POST", headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def test_review_identity_mismatch_rejected(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    with _Server() as server:
        status, payload = _post(server.url("/api/twin/reviews"), {
            "action": "ACCEPT", "evidence_id": "ev-audit-1",
            "reviewer_id": "mallory", "user_id": "alice", "rationale": "x",
        })
        assert status == 400
        assert payload["error"] == "identity_mismatch"


def test_review_records_verified_principal(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    with _Server() as server:
        status, payload = _post(server.url("/api/twin/reviews"), {
            "action": "ACCEPT", "evidence_id": "ev-audit-2",
            "reviewer_id": "alice", "user_id": "alice", "rationale": "x",
        })
        assert status == 201
        assert payload["reviewer_id"] == "alice"
        assert payload["identity_verified"] is True


def test_scheduler_stores_and_lists_real_jobs(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    with _Server() as server:
        status, payload = _post(server.url("/api/experiments/scheduler/jobs"), {
            "experiment_id": "exp-audit",
            "spec": {"name": "sched-audit", "optimizer": "exact"},
        })
        assert status == 201
        assert payload["job_id"].startswith("job-")
        status, raw, _ = _get(server.url("/api/experiments/scheduler/jobs"))
        assert status == 200
        jobs = json.loads(raw.decode())["jobs"]
        assert any(j["id"] == payload["job_id"] for j in jobs)


def test_cors_allowlist_and_preflight(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("RIFT_CORS_ORIGINS", "http://localhost:5173")
    with _Server() as server:
        status, _, headers = _get(server.url("/api/health"), {"Origin": "http://localhost:5173"})
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
        status, _, headers = _get(server.url("/api/health"), {"Origin": "http://evil.example.com"})
        assert status == 200
        assert "Access-Control-Allow-Origin" not in headers


def test_import_rejects_unvalidated_runs(monkeypatch):
    from rift.experiments import experiment_archive
    import pytest
    with pytest.raises(ValueError):
        experiment_archive.import_experiment({
            "experiment": {"name": "x"},
            "runs": [{"id": "r1", "spec": {"name": "bad", "optimizer": "nope"}}],
        })


def test_traffic_spec_validates_and_runs():
    from rift.experiments import validate_spec_payload
    from rift.runner import run_spec
    spec = validate_spec_payload({
        "name": "t", "scenario_name": "traffic-optimization",
        "initial_state": {"flow_rate": 1200, "queue_length": 25, "avg_wait_time": 45},
        "policy_variables": ["green_time_ratio", "cycle_length"],
        "optimizer": "exact",
    })
    out = run_spec(spec)
    assert isinstance(out, dict) and out
