"""Route handlers (split verbatim from api.py; see package README)."""
from __future__ import annotations

from .support import _fetch_supabase_row, _is_not_found_error, _is_valid_uuid, _mirror_experiment_to_archive, _mirror_run_to_archive, _resolve_experiment, _resolve_run, _run_from_row, _spec_from_experiment_row, _spec_from_payload
from rift import __version__ as ENGINE_VERSION
from rift.supabase_store import SupabaseStore
from datetime import datetime, timezone
import json
from rift.observability import log_event
from rift.auth import owner_mismatch
from rift.auth import require_user_id_enforced
from rift.runner import run_spec
import uuid
from rift.experiments import validate_run_payload
from rift.experiments import validate_spec_payload


def get_api_experiments_runs(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/runs"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        if not _is_valid_uuid(experiment_id):
            h._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        payload, _spec_dict, err = _resolve_experiment(store, experiment_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing" or payload is None:
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        try:
            from rift.experiments import experiment_archive
            if store.configured:
                # Durable list from the authoritative store, tenant
                # filtered per row; adapted to the canonical run shape
                # so both backends serve one contract.
                try:
                    rows = (store.list_runs(experiment_id).data or [])
                except Exception:
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    h._finish(timer, request_id, "GET", path, 502, "persistence_error")
                    return True
                spec_obj = _spec_from_payload(payload)
                runs = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if owner_mismatch(row.get("user_id"), caller):
                        continue
                    run = _run_from_row(row, spec_obj) if spec_obj is not None else None
                    runs.append(run.to_dict() if run is not None else dict(row))
            else:
                runs = [r.to_dict() for r in experiment_archive.get_runs(experiment_id)
                        if not owner_mismatch(getattr(r, "user_id", None), caller)]
            h._send(200, json.dumps(runs), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 200)
        except Exception:
            h._send(500, json.dumps({"error": "runs_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True
# --- Phase 10: Experiment Platform ---
    return False


def _template_visible(t, caller: str | None) -> bool:
    """Template visibility: public, system/legacy, or owned by the caller.

    Unauthenticated (dev open mode) callers see everything, matching the
    workspace-visible default for ownerless objects elsewhere.
    """
    if t.is_public:
        return True
    if caller is None:
        return True
    created_by = t.created_by or ""
    return created_by in ("", "system", "anonymous") or created_by == caller


def get_api_experiments_templates(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/templates": (moved verbatim from api.py do_GET)."""
    caller, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.experiments import experiment_archive
        templates = [t.to_dict() for t in experiment_archive.list_templates(public_only=False)
                     if _template_visible(t, caller)]
        h._send(200, json.dumps({"templates": templates}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "templates_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True

    return False


def get_api_experiments_templates_2(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/templates/"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        template_id = parts[3]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        try:
            from rift.experiments import experiment_archive
            template = experiment_archive.get_template(template_id)
            if template and not _template_visible(template, caller):
                h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 403, "auth")
                return True
            if template:
                h._send(200, json.dumps(template.to_dict()), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 200)
            else:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 404, "not_found")
        except Exception:
            h._send(500, json.dumps({"error": "templates_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_experiments_versions(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/versions"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        payload, _, err = _resolve_experiment(store, experiment_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing" or payload is None:
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        try:
            # Durable versions live on the Supabase row (migration 008);
            # the archive mirror only feeds pre-migration rows that lack
            # the column. (Standalone version records only; the experiment
            # itself is never a member of its own version list.)
            versions = payload.get("versions")
            if not isinstance(versions, list):
                from rift.experiments import experiment_archive
                exp = experiment_archive.get_experiment(experiment_id)
                if exp and owner_mismatch(exp.get("user_id"), caller):
                    h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    h._finish(timer, request_id, "GET", path, 403, "auth")
                    return True
                versions = (exp or {}).get("versions", [])
            versions = [v for v in versions if isinstance(v, dict)]
            h._send(200, json.dumps({"experiment_id": experiment_id, "versions": versions}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 200)
        except Exception:
            h._send(500, json.dumps({"error": "versions_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_experiments_runs_3(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and "/runs/" in path: (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 5:
        experiment_id = parts[2]
        run_id = parts[4]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        payload, err = _resolve_run(store, run_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing" or payload is None:
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        if payload.get("experiment_id") != experiment_id:
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        # Canonical run shape (nested spec): adapt Supabase rows so the
        # contract matches the archive path regardless of backend.
        if not isinstance(payload.get("spec"), dict):
            exp_payload, _, exp_err = _resolve_experiment(store, experiment_id, caller)
            spec_obj = _spec_from_payload(exp_payload) if exp_err is None and exp_payload else None
            run = _run_from_row(payload, spec_obj) if spec_obj is not None else None
            if run is not None:
                payload = run.to_dict()
        h._send(200, json.dumps(payload), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
        return True

    return False


def get_api_experiments_snapshots(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/snapshots"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        _, _, err = _resolve_experiment(store, experiment_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing":
            h._send(404, json.dumps({"error": "no_snapshot"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        try:
            from rift.experiments import experiment_archive
            exp = experiment_archive.get_experiment(experiment_id)
            if exp and exp.get("snapshot"):
                h._send(200, json.dumps(exp["snapshot"]), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 200)
            else:
                h._send(404, json.dumps({"error": "no_snapshot"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 404, "not_found")
        except Exception:
            h._send(500, json.dumps({"error": "snapshots_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_experiments_benchmarks(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/benchmarks": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.experiments import experiment_archive
        benchmarks = [b.to_dict() for b in experiment_archive._benchmarks.values()]
        h._send(200, json.dumps({"benchmarks": benchmarks}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "benchmarks_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True

    return False


def get_api_experiments_evidence(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/evidence"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        _, _, err = _resolve_experiment(store, experiment_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing":
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        try:
            from rift.experiments import experiment_archive
            bundles = [b.to_dict() for b in experiment_archive.evidence_for_experiment(experiment_id)]
            h._send(200, json.dumps({"experiment_id": experiment_id, "bundles": bundles}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 200)
        except Exception:
            h._send(500, json.dumps({"error": "evidence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_experiments_export(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/export"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        try:
            from rift.experiments import experiment_archive
            package = experiment_archive.export_experiment(experiment_id)
            if package is not None and owner_mismatch(
                    (package.get("experiment") or {}).get("user_id"), caller):
                h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 403, "auth")
                return True
            if package is None:
                # Fall back to Supabase-backed experiments (with
                # ownership enforcement) when the local archive
                # has no record (e.g. after a restart).
                store = SupabaseStore()
                if store.configured:
                    exp_row, failed = h._load_row(
                        lambda: store.get_experiment(experiment_id),
                        timer, request_id, "GET", path,
                    )
                    if not failed and exp_row:
                        if owner_mismatch(exp_row.get("user_id"), caller):
                            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                            h._finish(timer, request_id, "GET", path, 403, "auth")
                            return True
                        spec = _spec_from_experiment_row(exp_row)
                        if spec is not None:
                            runs_out = []
                            try:
                                rows = (store.list_runs(experiment_id).data or [])
                            except Exception:
                                rows = []
                            for row in rows:
                                if owner_mismatch(row.get("user_id"), caller):
                                    continue
                                run = _run_from_row(row, spec)
                                if run is not None:
                                    runs_out.append(run.to_dict())
                            package = {
                                "experiment": exp_row,
                                "spec": spec.to_dict(),
                                "runs": runs_out,
                                "exported_at": datetime.now(timezone.utc).isoformat(),
                                "engine_version": ENGINE_VERSION,
                            }
            if package:
                h._send(200, json.dumps(package), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 200)
            else:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 404, "not_found")
        except Exception:
            h._send(500, json.dumps({"error": "export_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_experiments_replay(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/replay"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        try:
            from rift.experiments import experiment_archive, validate_spec_payload
            from rift.runner import run_spec
            spec_data = None
            exp = experiment_archive.get_experiment(experiment_id)
            if exp:
                if owner_mismatch(exp.get("user_id"), caller):
                    h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    h._finish(timer, request_id, "GET", path, 403, "auth")
                    return True
                spec_data = exp.get("spec")
            if spec_data is None:
                # Fall back to Supabase-backed experiments (owned).
                store = SupabaseStore()
                if store.configured:
                    exp_row, failed = h._load_row(
                        lambda: store.get_experiment(experiment_id),
                        timer, request_id, "GET", path,
                    )
                    if not failed and exp_row:
                        if owner_mismatch(exp_row.get("user_id"), caller):
                            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                            h._finish(timer, request_id, "GET", path, 403, "auth")
                            return True
                        spec = _spec_from_experiment_row(exp_row)
                        if spec is not None:
                            spec_data = spec.to_dict()
            if not spec_data:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 404, "not_found")
                return True
            try:
                spec = validate_spec_payload(spec_data if isinstance(spec_data, dict) else {})
            except ValueError as exc:
                h._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 400, "validation")
                return True
            # Deterministic server-side replay: re-execute the
            # stored spec through the canonical runner.
            try:
                result = run_spec(spec)
            except Exception as exc:
                h._send(502, json.dumps({"error": "replay_failed", "detail": str(exc)[:300]}), request_id=request_id)
                h._finish(timer, request_id, "GET", path, 502, "replay_failed")
                return True
            h._send(200, json.dumps({
                "experiment_id": experiment_id,
                "spec": spec.to_dict(),
                "fingerprint": spec.fingerprint(),
                "result": result,
            }), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 200)
        except Exception:
            h._send(500, json.dumps({"error": "replay_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 500, "internal")
        return True

    return False


def get_api_experiments_scheduler_jobs(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/scheduler/jobs": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.experiments import local_scheduler
        jobs = []
        for job in local_scheduler.list_jobs():
            view = dict(job)
            spec = view.get("spec")
            if hasattr(spec, "to_dict"):
                view["spec"] = spec.to_dict()
            jobs.append(view)
        h._send(200, json.dumps({"jobs": jobs, "note": "local in-process scheduler; jobs do not survive restarts"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "scheduler_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True

    return False


def get_api_experiments(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 3:
        experiment_id = parts[2]
        if not _is_valid_uuid(experiment_id):
            h._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        payload, _, err = _resolve_experiment(store, experiment_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing" or payload is None:
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        h._send(200, json.dumps(payload), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
        return True
    return False


def get_api_runs(h, request_id, timer, path, query):
    """Route if path.startswith("/api/runs/"): (moved verbatim from api.py do_GET)."""
    parts = path.strip("/").split("/")
    if len(parts) == 3:
        run_id = parts[2]
        if not _is_valid_uuid(run_id):
            h._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, None, query)
        if not ok:
            h._finish(timer, request_id, "GET", path, 401, "auth")
            return True
        store = SupabaseStore()
        payload, err = _resolve_run(store, run_id, caller)
        if err == "forbidden":
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 403, "auth")
            return True
        if err == "unavailable":
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return True
        if err == "missing" or payload is None:
            h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 404, "not_found")
            return True
        h._send(200, json.dumps(payload), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
        return True

    return False


def post_api_experiments(h, request_id, timer, path, query):
    """Route if path == "/api/experiments": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    owner, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        spec = validate_spec_payload(body if isinstance(body, dict) else {})
    except ValueError as exc:
        h._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    if require_user_id_enforced() and not owner:
        h._send(400, json.dumps({"error": "missing_user_id"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    store = SupabaseStore()
    if not store.configured:
        h._send(503, json.dumps({
            "error": "persistence_not_configured",
            "detail": "Set RIFT_SUPABASE_URL and RIFT_SUPABASE_KEY on the server.",
        }), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 503, "persistence_not_configured")
        return True
    try:
        result = store.create_experiment({
            "name": spec.name,
            "description": spec.description,
            "scenario": {"name": spec.scenario_name, "initial_state": spec.initial_state},
            "perturbations": list(spec.perturbations),
            "policy_variables": list(spec.policy_variables),
            "optimizer_config": {"optimizer": spec.optimizer, "backend": spec.backend, "seed": spec.seed},
            "backend": spec.backend,
            "seed": spec.seed,
            "engine_version": spec.engine_version,
            "fingerprint": spec.fingerprint(),
            "status": "created",
            **({"user_id": owner} if owner else {}),
        })
        _mirror_experiment_to_archive(spec, result.data or {}, owner)
        h._send(201, json.dumps(result.data), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201, extra_experiment="created")
    except Exception:
        log_event("dependency_failure", request_id=request_id, dependency="supabase")
        h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 502, "persistence_error")
    return True

    return False


def post_api_experiments_runs_run(h, request_id, timer, path, query):
    """Route if (path.startswith("/api/experiments/") and (path.endswith("/runs") or path.endswith("/run"))): (moved verbatim from api.py do_POST)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        if not _is_valid_uuid(experiment_id):
            h._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        body, raw = h._read_json()
        if body == "overflow":
            h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 413, "validation")
            return True
        if body is None:
            h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
        if not ok:
            h._finish(timer, request_id, "POST", path, 401, "auth")
            return True
        try:
            run = validate_run_payload(body if isinstance(body, dict) else {})
        except ValueError as exc:
            h._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        store = SupabaseStore()
        if not store.configured:
            h._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 503, "persistence_not_configured")
            return True
        try:
            experiment, failed = h._load_row(
                lambda: store.get_experiment(experiment_id),
                timer, request_id, "POST", path,
            )
            if failed:
                return True
            if require_user_id_enforced() and not caller:
                h._send(400, json.dumps({"error": "missing_user_id"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            if owner_mismatch(experiment.get("user_id"), caller):
                h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 403, "auth")
                return True
            payload = {
                "experiment_id": experiment_id,
                "optimizer": run["optimizer"],
                "result": run["result"],
                "metrics": run["metrics"],
                "seed": run["seed"],
                "backend": "statevector-simulator",
                "engine_version": ENGINE_VERSION,
            }
            if caller:
                payload["user_id"] = caller
            result = store.create_run(payload)
            spec = _spec_from_experiment_row(experiment)
            if spec is not None:
                _mirror_run_to_archive(experiment_id, spec, run, result.data or {})
            h._send(201, json.dumps(result.data), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 201)
        except Exception:
            log_event("dependency_failure", request_id=request_id, dependency="supabase")
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 502, "persistence_error")
        return True

    return False


def post_api_experiments_execute(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/execute"): (moved verbatim from api.py do_POST)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        if not _is_valid_uuid(experiment_id):
            h._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        body, raw = h._read_json()
        if body == "overflow":
            h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 413, "validation")
            return True
        if body is None:
            body = {}
        caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
        if not ok:
            h._finish(timer, request_id, "POST", path, 401, "auth")
            return True
        store = SupabaseStore()
        if not store.configured:
            h._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 503, "persistence_not_configured")
            return True
        row, failed = h._load_row(
            lambda: store.get_experiment(experiment_id),
            timer, request_id, "POST", path,
        )
        if failed:
            return True
        if require_user_id_enforced() and not caller:
            h._send(400, json.dumps({"error": "missing_user_id"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        if owner_mismatch(row.get("user_id"), caller):
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 403, "auth")
            return True
        stored_scenario = row.get("scenario") or {}
        optimizer_config = row.get("optimizer_config") or {}
        try:
            spec = validate_spec_payload({
                "name": row.get("name", "experiment"),
                "scenario_name": stored_scenario.get("name", "smart-building-emergency"),
                "initial_state": stored_scenario.get("initial_state", {}),
                "perturbations": row.get("perturbations", []),
                "policy_variables": row.get("policy_variables", []),
                "optimizer": optimizer_config.get("optimizer", "exact"),
                "backend": row.get("backend", "statevector-simulator"),
                "seed": row.get("seed"),
                "description": row.get("description", ""),
            })
        except ValueError as exc:
            try:
                store.update_experiment(experiment_id, {"status": "failed", "error": {"message": str(exc)[:300]}})
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
            h._send(422, json.dumps({"error": "invalid experiment", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 422, "validation")
            return True
        try:
            record = run_spec(spec)
        except ValueError as exc:
            try:
                store.update_experiment(experiment_id, {"status": "failed", "error": {"message": str(exc)[:300]}})
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
            h._send(422, json.dumps({"error": "invalid experiment", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 422, "validation")
            return True
        except Exception:
            try:
                store.update_experiment(experiment_id, {"status": "failed", "error": {"message": "execution failed"}})
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
            log_event("internal_error", request_id=request_id, route="execute")
            h._send(500, json.dumps({"error": "execution_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 500, "internal")
            return True
        try:
            run_payload: dict = {
                "experiment_id": experiment_id,
                "optimizer": spec.optimizer,
                "backend": spec.backend,
                "optimizer_config": {"optimizer": spec.optimizer, "backend": spec.backend, "seed": spec.seed},
                "result": record,
                "metrics": {
                    "robust_cost": record["robust_cost"],
                    "nominal_cost": record["nominal_cost"],
                    "feasible": record["feasible"],
                    "duration_ms": record["duration_ms"],
                },
                "seed": spec.seed,
                "engine_version": ENGINE_VERSION,
                "fingerprint": spec.fingerprint(),
            }
            if caller or row.get("user_id"):
                run_payload["user_id"] = caller or row.get("user_id")
            created = store.create_run(run_payload)
            try:
                store.update_experiment(experiment_id, {"status": "succeeded"})
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
            h._send(201, json.dumps(created.data), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 201)
        except Exception:
            log_event("dependency_failure", request_id=request_id, dependency="supabase")
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 502, "persistence_error")
        return True

    return False


def post_api_experiments_templates(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/templates": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.experiments import experiment_archive, ExperimentTemplate
        try:
            spec = validate_spec_payload(body.get("spec") or {})
        except ValueError as exc:
            h._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        name = str(body.get("name", "") or "").strip()
        if not name:
            h._send(400, json.dumps({"error": "name is required"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        template = ExperimentTemplate(
            id=f"tmpl-{uuid.uuid4().hex[:12]}",
            name=name,
            description=str(body.get("description", "")),
            spec=spec,
            version=str(body.get("version", "1.0.0")),
            created_by=caller or "anonymous",
            tags=tuple(body.get("tags", [])),
            is_public=bool(body.get("is_public", False)),
        )
        experiment_archive.store_template(template)
        h._send(201, json.dumps(template.to_dict()), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except Exception:
        log_event("internal_error", request_id=request_id, route="templates-create")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

    return False


def post_api_experiments_versions(h, request_id, timer, path, query):
    """Route if path.startswith("/api/experiments/") and path.endswith("/versions"): (moved verbatim from api.py do_POST)."""
    parts = path.strip("/").split("/")
    if len(parts) == 4:
        experiment_id = parts[2]
        body, raw = h._read_json()
        if body == "overflow":
            h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 413, "validation")
            return True
        if body is None:
            h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
        if not ok:
            h._finish(timer, request_id, "POST", path, 401, "auth")
            return True
        try:
            from rift.experiments import experiment_archive
            # Validate the version spec through the canonical validator
            # (module-global; must not be re-imported locally here or
            # it shadows the global for every other do_POST path).
            try:
                spec = validate_spec_payload(body.get("spec") or {})
            except ValueError as exc:
                h._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            store = SupabaseStore()
            if store.configured:
                row, err = _fetch_supabase_row(store, "experiment", experiment_id)
                if err == "unavailable":
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                    return True
                if row:
                    if owner_mismatch(row.get("user_id"), caller):
                        h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                        h._finish(timer, request_id, "POST", path, 403, "auth")
                        return True
                    # Versions are standalone records; never seed the list
                    # with the experiment itself (that creates a circular
                    # reference that breaks JSON serialization).
                    existing = row.get("versions")
                    if not isinstance(existing, list):
                        # Pre-migration rows lack the versions column:
                        # seed from the archive mirror instead (gated).
                        exp = experiment_archive.get_experiment(experiment_id)
                        if exp and owner_mismatch(exp.get("user_id"), caller):
                            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                            h._finish(timer, request_id, "POST", path, 403, "auth")
                            return True
                        existing = (exp or {}).get("versions", [])
                    existing = [v for v in existing if isinstance(v, dict)]
                    version = body.get("version", len(existing) + 1)
                    new_version = {
                        "version": version,
                        "spec": spec.to_dict(),
                        "fingerprint": spec.fingerprint(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "created_by": caller or "anonymous",
                        "description": body.get("description", ""),
                    }
                    updated = existing + [new_version]
                    try:
                        store.update_experiment(experiment_id, {"versions": updated, "status": "configured"})
                    except Exception as exc:
                        msg = str(exc).lower()
                        if "42703" in msg or ("versions" in msg and ("does not exist" in msg or "column" in msg)):
                            # Database predates migration 008: archive-only
                            # write, flagged honestly as non-durable.
                            log_event("versions_not_durable", request_id=request_id, experiment_id=experiment_id)
                            exp = experiment_archive.get_experiment(experiment_id) or {"id": experiment_id}
                            exp["versions"] = updated
                            exp["status"] = "configured"
                            experiment_archive.store_experiment(exp)
                            h._send(201, json.dumps({"experiment_id": experiment_id, "version": new_version, "durable": False}), request_id=request_id)
                            h._finish(timer, request_id, "POST", path, 201)
                            return True
                        log_event("dependency_failure", request_id=request_id, dependency="supabase")
                        h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                        h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                        return True
                    try:
                        exp = experiment_archive.get_experiment(experiment_id)
                        if exp:
                            exp["versions"] = updated
                            exp["status"] = "configured"
                            experiment_archive.store_experiment(exp)
                    except Exception:
                        log_event("mirror_failure", request_id=request_id, experiment_id=experiment_id)
                    h._send(201, json.dumps({"experiment_id": experiment_id, "version": new_version, "durable": True}), request_id=request_id)
                    h._finish(timer, request_id, "POST", path, 201)
                    return True
                # Supabase-miss: fall through to the archive path below.
            exp = experiment_archive.get_experiment(experiment_id)
            if not exp:
                h._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 404, "not_found")
                return True
            if owner_mismatch(exp.get("user_id"), caller):
                h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 403, "auth")
                return True
            # Versions are standalone records; never seed the list
            # with the experiment itself (that creates a circular
            # reference that breaks JSON serialization).
            existing = [v for v in exp.get("versions", []) if isinstance(v, dict)]
            version = body.get("version", len(existing) + 1)
            new_version = {
                "version": version,
                "spec": spec.to_dict(),
                "fingerprint": spec.fingerprint(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": caller or "anonymous",
                "description": body.get("description", ""),
            }
            exp["versions"] = existing + [new_version]
            exp["status"] = "configured"
            experiment_archive.store_experiment(exp)
            h._send(201, json.dumps({"experiment_id": experiment_id, "version": new_version, "durable": False}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 201)
        except Exception:
            log_event("internal_error", request_id=request_id, route="versions-create")
            h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 500, "internal")
        return True

    return False


def post_api_experiments_compare(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/compare": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.experiments import experiment_archive, comparison_engine
        comparison_type = body.get("type", "optimizer")
        baseline_id = body.get("baseline_id")
        candidate_ids = body.get("candidate_ids", [])
        if not baseline_id or not candidate_ids:
            h._send(400, json.dumps({"error": "baseline_id and candidate_ids required"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        store = SupabaseStore()

        def _resolve(run_id: str):
            # Supabase first when configured (ownership-enforced),
            # then the local archive mirror (dual-written on create,
            # ownership-enforced too). Uses the no-send fetch: _load_row
            # responds itself, so it must not be used on paths that fall
            # through to the archive (double-send + silent stale reads).
            # A genuine Supabase outage surfaces as "unavailable" (the
            # caller 502s) instead of quietly serving the mirror.
            if store.configured:
                row, err = _fetch_supabase_row(store, "run", run_id)
                if err == "unavailable":
                    return "unavailable", None
                if row:
                    if owner_mismatch(row.get("user_id"), caller):
                        return "forbidden", None
                    exp_row, exp_err = _fetch_supabase_row(
                        store, "experiment", row.get("experiment_id", ""))
                    if exp_err == "unavailable":
                        return "unavailable", None
                    if exp_row:
                        if owner_mismatch(exp_row.get("user_id"), caller):
                            return "forbidden", None
                        spec = _spec_from_experiment_row(exp_row)
                        if spec is not None:
                            run = _run_from_row(row, spec)
                            if run is not None:
                                return None, run
                    # Supabase has the run but the chain does not adapt
                    # (or the experiment is missing there): fall through
                    # to the archive mirror below.
            run = experiment_archive.find_run(run_id)
            if run is not None:
                if owner_mismatch(getattr(run, "user_id", None), caller):
                    return "forbidden", None
                return None, run
            return "missing", None

        forbidden = False
        unavailable = False
        candidate_runs = []
        err, baseline_run = _resolve(str(baseline_id))
        if err == "forbidden":
            forbidden = True
        elif err == "unavailable":
            unavailable = True
        else:
            for cid in candidate_ids:
                err, run = _resolve(str(cid))
                if err == "forbidden":
                    forbidden = True
                    break
                if err == "unavailable":
                    unavailable = True
                    break
                if run is not None:
                    candidate_runs.append(run)
        if forbidden:
            h._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 403, "auth")
            return True
        if unavailable:
            log_event("dependency_failure", request_id=request_id, dependency="supabase")
            h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 502, "persistence_error")
            return True
        if not baseline_run:
            h._send(404, json.dumps({"error": "baseline_not_found"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 404, "not_found")
            return True
        if comparison_type == "optimizer":
            result = comparison_engine.compare_optimizers(baseline_run, candidate_runs)
        elif comparison_type == "model":
            result = comparison_engine.compare_models(baseline_run, candidate_runs)
        elif comparison_type == "perturbation":
            result = comparison_engine.compare_perturbations(baseline_run, candidate_runs)
        elif comparison_type == "robustness":
            result = comparison_engine.compare_robustness(baseline_run, candidate_runs)
        elif comparison_type == "regression":
            result = comparison_engine.compare_regression(baseline_run, candidate_runs)
        else:
            h._send(400, json.dumps({"error": "invalid_comparison_type"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        experiment_archive.store_comparison(result)
        h._send(201, json.dumps(result.to_dict()), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except Exception:
        log_event("internal_error", request_id=request_id, route="experiments-compare")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

    return False


def post_api_experiments_import(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/import": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    caller, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.experiments import experiment_archive
        new_name = body.get("name")
        package = body.get("package")
        if not package:
            h._send(400, json.dumps({"error": "package required"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        store = SupabaseStore()
        if store.configured:
            # Persist authoritatively so imports survive restart; the
            # archive only mirrors back (uniform uuid ids, no split brain).
            # A package's original owner claim is never trusted: the
            # importer becomes the owner of everything imported.
            try:
                spec = _spec_from_import_package(package)
            except ValueError as exc:
                h._send(400, json.dumps({"error": "invalid_package", "detail": str(exc)[:300]}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            try:
                result = store.create_experiment({
                    "name": new_name or spec.name,
                    "description": spec.description,
                    "scenario": {"name": spec.scenario_name, "initial_state": spec.initial_state},
                    "perturbations": list(spec.perturbations),
                    "policy_variables": list(spec.policy_variables),
                    "optimizer_config": {"optimizer": spec.optimizer, "backend": spec.backend, "seed": spec.seed},
                    "backend": spec.backend,
                    "seed": spec.seed,
                    "engine_version": spec.engine_version,
                    "fingerprint": spec.fingerprint(),
                    "status": "created",
                    **({"user_id": caller} if caller else {}),
                })
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
                h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                return True
            sup_row = result.data or {}
            sup_id = sup_row.get("id")
            _mirror_experiment_to_archive(spec, sup_row, caller)
            runs_imported = 0
            for rd in package.get("runs", []) if isinstance(package, dict) else []:
                if not isinstance(rd, dict):
                    continue
                run_payload = {
                    "experiment_id": sup_id,
                    "optimizer": str(rd.get("optimizer", spec.optimizer)),
                    "result": rd.get("result") if isinstance(rd.get("result"), dict) else None,
                    "metrics": dict(rd.get("metrics") or {}),
                    "seed": rd.get("seed"),
                    "backend": str(rd.get("backend", "statevector-simulator")),
                    "engine_version": str(rd.get("engine_version", ENGINE_VERSION)),
                    **({"user_id": caller} if caller else {}),
                }
                try:
                    run_result = store.create_run(run_payload)
                except Exception:
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    h._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    h._finish(timer, request_id, "POST", path, 502, "persistence_error")
                    return True
                _mirror_run_to_archive(sup_id, spec, run_payload, run_result.data or {})
                runs_imported += 1
            h._send(201, json.dumps({"experiment_id": sup_id, "durable": True, "runs_imported": runs_imported}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 201)
            return True
        try:
            new_id = experiment_archive.import_experiment(package, new_name, owner=caller)
        except ValueError as exc:
            h._send(400, json.dumps({"error": "invalid_package", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        h._send(201, json.dumps({"experiment_id": new_id, "durable": False}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except Exception:
        log_event("internal_error", request_id=request_id, route="experiments-import")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

    return False


def _spec_from_import_package(package: dict):
    """Extract + validate one ExperimentSpec from an import package.

    Prefers the experiment entry's spec, then the first run spec, then
    the Supabase-row column shape. Raises ValueError when nothing
    validates (caller: 400, fail closed).
    """
    exp_data = package.get("experiment") if isinstance(package, dict) else None
    if isinstance(exp_data, dict) and isinstance(exp_data.get("spec"), dict):
        # An explicitly present spec must validate (fail closed); the
        # row-shape adapter below is only for spec-less row exports and
        # must never mask a bad nested spec with defaults.
        try:
            return validate_spec_payload(exp_data["spec"])
        except ValueError as exc:
            raise ValueError(f"invalid experiment spec: {exc}")
    for rd in (package.get("runs") or []) if isinstance(package, dict) else []:
        if isinstance(rd, dict) and isinstance(rd.get("spec"), dict):
            try:
                return validate_spec_payload(rd["spec"])
            except ValueError as exc:
                raise ValueError(f"invalid run spec: {exc}")
            break
    if isinstance(exp_data, dict):
        spec = _spec_from_experiment_row(exp_data)
        if spec is not None:
            return spec
    raise ValueError("package contains no valid experiment spec")


def post_api_experiments_scheduler_jobs(h, request_id, timer, path, query):
    """Route if path == "/api/experiments/scheduler/jobs": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    _, ok = h._identity(request_id, body if isinstance(body, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.experiments import local_scheduler
        experiment_id = str(body.get("experiment_id", "") or "").strip()
        if not experiment_id:
            h._send(400, json.dumps({"error": "experiment_id is required"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        try:
            spec = validate_spec_payload(body.get("spec") or {})
        except ValueError as exc:
            h._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        run_at = body.get("run_at")
        repeat = body.get("repeat")
        if repeat not in (None, "hourly", "daily"):
            h._send(400, json.dumps({"error": "repeat must be hourly, daily, or omitted"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        job_id = local_scheduler.schedule(experiment_id, spec, run_at=run_at, repeat=repeat)
        local_scheduler.start()
        h._send(201, json.dumps({"job_id": job_id, "status": "scheduled", "run_at": run_at, "repeat": repeat}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except Exception:
        log_event("internal_error", request_id=request_id, route="scheduler-create")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

    return False
