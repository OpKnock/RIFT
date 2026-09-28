"""Route handlers (split verbatim from api.py; see package README)."""
from __future__ import annotations

from rift import __version__ as ENGINE_VERSION
import json
from rift.observability import log_event
import os
from rift.auth import service_token_configured


def get_api_twin_demo(h, request_id, timer, path, query):
    """Route if path == "/api/twin/demo": (moved verbatim from api.py do_GET)."""
    try:
        from rift.health.demo_data import demo_stream
        from rift.health.ehr import demo_ehr, normalize_ehr
        from rift.health.twin import DigitalTwin

        raw_t = (query.get("t") or ["13"])[0]
        try:
            day = int(raw_t)
        except (TypeError, ValueError):
            raise ValueError(f"invalid replay day: {raw_t!r}")
        if not 0 <= day <= 13:
            raise ValueError(f"replay day {day} out of range [0, 13]")
        ehr, ehr_issues = normalize_ehr(demo_ehr())
        twin = DigitalTwin(ehr, demo_stream())
        snapshot = twin.update(day)
        payload = {
            **snapshot,
            "meta": {
                "engine": "rift",
                "engine_version": ENGINE_VERSION,
                "capability": "patient-digital-twin",
                "dataset": "synthetic 14-day demo series (seed 42); NOT clinically validated",
                "ehr_issues": ehr_issues,
                "safety": "decision support only; human-in-the-loop required",
            },
        }
        h._send(200, json.dumps(payload), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except (ValueError, KeyError, TypeError) as exc:
        log_event("validation_failure", request_id=request_id, detail=str(exc)[:200])
        h._send(422, json.dumps({"error": "invalid twin request", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 422, "validation")
    except Exception:
        log_event("internal_error", request_id=request_id, route="twin-demo")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True


def get_api_twin_prospective(h, request_id, timer, path, query):
    """Route if path == "/api/twin/prospective": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.health import prospective as _pros
        h._send(200, json.dumps(_pros.manager.stats()), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "prospective_error", "request_id": request_id}),
                   request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True


def get_api_twin_reviews(h, request_id, timer, path, query):
    """Route if path == "/api/twin/reviews": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id, None, query)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.health import reviews as _rev
        h._send(200, json.dumps({
            "stats": _rev.ledger.stats(),
            "reviews": _rev.ledger.list(),
        }), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "reviews_error", "request_id": request_id}),
                   request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True


def get_api_explainability_audit(h, request_id, timer, path, query):
    """Route if path == "/api/explainability/audit": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.explainability import audit_log
        h._send(200, json.dumps({"records": [r.to_dict() for r in audit_log.query(limit=200)]}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "audit_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True



def get_api_explainability_evidence(h, request_id, timer, path, query):
    """Route if path == "/api/explainability/evidence": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.explainability import evidence_store
        h._send(200, json.dumps({"packages": [p.to_dict() for p in evidence_store._packages.values()]}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "evidence_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True



def get_api_intelligence_status(h, request_id, timer, path, query):
    """Route if path == "/api/intelligence/status": (moved verbatim from api.py do_GET)."""
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.advanced_intelligence import llm_provider
        provider = type(llm_provider).__name__
        h._send(200, json.dumps({
            "provider": provider,
            "mock": provider == "MockLLMProvider",
            "openai_compatible_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "note": ("Mock provider: NL endpoints return deterministic "
                     "placeholder outputs. Set OPENAI_API_KEY (and "
                     "optionally OPENAI_BASE_URL) to enable a real "
                     "OpenAI-compatible provider.")
            if provider == "MockLLMProvider" else
            "Real LLM provider active; all explanations remain grounded in deterministic artifacts.",
        }), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "intelligence_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True



def get_api_twin_evidence(h, request_id, timer, path, query):
    """Route if path == "/api/twin/evidence": (moved verbatim from api.py do_GET)."""
    try:
        from rift.health.demo_data import demo_series
        from rift.health.ehr import demo_ehr, normalize_ehr
        from rift.health.evaluate import (
            EXTERNAL_SERIES_CONFIG,
            OUTCOME_RULE,
            backtest,
            calibration_report,
            external_validation,
            reliability,
            stress_sweep,
        )
        from rift.health.model_registry import deployment_gate, get_model, verify_weights
        from rift.health.subgroups import subgroup_metrics
        from rift.health.twin import DigitalTwin

        ehr, _ = normalize_ehr(demo_ehr())
        long_twin = DigitalTwin(ehr, demo_series())
        held_out = backtest(long_twin, 30, 59)
        stress = stress_sweep(demo_series(), ehr, list(range(30, 45)))
        calibration = calibration_report(
            [d for d in held_out["per_day"] if d["day"] < 45],
            [d for d in held_out["per_day"] if d["day"] >= 45],
            methods=("platt", "isotonic", "beta"),
        )
        # Use Platt for external validation (backward compatibility)
        platt_params = calibration["methods"]["platt"]["params"]
        external = external_validation(
            stream=demo_series(
                seed=EXTERNAL_SERIES_CONFIG["seed"],
                days=EXTERNAL_SERIES_CONFIG["days"],
                spells=EXTERNAL_SERIES_CONFIG["spells"],
            ),
            ehr=ehr,
            params=platt_params,
            source_id=EXTERNAL_SERIES_CONFIG["source_id"],
            day_start=0,
            day_end=EXTERNAL_SERIES_CONFIG["days"] - 1,
        )
        payload = {
            "labels": held_out["labels"],
            "outcome_rule": OUTCOME_RULE["description"],
            "calibration_window": "days 0-29",
            "held_out_window": "days 30-59",
            "days_evaluated": held_out["days_evaluated"],
            "mae": held_out["mae"],
            "event_agreement": held_out["event_agreement"],
            "sensitivity": held_out["sensitivity"],
            "specificity": held_out["specificity"],
            "brier": held_out["brier"],
            "interval_coverage": held_out["interval_coverage"],
            "onset_lags": held_out["onset_lags"],
            "mean_onset_lag": held_out["mean_onset_lag"],
            "confusion": held_out["confusion"],
            "reliability": reliability(held_out),
            "subgroups": subgroup_metrics(held_out["per_day"]),
            "cohort": __import__("rift.health.cohort", fromlist=["cohort_backtest"]).cohort_backtest(),
            "prospective": __import__("rift.health.prospective", fromlist=["manager"]).manager.stats(),
            "calibration_repair": {
                "method": "platt-scaling fit on days 30-44 only (also isotonic, beta)",
                "params": calibration["methods"]["platt"]["params"],
                "test_window": "days 45-59 (untouched)",
                "raw": {k: calibration["methods"]["platt"]["raw"][k] for k in ("brier", "ece")},
                "calibrated": {k: calibration["methods"]["platt"]["calibrated"][k] for k in ("brier", "ece")},
                "isotonic": {k: calibration["methods"]["isotonic"]["calibrated"][k] for k in ("brier", "ece")},
                "beta": {k: calibration["methods"]["beta"]["calibrated"][k] for k in ("brier", "ece")},
            },
            "external_validation": {
                k: external[k] for k in (
                    "source_id", "status", "days_evaluated", "events",
                    "params_used", "recalibrated", "event_agreement",
                    "agreement_ci95", "sensitivity", "specificity",
                    "brier_raw", "brier_calibrated", "ece_raw",
                    "ece_calibrated", "slope_intercept",
                    "interval_coverage", "sample_adequacy",
                    "confusion", "warnings",
                )
            },
            "stress": stress,
            "meta": {
                "engine": "rift",
                "engine_version": ENGINE_VERSION,
                "dataset": "synthetic 60-day series (seed 7); NOT clinically validated",
                "calibration": "demo / not calibrated",
                "model": get_model(),
                "weights_verified": verify_weights(),
                "deployment_gate": deployment_gate(get_model()["model_id"], {
                    "source": "live external_validation block in this response",
                    "events": external.get("events") or 0,
                    "non_events": (external.get("days_evaluated") or 0) - (external.get("events") or 0),
                    "calibrated": False,
                    "clinical_review": False,
                    "synthetic": True,
                }),
            },
        }
        h._send(200, json.dumps(payload), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        log_event("internal_error", request_id=request_id, route="twin-evidence")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True


def post_api_twin_reviews(h, request_id, timer, path, query):
    """Route if path == "/api/twin/reviews": (moved verbatim from api.py do_POST)."""
    body, raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if not isinstance(body, dict):
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    owner, ok = h._identity(request_id, body, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.health import reviews as _rev
        from rift.health.monitoring import collector as _ops
        # Reviewer identity comes from the authenticated principal.
        # A caller-supplied reviewer_id that disagrees with it is
        # rejected (fail-closed identity); in open dev mode with no
        # authenticated principal the asserted id is accepted but
        # explicitly marked unverified in the audit entry.
        claimed = str(body.get("reviewer_id", "") or "").strip()
        from rift.auth_jwt import jwt_mode_enabled as _jwt_mode
        auth_on = service_token_configured() is not None or _jwt_mode()
        if owner:
            if claimed and claimed != owner:
                h._send(400, json.dumps({"error": "identity_mismatch", "detail": "reviewer_id must match the authenticated principal"}), request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            reviewer_id, verified = owner, True
        elif auth_on:
            # Auth is configured but no principal resolved: a review
            # without an attributable reviewer is not auditable.
            h._send(400, json.dumps({"error": "missing_user_id", "detail": "submit user_id (service-token mode) or a Bearer token (JWT mode) so the review is attributable"}), request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        else:
            reviewer_id, verified = claimed, False
        entry = _rev.ledger.record(
            action=body.get("action", ""),
            evidence_id=body.get("evidence_id", ""),
            reviewer_id=reviewer_id,
            rationale=body.get("rationale", ""),
            supersedes=body.get("supersedes"),
            identity_verified=verified,
        )
        try:
            _ops.record_review(entry["action"])
        except Exception:  # nosec B110 -- monitoring is best-effort
            pass
        h._send(201, json.dumps(entry), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 201)
    except ValueError as exc:
        h._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}),
                   request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
    except Exception:
        log_event("internal_error", request_id=request_id, route="twin-reviews")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}),
                   request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True



def post_api_twin_prospective(h, request_id, timer, path, query):
    """Route if path == "/api/twin/prospective": (moved verbatim from api.py do_POST)."""
    # POST mirrors GET query-param handling inside POST body.
    # State-mutating (lock/reconcile): gated like the GET.
    parsed_q2 = {}
    body2, _ = h._read_json()
    if body2 == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if body2 is None:
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    _, ok = h._identity(request_id, body2 if isinstance(body2, dict) else None, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.health import prospective as _pros2
        action = (body2 or {}).get("action") or "lock"
        if action == "lock":
            from rift.health.demo_data import demo_series
            from rift.health.ehr import demo_ehr, normalize_ehr
            from rift.health.twin import DigitalTwin
            ehr, _ = normalize_ehr(demo_ehr())
            snap = DigitalTwin(ehr, demo_series()).update(10)
            rec = _pros2.manager.lock_prediction(
                patient_id=snap["patient_id"], day=snap["day_index"],
                predicted_risk=snap["risk"]["risk"],
                predicted_event=snap["risk"]["event_predicted"],
                input_hash=snap["provenance"]["input_hash"])
            h._send(200, json.dumps(rec), request_id=request_id)
        elif action == "reconcile":
            lock_id = (body2 or {}).get("lock_id")
            realized = (body2 or {}).get("realized_event")
            if not lock_id or not isinstance(realized, bool):
                h._send(400, json.dumps({"error": "lock_id and realized_event required"}),
                           request_id=request_id)
                h._finish(timer, request_id, "POST", path, 400, "validation")
                return True
            else:
                h._send(200, json.dumps(_pros2.manager.reconcile_outcome(lock_id, realized)),
                           request_id=request_id)
        else:
            h._send(200, json.dumps(_pros2.manager.stats()), request_id=request_id)
    except Exception:
        h._send(500, json.dumps({"error": "prospective_error", "request_id": request_id}),
                   request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
        return True
    h._finish(timer, request_id, "POST", path, 200)
    return True


def post_api_intelligence_scenario(h, request_id, timer, path, query):
    """Route if path == "/api/intelligence/scenario": (moved verbatim from api.py do_POST)."""
    # Natural language -> validated ExperimentSpec. The LLM proposes;
    # validate_spec_payload disposes: invalid specs 400, never execute.
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
    description = str((body if isinstance(body, dict) else {}).get("description", "") or "").strip()
    if not description:
        h._send(400, json.dumps({"error": "description is required"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    try:
        from rift.advanced_intelligence import create_scenario_nl, llm_provider
        result = create_scenario_nl(description)
        result["provider"] = type(llm_provider).__name__
        result["mock"] = type(llm_provider).__name__ == "MockLLMProvider"
        status = 200 if result.get("valid") else 422
        h._send(status, json.dumps(result), request_id=request_id)
        h._finish(timer, request_id, "POST", path, status)
    except Exception:
        log_event("internal_error", request_id=request_id, route="intelligence-scenario")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True



def post_api_intelligence_explain(h, request_id, timer, path, query):
    """Route if path == "/api/intelligence/explain": (moved verbatim from api.py do_POST)."""
    # Grounded explanation of a twin snapshot: the snapshot is
    # computed deterministically first, the LLM only narrates it.
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
        day = (body if isinstance(body, dict) else {}).get("day", 13)
        try:
            day = int(day)
        except (TypeError, ValueError):
            raise ValueError(f"invalid day: {day!r}")
        if not 0 <= day <= 13:
            raise ValueError(f"day {day} out of range [0, 13]")
        from rift.health.demo_data import demo_stream
        from rift.health.ehr import demo_ehr, normalize_ehr
        from rift.health.twin import DigitalTwin
        from rift.advanced_intelligence import explain_grounded, llm_provider
        ehr, _ = normalize_ehr(demo_ehr())
        snapshot = DigitalTwin(ehr, demo_stream()).update(day)
        result = explain_grounded(snapshot, snapshot.get("guardian", {}))
        result["provider"] = type(llm_provider).__name__
        result["mock"] = type(llm_provider).__name__ == "MockLLMProvider"
        h._send(200, json.dumps(result), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 200)
    except (ValueError, KeyError, TypeError) as exc:
        h._send(422, json.dumps({"error": "invalid intelligence request", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 422, "validation")
    except Exception:
        log_event("internal_error", request_id=request_id, route="intelligence-explain")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True

