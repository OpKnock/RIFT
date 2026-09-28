"""Shared helpers for route handlers (moved verbatim from rift.api).

Single home for module-level helpers/constants the handlers need.
rift.api re-exports what it still uses; no state is duplicated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from rift import __version__ as ENGINE_VERSION
from rift.auth import owner_mismatch
from rift.benchmark import benchmark_suite
from rift.billing import (
    BillingNotConfigured,
    CheckoutRequest,
    LemonSqueezyProvider,
    idempotency_key as billing_idempotency_key,
    is_entitled,
    parse_webhook_event,
    subscription_update_from_event,
    verify_webhook_signature,
    webhook_event_id,
)
from rift.causal import emergency_causal_graph
from rift.counterfactual import generate_futures
from rift.futures import branch_futures
from rift.limits import SCENARIO_BOUNDS
from rift.models import Scenario
from rift.multivariable import (
    build_robust_qubo_projection,
    exact_multivariable_robust_minimize,
    optimize_policy_space,
)
from rift.observability import log_event
from rift.optimizer import QUBO, QuantumOptimizer, exact_minimize
from rift.robust import rank_robust_candidates
from rift.robust_qubo import build_robust_qubo, robust_policy_cost
from rift.scenarios import emergency_building
from rift.uncertainty import normalized_risk_entropy
from rift.verifier import verify_under_perturbations
import os
import uuid


FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend-dist"


PERTURBATIONS = [
    {"smoke": 2.0},
    {"crowd": 80.0},
    {"smoke": 2.0, "crowd": 80.0},
    {"corridor_capacity": -70.0},
]


POLICY_VARIABLES = ("route_a", "route_c", "stairwell_b")


# In-memory webhook dedup for offline mode (bounded; DB is authoritative).
_SEEN_WEBHOOK_KEYS: list[str] = []


class _ClientGone(Exception):
    """Control-flow: SSE client disconnected mid-stream (not an error)."""


def _publish_event(topic: str, payload: dict) -> None:
    """Best-effort publish to the in-process event bus (SSE fan-out).

    Never raises: telemetry must not break request handling. Failures
    are invisible by design — the bus is in-memory and lossy.
    """
    try:
        from rift.realtime import event_bus
        event_bus.publish_sync(topic, payload)
    except Exception:  # nosec B110 -- see docstring
        pass


def _spec_from_experiment_row(row: dict) -> "ExperimentSpec | None":
    """Rebuild a validated spec from a Supabase experiment row (or None).

    Lets Supabase-persisted experiments participate in archive-backed
    flows (compare/export/replay) without duplicating engine logic.
    Returns None when the row cannot be validated (fail-soft: callers
    treat the experiment as unresolvable, never as valid-by-default).
    """
    try:
        from rift.experiments import validate_spec_payload
        scenario = row.get("scenario") or {}
        cfg = row.get("optimizer_config") or {}
        return validate_spec_payload({
            "name": row.get("name", ""),
            "scenario_name": scenario.get("name", "smart-building-emergency"),
            "initial_state": scenario.get("initial_state", {}),
            "perturbations": row.get("perturbations", []),
            "policy_variables": row.get("policy_variables", []),
            "optimizer": cfg.get("optimizer", "exact"),
            "backend": row.get("backend", "statevector-simulator"),
            "seed": row.get("seed"),
            "description": row.get("description", ""),
        })
    except Exception:
        return None


def _run_from_row(row: dict, spec: "ExperimentSpec") -> "ExperimentRun | None":
    """Adapt a Supabase run row to an ExperimentRun (or None)."""
    try:
        from rift.experiments import ExperimentRun
        metrics = row.get("metrics")
        result = row.get("result")
        return ExperimentRun(
            id=str(row.get("id", "")),
            experiment_id=str(row.get("experiment_id", "")),
            experiment_version=int(row.get("experiment_version", 1)),
            spec=spec,
            optimizer=str(row.get("optimizer", spec.optimizer)),
            metrics=dict(metrics) if isinstance(metrics, dict) else {},
            result=dict(result) if isinstance(result, dict) else None,
            seed=row.get("seed"),
            engine_version=str(row.get("engine_version", ENGINE_VERSION)),
            started_at=str(row.get("created_at") or datetime.now(timezone.utc).isoformat()),
            completed_at=row.get("completed_at"),
            status=str(row.get("status", "succeeded")),
            user_id=row.get("user_id"),
        )
    except Exception:
        return None


def _fetch_supabase_row(store: "SupabaseStore", kind: str,
                          obj_id: str) -> tuple[dict, str | None]:
    """Fetch one Supabase row without sending any response.

    Returns (row_dict, error). A clean miss yields ({}, None); a genuine
    transport/API failure yields ({}, "unavailable"). Unlike _load_row
    this never sends, so callers with archive fallbacks cannot
    double-respond on outage paths.
    """
    if not store.configured:
        return {}, None
    get = store.get_experiment if kind == "experiment" else store.get_run
    try:
        fetched = get(obj_id)
    except Exception as exc:
        if not _is_not_found_error(exc):
            log_event("dependency_failure", dependency="supabase")
            return {}, "unavailable"
        return {}, None
    return (fetched.data if fetched else None) or {}, None


def _spec_from_payload(payload: dict) -> "ExperimentSpec | None":
    """Best-effort ExperimentSpec from a resolved experiment payload.

    Handles both shapes: archive mirrors (nested spec dict) and Supabase
    rows (scenario/optimizer_config columns). Returns None when neither
    parses, letting callers fall back to raw row dicts.
    """
    if isinstance(payload.get("spec"), dict):
        try:
            from rift.experiments import ExperimentSpec
            return ExperimentSpec(**payload["spec"])
        except Exception:
            pass
    try:
        return _spec_from_experiment_row(payload)
    except Exception:
        return None


def _resolve_experiment(store: "SupabaseStore", experiment_id: str,
                        caller: str | None) -> tuple[dict | None, dict | None, str | None]:
    """Single resolve path for experiment reads (persistence unification).

    Supabase first when configured (ownership-enforced). The archive
    mirror is only consulted when Supabase is NOT configured: once the
    database is authoritative, a clean miss means "missing" (404) — a
    deleted row must never resurrect from a stale mirror, and an outage
    surfaces as "unavailable" (callers must 502, never serve the mirror).
    Archive records carry user_id so the unconfigured path enforces the
    same tenant boundary. Payload shape mirrors the Supabase row so
    callers treat both stores uniformly.

    Never sends responses (unlike _load_row): callers own status codes,
    so fallback never double-sends. A Supabase transport error surfaces
    as "unavailable" (caller: 502) rather than silently falling back to
    a potentially stale mirror as if authoritative.
    """
    from rift.experiments import experiment_archive
    row, err = _fetch_supabase_row(store, "experiment", experiment_id)
    if err:
        return None, None, err
    if row:
        if owner_mismatch(row.get("user_id"), caller):
            return None, None, "forbidden"
        spec = _spec_from_experiment_row(row)
        return (dict(row), spec.to_dict() if spec is not None else None, None)
    if store.configured:
        # Authoritative miss: the archive is only a mirror/cache, never a
        # second source of truth. A deleted row must not resurrect here.
        return None, None, "missing"
    exp = experiment_archive.get_experiment(experiment_id)
    if exp:
        # The archive mirror is not authoritative, but it is also not
        # public: enforce the same tenant boundary (stale or deleted
        # Supabase rows must not leak across owners via the mirror).
        if owner_mismatch(exp.get("user_id"), caller):
            return None, None, "forbidden"
        return (dict(exp), exp.get("spec") if isinstance(exp.get("spec"), dict) else None, None)
    return None, None, "missing"


def _resolve_run(store: "SupabaseStore", run_id: str,
                 caller: str | None) -> tuple[dict | None, str | None]:
    """Single resolve path for run reads. Returns (payload_dict, error)."""
    from rift.experiments import experiment_archive
    row, err = _fetch_supabase_row(store, "run", run_id)
    if err:
        return None, err
    if row:
        if owner_mismatch(row.get("user_id"), caller):
            return None, "forbidden"
        return dict(row), None
    if store.configured:
        return None, "missing"
    run = experiment_archive.find_run(run_id)
    if run is not None:
        if owner_mismatch(getattr(run, "user_id", None), caller):
            return None, "forbidden"
        return run.to_dict(), None
    return None, "missing"


def _mirror_experiment_to_archive(spec: "ExperimentSpec", row: dict, owner: str | None) -> None:
    """Mirror a Supabase-persisted experiment into the local archive.

    Makes Supabase rows visible to archive-backed flows (compare/export/
    replay/templates) without a second query path in every handler.
    Best-effort: mirror failures never break the authoritative write.
    """
    try:
        from rift.experiments import experiment_archive
        record = {
            "id": row.get("id"),
            "name": spec.name,
            "scenario_name": spec.scenario_name,
            "spec": spec.to_dict(),
            "fingerprint": spec.fingerprint(),
            "status": row.get("status", "created"),
            "versions": [],
            # user_id (not just created_by) so archive reads can enforce
            # the same tenant boundary as Supabase rows.
            "user_id": row.get("user_id") or owner,
            "created_by": owner or "anonymous",
            "mirrored_from": "supabase",
            "mirrored_at": datetime.now(timezone.utc).isoformat(),
        }
        experiment_archive.store_experiment(record)
    except Exception:  # nosec B110 -- mirror is best-effort
        pass


def _mirror_run_to_archive(experiment_id: str, spec: "ExperimentSpec",
                           run_payload: dict, result_row: dict | None) -> None:
    """Mirror a Supabase-persisted run into the local archive (best-effort)."""
    try:
        from rift.experiments import experiment_archive, ExperimentRun
        import uuid as _uuid
        row = result_row or {}
        run = ExperimentRun(
            id=str(row.get("id") or f"run-{_uuid.uuid4().hex[:12]}"),
            experiment_id=experiment_id,
            experiment_version=int(row.get("experiment_version", 1)),
            spec=spec,
            optimizer=str(run_payload.get("optimizer", spec.optimizer)),
            metrics=dict(run_payload.get("metrics") or {}),
            result=dict(run_payload["result"]) if isinstance(run_payload.get("result"), dict) else None,
            seed=run_payload.get("seed"),
            engine_version=str(row.get("engine_version", ENGINE_VERSION)),
            started_at=str(row.get("created_at") or datetime.now(timezone.utc).isoformat()),
            completed_at=row.get("completed_at"),
            status=str(row.get("status", "succeeded")),
            user_id=row.get("user_id") or run_payload.get("user_id"),
        )
        experiment_archive.store_run(run)
    except Exception:  # nosec B110 -- mirror is best-effort
        pass


def _cors_allowed_origins() -> list[str]:
    """Explicit CORS allow-list (no wildcard). Defaults cover local dev.

    Override with RIFT_CORS_ORIGINS as a comma-separated list, e.g.
    "https://app.example.com". Fronted production deployments may
    alternatively terminate CORS at the edge and leave this empty — an
    empty list disables CORS headers entirely.
    """
    raw = os.getenv("RIFT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


def _cors_headers(origin: str | None) -> dict[str, str]:
    """CORS headers for a request Origin, or {} when not allowed.

    Echoes the Origin only when it is on the explicit allow-list, so
    credentialed (Bearer) cross-origin calls from the dev UI work while
    arbitrary origins stay blocked.
    """
    if not origin:
        return {}
    if origin not in _cors_allowed_origins():
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Request-ID",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }


def _seen_webhook_key(key: str | None) -> bool:
    """Check-only: True when this key was fully processed before."""
    return bool(key) and key in _SEEN_WEBHOOK_KEYS


def _apply_subscription_update(store, event: dict, request_id: str | None) -> bool:
    """Apply the subscription-mirror side effect idempotently.

    Returns True when there is nothing to apply or the upsert succeeded.
    Returns False on failure — callers must answer 502 so the provider
    retries, since a recorded event without its subscription mirror would
    leave entitlements stale. Single choke point so the duplicate,
    unique-violation, and fresh paths cannot drift apart.
    """
    update = subscription_update_from_event(event)
    if update is None:
        return True
    try:
        row = dict(update)
        custom = event.get("custom_data") or {}
        if custom.get("user_id"):
            row["user_id"] = custom["user_id"]
        store.upsert_subscription(row)
        return True
    except Exception:
        log_event("dependency_failure", request_id=request_id, dependency="supabase")
        return False


def _remember_webhook_key(key: str | None) -> None:
    """Record a key ONLY after durable processing succeeded.

    Never call this on failure paths: a 502 must leave the key
    unremembered so the provider retry reprocesses the event instead
    of being misclassified as a duplicate.
    """
    if not key or key in _SEEN_WEBHOOK_KEYS:
        return
    _SEEN_WEBHOOK_KEYS.append(key)
    if len(_SEEN_WEBHOOK_KEYS) > 1000:
        del _SEEN_WEBHOOK_KEYS[:500]


def scenario_payload(scenario: Scenario):
    perturbations = PERTURBATIONS
    futures = generate_futures(scenario)
    ranked = rank_robust_candidates(scenario, futures, perturbations)

    q = QUBO(
        ("route_a", "route_c"),
        {"route_a": 4.0, "route_c": 2.5},
        {("route_a", "route_c"): -1.5},
    )

    multi_ranked = optimize_policy_space(
        scenario, POLICY_VARIABLES, perturbations
    )
    multi_exact = exact_multivariable_robust_minimize(
        scenario, POLICY_VARIABLES, perturbations
    )
    multi_projection = build_robust_qubo_projection(
        scenario, POLICY_VARIABLES, perturbations
    )
    multi_qaoa = QuantumOptimizer().solve(
        multi_projection, objective="cvar", alpha=0.25
    )

    projection_gaps = [
        abs(
            multi_projection.energy(policy.assignment)
            - robust_policy_cost(scenario, policy.assignment, perturbations)
        )
        for policy in multi_ranked
    ]

    robust_qubo = build_robust_qubo(scenario, q.variables, perturbations)
    classical_robust = exact_minimize(robust_qubo)
    quantum_robust = QuantumOptimizer().solve(robust_qubo)
    cvar_robust = QuantumOptimizer().solve(
        robust_qubo, objective="cvar", alpha=0.25
    )
    bench = benchmark_suite(q)

    robust_bench = {
        "qubo": {
            "variables": robust_qubo.variables,
            "linear": robust_qubo.linear,
            "quadratic": {
                f"{left},{right}": value
                for (left, right), value in (robust_qubo.quadratic or {}).items()
            },
            "offset": robust_qubo.offset,
        },
        "classical": {
            "assignment": classical_robust.assignment,
            "energy": classical_robust.energy,
            "method": classical_robust.method,
        },
        "qaoa": {
            "assignment": quantum_robust.assignment,
            "energy": quantum_robust.energy,
            "method": quantum_robust.method,
        },
        "cvar_qaoa": {
            "assignment": cvar_robust.assignment,
            "energy": cvar_robust.energy,
            "method": cvar_robust.method,
            "alpha": 0.25,
        },
    }

    guardian = verify_under_perturbations(
        dict(scenario.initial_state),
        multi_exact.assignment,
        scenario.transition,
        list(scenario.constraints),
        perturbations,
    )

    return {
        "scenario": {
            "name": scenario.name,
            "initial_state": scenario.initial_state,
            "interventions": {
                key: list(value) for key, value in scenario.interventions.items()
            },
        },
        "futures": [
            {
                "policy": future.policy,
                "state": future.state,
                "score": future.score,
                "valid": future.valid,
            }
            for future in futures
        ],
        "robust": [
            {
                "policy": assessment.candidate.policy,
                "score": assessment.candidate.score,
                "worst_case_score": (
                    assessment.worst_case.adversarial_score
                    if assessment.worst_case
                    else assessment.candidate.score
                ),
                "robustness_gap": assessment.robustness_gap,
                "feasible_under_all": assessment.feasible_under_all,
                "worst_perturbation": (
                    assessment.worst_case.perturbation
                    if assessment.worst_case
                    else {}
                ),
            }
            for assessment in ranked
        ],
        "robust_optimization": robust_bench,
        "multivariable": {
            "variables": list(POLICY_VARIABLES),
            "policy_count": 2 ** len(POLICY_VARIABLES),
            "exact": {
                "assignment": multi_exact.assignment,
                "energy": multi_exact.energy,
                "method": multi_exact.method,
            },
            "qaoa_projection": {
                "assignment": multi_qaoa.assignment,
                "energy": multi_qaoa.energy,
                "method": multi_qaoa.method,
                "approximation": True,
                "objective": "cvar",
                "alpha": 0.25,
            },
            "projection_error": {
                "max_absolute_gap": max(projection_gaps, default=0.0),
                "mean_absolute_gap": (
                    sum(projection_gaps) / len(projection_gaps)
                    if projection_gaps
                    else 0.0
                ),
            },
            "top_policies": [
                {
                    "assignment": policy.assignment,
                    "nominal_cost": policy.nominal_cost,
                    "robust_cost": policy.robust_cost,
                    "feasible": policy.feasible,
                    "worst_perturbation": policy.worst_perturbation,
                }
                for policy in multi_ranked[:6]
            ],
        },
        "benchmark": [
            {
                "method": item.method,
                "energy": item.energy,
                "assignment": item.assignment,
                "runtime_ms": item.runtime_ms,
                "note": item.note,
                "probability": item.probability,
                "expected_energy": item.expected_energy,
            }
            for item in bench
        ],
        "causal_graph": {
            "nodes": emergency_causal_graph().nodes,
            "edges": [
                {
                    "cause": edge.cause,
                    "effect": edge.effect,
                    "strength": edge.strength,
                }
                for edge in emergency_causal_graph().edges
            ],
        },
        "uncertainty": {
            "risk_entropy": normalized_risk_entropy(
                [future.score for future in futures]
            )
        },
        "guardian": {
            "passed": all(result.passed for result in guardian),
            "checks": [
                {"passed": result.passed, "violations": list(result.violations)}
                for result in guardian
            ],
            "scope": "nominal + every declared perturbation",
            "policy": multi_exact.assignment,
        },
        "future_tree": [
            {
                "id": node.id,
                "parent_id": node.parent_id,
                "depth": node.depth,
                "policy": node.policy,
                "score": node.score,
                "valid": node.valid,
                "label": node.label,
            }
            for node in branch_futures(scenario, 2).nodes
        ],
        "reproducibility": {
            "engine_version": ENGINE_VERSION,
            "backend": "statevector-simulator",
            "perturbations": PERTURBATIONS,
            "policy_variables": list(POLICY_VARIABLES),
            "note": "deterministic demo configuration; no hidden sampling",
        },
    }


def _bounded_float(raw: str, key: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid numeric value for {key!r}")
    bounds = SCENARIO_BOUNDS.get(key)
    if bounds is not None:
        lo, hi = bounds
        if not (lo <= value <= hi):
            raise ValueError(f"{key!r}={value} out of range [{lo}, {hi}]")
    return value


def configured_scenario(query):
    scenario = emergency_building()
    for key in ("crowd", "smoke", "corridor_capacity"):
        if key in query:
            scenario.initial_state[key] = _bounded_float(query[key][0], key)
    if query.get("block_b", ["0"])[0].lower() in ("1", "true", "yes"):
        scenario.initial_state["blocked_b_penalty"] = 35.0
    return scenario


def _is_not_found_error(exc: Exception) -> bool:
    """Best-effort classification of Supabase/PostgREST missing-row errors.

    ``.single()`` raises (rather than returning None) when no row matches;
    PostgREST reports that as code PGRST116 / "0 rows". Anything else is a
    genuine dependency failure. Kept narrow to avoid mislabeling outages.
    """
    text = str(exc)
    return "PGRST116" in text or "0 rows" in text


def _is_valid_uuid(value: str) -> bool:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return str(parsed) == str(value).lower()
