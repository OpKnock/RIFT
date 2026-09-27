"""RIFT HTTP boundary (stdlib only): lab demo + persistence + billing.

Security posture (see docs/security.md):
- Optional service-token gate (RIFT_API_TOKEN) on persistence/checkout/entitlement.
- Webhooks authenticate via HMAC X-Signature, never bearer tokens.
- Upstream exception details are logged server-side and never echoed to clients.
- Every response carries request ID + baseline security headers.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__ as ENGINE_VERSION
from .auth import (
    owner_mismatch,
    require_user_id_enforced,
    resolve_caller,
    service_token_configured,
)
from .benchmark import benchmark_suite
from .billing import (
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
from .causal import emergency_causal_graph
from .counterfactual import generate_futures
from .experiments import validate_run_payload, validate_spec_payload
from .futures import branch_futures
from .limits import MAX_PAYLOAD_BYTES, SCENARIO_BOUNDS, describe_limits
from .models import Scenario
from .multivariable import (
    build_robust_qubo_projection,
    exact_multivariable_robust_minimize,
    optimize_policy_space,
)
from .observability import Timer, log_event, new_request_id
from .optimizer import QUBO, QuantumOptimizer, exact_minimize
from . import ratelimit
from .robust import rank_robust_candidates
from .robust_qubo import build_robust_qubo, robust_policy_cost
from .runner import run_spec
from .scenarios import emergency_building
from .settings import billing_status, get_billing_config, supabase_status
from .supabase_store import SupabaseStore
from .uncertainty import normalized_risk_entropy
from .verifier import verify_under_perturbations

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend-dist"
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
        from .realtime import event_bus
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
        from .experiments import validate_spec_payload
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
        from .experiments import ExperimentRun
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
        )
    except Exception:
        return None


def _resolve_experiment(store: "SupabaseStore", experiment_id: str,
                        caller: str | None) -> tuple[dict | None, dict | None, str | None]:
    """Single resolve path for experiment reads (persistence unification).

    Supabase first when configured (ownership-enforced), then the local
    archive mirror. Returns (payload_dict, spec_dict_or_None, error) where
    error is None on success, "forbidden", or "missing". Payload shape
    mirrors the Supabase row so callers treat both stores uniformly.

    Never sends responses (unlike _load_row): callers own status codes,
    so fallback never double-sends. A Supabase transport error surfaces
    as "unavailable" (caller: 502) rather than silently falling back to
    a potentially stale mirror as if authoritative.
    """
    from .experiments import experiment_archive
    if store.configured:
        try:
            fetched = store.get_experiment(experiment_id)
        except Exception as exc:
            # PGRST116/"0 rows" is a clean miss (fall through to the
            # mirror); anything else is a genuine outage.
            if not _is_not_found_error(exc):
                log_event("dependency_failure", dependency="supabase")
                return None, None, "unavailable"
            fetched = None
        row = (fetched.data if fetched else None) or {}
        if row:
            if owner_mismatch(row.get("user_id"), caller):
                return None, None, "forbidden"
            spec = _spec_from_experiment_row(row)
            return (dict(row), spec.to_dict() if spec is not None else None, None)
    exp = experiment_archive.get_experiment(experiment_id)
    if exp:
        return (dict(exp), exp.get("spec") if isinstance(exp.get("spec"), dict) else None, None)
    return None, None, "missing"


def _resolve_run(store: "SupabaseStore", run_id: str,
                 caller: str | None) -> tuple[dict | None, str | None]:
    """Single resolve path for run reads. Returns (payload_dict, error)."""
    from .experiments import experiment_archive
    if store.configured:
        try:
            fetched = store.get_run(run_id)
        except Exception as exc:
            if not _is_not_found_error(exc):
                log_event("dependency_failure", dependency="supabase")
                return None, "unavailable"
            fetched = None
        row = (fetched.data if fetched else None) or {}
        if row:
            if owner_mismatch(row.get("user_id"), caller):
                return None, "forbidden"
            return dict(row), None
    run = experiment_archive.find_run(run_id)
    if run is not None:
        return run.to_dict(), None
    return None, "missing"


def _mirror_experiment_to_archive(spec: "ExperimentSpec", row: dict, owner: str | None) -> None:
    """Mirror a Supabase-persisted experiment into the local archive.

    Makes Supabase rows visible to archive-backed flows (compare/export/
    replay/templates) without a second query path in every handler.
    Best-effort: mirror failures never break the authoritative write.
    """
    try:
        from .experiments import experiment_archive
        record = {
            "id": row.get("id"),
            "name": spec.name,
            "scenario_name": spec.scenario_name,
            "spec": spec.to_dict(),
            "fingerprint": spec.fingerprint(),
            "status": row.get("status", "created"),
            "versions": [],
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
        from .experiments import experiment_archive, ExperimentRun
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


def _client_ip(handler: BaseHTTPRequestHandler) -> str:
    """Best-effort client identity for rate limiting.

    Uses ``X-Forwarded-For`` only when the operator explicitly trusts the
    proxy (``RIFT_TRUST_PROXY=true``); otherwise the direct peer address.
    """
    import os

    if os.getenv("RIFT_TRUST_PROXY", "false").strip().lower() in ("1", "true", "yes"):
        forwarded = handler.headers.get("X-Forwarded-For")
        if forwarded and isinstance(forwarded, str):
            first = forwarded.split(",")[0].strip()
            if first:
                return first[:128]
    try:
        return str(handler.client_address[0])
    except (AttributeError, IndexError, TypeError):
        return "unknown"


def _is_valid_uuid(value: str) -> bool:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return str(parsed) == str(value).lower()


class Handler(BaseHTTPRequestHandler):
    server_version = "RIFT/" + ENGINE_VERSION
    protocol_version = "HTTP/1.1"

    def _send(self, status, data, content_type="application/json", request_id=None, extra_headers=None):
        raw = data if isinstance(data, bytes) else data.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if request_id:
            self.send_header("X-Request-ID", request_id)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, str(value))
        # Explicit allow-list CORS (no wildcard): the dev UI runs
        # cross-origin (Vite :5173 -> API :8080). Production may set
        # RIFT_CORS_ORIGINS or terminate CORS at the edge instead.
        for key, value in _cors_headers(self.headers.get("Origin")).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _finish(self, timer: Timer, request_id: str, method: str, path: str,
                status: int, error_category: str | None = None, **extra):
        try:
            from .health.monitoring import collector as ops_collector

            ops_collector.record_request(path.split("?")[0][:200], status,
                                         round(timer.elapsed_ms(), 2))
        except Exception:  # nosec B110 -- monitoring is best-effort; failure must not break request handling
            pass
        log_event(
            "http_request",
            request_id=request_id,
            method=method,
            path=path.split("?")[0][:200],
            status=status,
            duration_ms=round(timer.elapsed_ms(), 2),
            error_category=error_category,
            **extra,
        )

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return b"", False
        if length > MAX_PAYLOAD_BYTES:
            # Consume-and-discard so the HTTP/1.1 keep-alive connection stays
            # in sync; responding without reading the body aborts the socket
            # on some platforms and breaks subsequent requests.
            remaining = length
            try:
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            except Exception:  # nosec B110 -- discard is best-effort; a broken socket fails the request anyway
                pass
            return b"", True
        try:
            return self.rfile.read(length), False
        except Exception:
            return b"", False

    def _read_json(self):
        raw, overflow = self._read_body()
        if overflow:
            return "overflow", raw
        if not raw:
            return {}, raw
        try:
            return json.loads(raw.decode("utf-8")), raw
        except (ValueError, UnicodeDecodeError):
            return None, raw

    def _identity(self, request_id, body=None, query=None):
        """Resolve caller identity; send 401 on failure.

        Returns ``(user_id_or_None, ok)``. In JWT mode the identity is the
        verified token sub and caller-supplied user_id is ignored; otherwise
        user_id comes from body/query (service-token gate still enforced).
        """
        user_id, error = resolve_caller(self.headers, body, query)
        if error:
            self._send(401, json.dumps({"error": "unauthorized"}), request_id=request_id)
            return None, False
        return user_id, True

    def _load_row(self, fetch, timer, request_id, method, path):
        """Fetch one Supabase row; return (row, None) or (None, (status, body)).

        Missing rows become 404; transport/API failures become 502. Callers
        must still apply ownership checks on the returned row.
        """
        try:
            fetched = fetch()
        except Exception as exc:
            if _is_not_found_error(exc):
                self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                self._finish(timer, request_id, method, path, 404, "not_found")
                return None, (404, None)
            log_event("dependency_failure", request_id=request_id, dependency="supabase")
            self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
            self._finish(timer, request_id, method, path, 502, "persistence_error")
            return None, (502, None)
        row = (fetched.data if fetched else None) or {}
        if not row:
            self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
            self._finish(timer, request_id, method, path, 404, "not_found")
            return None, (404, None)
        return row, None

    def _rate_limit(self, timer: Timer, request_id: str, method: str, path: str) -> bool:
        """Enforce the in-process rate limit. Returns True to continue."""
        if not ratelimit.enabled():
            return True
        allowed, retry_after, scope = ratelimit.check_request(_client_ip(self), path)
        if allowed:
            return True
        log_event(
            "rate_limited", request_id=request_id, method=method,
            scope=scope, retry_after_s=retry_after,
        )
        self._send(
            429,
            json.dumps({"error": "rate_limited", "retry_after_s": retry_after}),
            request_id=request_id,
            extra_headers={"Retry-After": retry_after},
        )
        self._finish(timer, request_id, method, path, 429, "rate_limited")
        return False

    def do_OPTIONS(self):
        request_id = new_request_id()
        timer = Timer()
        # _send attaches the CORS preflight headers from the Origin.
        self._send(204, b"", content_type="text/plain", request_id=request_id)
        self._finish(timer, request_id, "OPTIONS", self.path, 204)

    def do_GET(self):
        request_id = new_request_id()
        timer = Timer()
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if not self._rate_limit(timer, request_id, "GET", path):
            return

        if path == "/api/ops/monitor":
            # Operational telemetry is gated like persistence endpoints: open
            # in dev mode, bearer-gated when JWT/service-token auth is set.
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .health.monitoring import collector as ops_collector

                snapshot = ops_collector.report()
                alerts = ops_collector.check_alerts()
                self._send(200, json.dumps({"monitor": snapshot, "alerts": alerts}),
                           request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "monitor_error", "request_id": request_id}),
                           request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path == "/api/events/stream":
            # Server-Sent Events over plain HTTP (no WebSocket upgrade on
            # the stdlib server). Auth-gated like the monitor endpoint.
            # Query: ?topics=a,b (defaults to the frontend topic set).
            # Each connection occupies one server thread until the client
            # disconnects; sized for local/dev fan-out, not internet scale.
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            from .realtime import FRONTEND_TOPICS, event_bus
            raw_topics = (query.get("topics") or [""])[0]
            topics = [t.strip() for t in raw_topics.split(",") if t.strip()] or FRONTEND_TOPICS
            topics = [t for t in topics if t in FRONTEND_TOPICS]
            if not topics:
                self._send(400, json.dumps({"error": "no valid topics"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 400, "validation")
                return
            queues = [(t, event_bus.subscribe_sync(t)) for t in topics]
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Accel-Buffering", "no")
                if request_id:
                    self.send_header("X-Request-ID", request_id)
                for key, value in _cors_headers(self.headers.get("Origin")).items():
                    self.send_header(key, value)
                self.end_headers()
                hello = json.dumps({"topics": topics, "timestamp": datetime.now(timezone.utc).isoformat()})
                self.wfile.write(f"event: connected\ndata: {hello}\n\n".encode())
                self.wfile.flush()
                last_beat = time.monotonic()
                while True:
                    got_one = False
                    for topic, q in queues:
                        try:
                            event = q.get(timeout=1.0)
                        except Exception:
                            continue
                        got_one = True
                        payload = json.dumps({"topic": topic, "data": event})
                        try:
                            self.wfile.write(f"event: message\ndata: {payload}\n\n".encode())
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            raise _ClientGone()
                    if not got_one and time.monotonic() - last_beat > 15.0:
                        try:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            raise _ClientGone()
                        last_beat = time.monotonic()
            except _ClientGone:
                pass
            except Exception:
                log_event("internal_error", request_id=request_id, route="events-stream")
            finally:
                for topic, q in queues:
                    event_bus.unsubscribe_sync(topic, q)
                self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/metrics":
            # Prometheus exposition for the deployment scrape config.
            # The metric vocabulary is defined once in
            # rift.health.monitoring (EXPORTED_METRICS / render_prometheus);
            # rules and dashboards must reference only those names.
            # Gated like persistence endpoints: open in dev mode,
            # bearer-gated when JWT/service-token auth is set, so the
            # production Ingress cannot expose telemetry anonymously.
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .health.monitoring import collector as ops_collector
                from .health.monitoring import render_prometheus

                body = render_prometheus(ops_collector.report())
                self._send(200, body, content_type="text/plain; version=0.0.4",
                           request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "monitor_error", "request_id": request_id}),
                           request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path == "/api/health":
            from .qpu import backend_status
            qb = backend_status()
            payload = {
                "status": "ok",
                "engine": "rift",
                "version": ENGINE_VERSION,
                "quantum_backend": qb["backend"],
                "quantum_backend_detail": qb,
                "persistence": supabase_status(),
                "billing": billing_status(),
            }
            self._send(200, json.dumps(payload), request_id=request_id)
            self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/api/meta":
            from .qpu import backend_status
            qb = backend_status()
            self._send(200, json.dumps({
                "engine": "rift",
                "engine_version": ENGINE_VERSION,
                "quantum_backend": qb["backend"],
                "quantum_backend_detail": qb,
                "capabilities": ["demo", "twin", "experiments", "runs",
                                 "operations", "explainability", "intelligence",
                                 "billing", "guardian", "events"],
                "optimizers": ["exact", "qaoa-expectation", "qaoa-cvar"],
                "backends": ["statevector-simulator"],
                "limits": describe_limits(),
                "auth": {"service_token_configured": service_token_configured() is not None},
            }), request_id=request_id)
            self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/api/persistence/status":
            self._send(200, json.dumps(supabase_status()), request_id=request_id)
            self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/api/billing/status":
            self._send(200, json.dumps(billing_status()), request_id=request_id)
            self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/api/billing/entitlement":
            caller, ok = self._identity(request_id, None, query)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            store = SupabaseStore()
            if not store.configured:
                self._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 503, "persistence_not_configured")
                return
            if not caller:
                self._send(400, json.dumps({"error": "user_id is required"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 400, "validation")
                return
            try:
                result = store.latest_subscription_for_user(caller)
                rows = result.data or []
                status = rows[0].get("status") if rows else "none"
                entitled = is_entitled(status) if rows else False
                self._send(200, json.dumps({"entitled": entitled, "status": status}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
                self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 502, "persistence_error")
            return
        if path == "/api/auth/session-info":
            # Which principal (if any) the current request authenticates as,
            # and by which mechanism. Never echoes secrets.
            caller, ok = self._identity(request_id, None, query)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            from .auth_jwt import jwt_mode_enabled
            from .sessions import parse_session_cookie, sessions
            mechanism = "caller-asserted (open dev)"
            if jwt_mode_enabled():
                mechanism = "verified-jwt"
            elif self.headers.get("Authorization"):
                mechanism = "bearer-token"
            elif sessions.has(parse_session_cookie(self.headers.get("Cookie"))):
                mechanism = "session-cookie"
            self._send(200, json.dumps({"user_id": caller, "mechanism": mechanism}), request_id=request_id)
            self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/api/demo":
            try:
                self._send(200, json.dumps(scenario_payload(configured_scenario(query))), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except (ValueError, KeyError, TypeError) as exc:
                log_event("validation_failure", request_id=request_id, detail=str(exc)[:200])
                self._send(422, json.dumps({"error": "invalid scenario", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 422, "validation")
            except Exception:
                log_event("internal_error", request_id=request_id, route="demo")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path == "/api/twin/demo":
            try:
                from .health.demo_data import demo_stream
                from .health.ehr import demo_ehr, normalize_ehr
                from .health.twin import DigitalTwin

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
                self._send(200, json.dumps(payload), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except (ValueError, KeyError, TypeError) as exc:
                log_event("validation_failure", request_id=request_id, detail=str(exc)[:200])
                self._send(422, json.dumps({"error": "invalid twin request", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 422, "validation")
            except Exception:
                log_event("internal_error", request_id=request_id, route="twin-demo")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path == "/api/twin/prospective":
            _, ok = self._identity(request_id, None, query)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .health import prospective as _pros
                self._send(200, json.dumps(_pros.manager.stats()), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "prospective_error", "request_id": request_id}),
                           request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path == "/api/twin/reviews":
            _, ok = self._identity(request_id, None, query)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .health import reviews as _rev
                self._send(200, json.dumps({
                    "stats": _rev.ledger.stats(),
                    "reviews": _rev.ledger.list(),
                }), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "reviews_error", "request_id": request_id}),
                           request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path == "/api/operations/incidents":
            # Tenant scoping: ?owner=<id> filters to one owner, ?mine=true
            # filters to the authenticated caller. Without either, listing
            # is workspace-visible (single-tenant assumption documented in
            # docs/security.md) so unacknowledged (owner-less) incidents
            # stay triageable.
            caller, ok = self._identity(request_id, None, query)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .operations import incident_store
                from .operations.incidents import IncidentStatus, IncidentSeverity, IncidentType

                status = (query.get("status") or [None])[0]
                severity = (query.get("severity") or [None])[0]
                type_ = (query.get("type") or [None])[0]
                owner = (query.get("owner") or [None])[0]
                if (query.get("mine") or [""])[0].lower() in ("1", "true", "yes"):
                    owner = caller

                incidents = incident_store.list(
                    status=IncidentStatus(status) if status else None,
                    severity=IncidentSeverity(severity) if severity else None,
                    type=IncidentType(type_) if type_ else None,
                    owner=owner,
                    limit=100,
                )
                self._send(200, json.dumps([i.to_dict() for i in incidents]), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "incidents_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path.startswith("/api/operations/incidents/") and not path.endswith("/action"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                incident_id = parts[3]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .operations import incident_store
                    incident = incident_store.get(incident_id)
                    if incident:
                        self._send(200, json.dumps(incident.to_dict()), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 200)
                    else:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                except Exception:
                    self._send(500, json.dumps({"error": "incidents_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path == "/api/operations/decisions":
            # Same tenant-scoping contract as the incident listing: ?owner=
            # filters (mapped to proposed_by here), ?mine=true scopes to
            # the caller; unfiltered listing stays workspace-visible.
            caller, ok = self._identity(request_id, None, query)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .operations import decision_store
                from .operations.decisions import DecisionStatus

                status = (query.get("status") or [None])[0]
                scenario_id = (query.get("scenario_id") or [None])[0]
                proposed_by = (query.get("owner") or [None])[0]
                if (query.get("mine") or [""])[0].lower() in ("1", "true", "yes"):
                    proposed_by = caller

                decisions = decision_store.list(
                    status=DecisionStatus(status) if status else None,
                    scenario_id=scenario_id,
                    proposed_by=proposed_by,
                    limit=100,
                )
                self._send(200, json.dumps([d.to_dict() for d in decisions]), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "decisions_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path.startswith("/api/operations/decisions/") and not path.endswith("/action"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                decision_id = parts[3]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .operations import decision_store
                    decision = decision_store.get(decision_id)
                    if decision:
                        self._send(200, json.dumps(decision.to_dict()), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 200)
                    else:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                except Exception:
                    self._send(500, json.dumps({"error": "decisions_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path == "/api/explainability/audit":
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .explainability import audit_log
                self._send(200, json.dumps({"records": [r.to_dict() for r in audit_log.query(limit=200)]}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "audit_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path == "/api/explainability/evidence":
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .explainability import evidence_store
                self._send(200, json.dumps({"packages": [p.to_dict() for p in evidence_store._packages.values()]}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "evidence_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path == "/api/intelligence/status":
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .advanced_intelligence import llm_provider
                provider = type(llm_provider).__name__
                self._send(200, json.dumps({
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
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "intelligence_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path == "/api/twin/evidence":
            try:
                from .health.demo_data import demo_series
                from .health.ehr import demo_ehr, normalize_ehr
                from .health.evaluate import (
                    EXTERNAL_SERIES_CONFIG,
                    OUTCOME_RULE,
                    backtest,
                    calibration_report,
                    external_validation,
                    reliability,
                    stress_sweep,
                )
                from .health.model_registry import deployment_gate, get_model, verify_weights
                from .health.subgroups import subgroup_metrics
                from .health.twin import DigitalTwin

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
                self._send(200, json.dumps(payload), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                log_event("internal_error", request_id=request_id, route="twin-evidence")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return
        if path.startswith("/api/experiments/") and path.endswith("/runs"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                if not _is_valid_uuid(experiment_id):
                    self._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, None, query)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                store = SupabaseStore()
                if not store.configured:
                    self._send(503, json.dumps({
                        "error": "persistence_not_configured",
                        "detail": "Set RIFT_SUPABASE_URL and RIFT_SUPABASE_KEY on the server.",
                    }), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 503, "persistence_not_configured")
                    return
                experiment, failed = self._load_row(
                    lambda: store.get_experiment(experiment_id),
                    timer, request_id, "GET", path,
                )
                if failed:
                    return
                if owner_mismatch(experiment.get("user_id"), caller):
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 403, "auth")
                    return
                try:
                    result = store.list_runs(experiment_id)
                    self._send(200, json.dumps(result.data), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 200)
                except Exception:
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 502, "persistence_error")
                return
        # --- Phase 10: Experiment Platform ---
        if path == "/api/experiments/templates":
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .experiments import experiment_archive
                templates = [t.to_dict() for t in experiment_archive.list_templates(public_only=False)]
                self._send(200, json.dumps({"templates": templates}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "templates_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path.startswith("/api/experiments/templates/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                template_id = parts[3]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    template = experiment_archive.get_template(template_id)
                    if template:
                        self._send(200, json.dumps(template.to_dict()), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 200)
                    else:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                except Exception:
                    self._send(500, json.dumps({"error": "templates_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path.startswith("/api/experiments/") and path.endswith("/versions"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    exp = experiment_archive.get_experiment(experiment_id)
                    if not exp:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                        return
                    # Return version history from experiment record
                    # (standalone version records only; the experiment
                    # itself is never a member of its own version list).
                    versions = [v for v in exp.get("versions", []) if isinstance(v, dict)]
                    self._send(200, json.dumps({"experiment_id": experiment_id, "versions": versions}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 200)
                except Exception:
                    self._send(500, json.dumps({"error": "versions_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path.startswith("/api/experiments/") and path.endswith("/runs"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    runs = [r.to_dict() for r in experiment_archive.get_runs(experiment_id)]
                    self._send(200, json.dumps({"experiment_id": experiment_id, "runs": runs}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 200)
                except Exception:
                    self._send(500, json.dumps({"error": "runs_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path.startswith("/api/experiments/") and "/runs/" in path:
            parts = path.strip("/").split("/")
            if len(parts) == 5:
                experiment_id = parts[2]
                run_id = parts[4]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    runs = experiment_archive.get_runs(experiment_id)
                    run = next((r for r in runs if r.id == run_id), None)
                    if run:
                        self._send(200, json.dumps(run.to_dict()), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 200)
                    else:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                except Exception:
                    self._send(500, json.dumps({"error": "runs_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path.startswith("/api/experiments/") and path.endswith("/snapshots"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    exp = experiment_archive.get_experiment(experiment_id)
                    if exp and exp.get("snapshot"):
                        self._send(200, json.dumps(exp["snapshot"]), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 200)
                    else:
                        self._send(404, json.dumps({"error": "no_snapshot"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                except Exception:
                    self._send(500, json.dumps({"error": "snapshots_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path == "/api/experiments/benchmarks":
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .experiments import experiment_archive
                benchmarks = [b.to_dict() for b in experiment_archive._benchmarks.values()]
                self._send(200, json.dumps({"benchmarks": benchmarks}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "benchmarks_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path.startswith("/api/experiments/") and path.endswith("/evidence"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                _, ok = self._identity(request_id)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    bundles = [b.to_dict() for b in experiment_archive.evidence_for_experiment(experiment_id)]
                    self._send(200, json.dumps({"experiment_id": experiment_id, "bundles": bundles}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 200)
                except Exception:
                    self._send(500, json.dumps({"error": "evidence_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path.startswith("/api/experiments/") and path.endswith("/export"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                caller, ok = self._identity(request_id, None, query)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    package = experiment_archive.export_experiment(experiment_id)
                    if package is None:
                        # Fall back to Supabase-backed experiments (with
                        # ownership enforcement) when the local archive
                        # has no record (e.g. after a restart).
                        store = SupabaseStore()
                        if store.configured:
                            exp_row, failed = self._load_row(
                                lambda: store.get_experiment(experiment_id),
                                timer, request_id, "GET", path,
                            )
                            if not failed and exp_row:
                                if owner_mismatch(exp_row.get("user_id"), caller):
                                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                                    self._finish(timer, request_id, "GET", path, 403, "auth")
                                    return
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
                        self._send(200, json.dumps(package), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 200)
                    else:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                except Exception:
                    self._send(500, json.dumps({"error": "export_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path.startswith("/api/experiments/") and path.endswith("/replay"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                caller, ok = self._identity(request_id, None, query)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive, validate_spec_payload
                    from .runner import run_spec
                    spec_data = None
                    exp = experiment_archive.get_experiment(experiment_id)
                    if exp:
                        spec_data = exp.get("spec")
                    if spec_data is None:
                        # Fall back to Supabase-backed experiments (owned).
                        store = SupabaseStore()
                        if store.configured:
                            exp_row, failed = self._load_row(
                                lambda: store.get_experiment(experiment_id),
                                timer, request_id, "GET", path,
                            )
                            if not failed and exp_row:
                                if owner_mismatch(exp_row.get("user_id"), caller):
                                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                                    self._finish(timer, request_id, "GET", path, 403, "auth")
                                    return
                                spec = _spec_from_experiment_row(exp_row)
                                if spec is not None:
                                    spec_data = spec.to_dict()
                    if not spec_data:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 404, "not_found")
                        return
                    try:
                        spec = validate_spec_payload(spec_data if isinstance(spec_data, dict) else {})
                    except ValueError as exc:
                        self._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 400, "validation")
                        return
                    # Deterministic server-side replay: re-execute the
                    # stored spec through the canonical runner.
                    try:
                        result = run_spec(spec)
                    except Exception as exc:
                        self._send(502, json.dumps({"error": "replay_failed", "detail": str(exc)[:300]}), request_id=request_id)
                        self._finish(timer, request_id, "GET", path, 502, "replay_failed")
                        return
                    self._send(200, json.dumps({
                        "experiment_id": experiment_id,
                        "spec": spec.to_dict(),
                        "fingerprint": spec.fingerprint(),
                        "result": result,
                    }), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 200)
                except Exception:
                    self._send(500, json.dumps({"error": "replay_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 500, "internal")
                return

        if path == "/api/experiments/scheduler/jobs":
            _, ok = self._identity(request_id)
            if not ok:
                self._finish(timer, request_id, "GET", path, 401, "auth")
                return
            try:
                from .experiments import local_scheduler
                jobs = []
                for job in local_scheduler.list_jobs():
                    view = dict(job)
                    spec = view.get("spec")
                    if hasattr(spec, "to_dict"):
                        view["spec"] = spec.to_dict()
                    jobs.append(view)
                self._send(200, json.dumps({"jobs": jobs, "note": "local in-process scheduler; jobs do not survive restarts"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
            except Exception:
                self._send(500, json.dumps({"error": "scheduler_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 500, "internal")
            return

        if path.startswith("/api/experiments/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                experiment_id = parts[2]
                if not _is_valid_uuid(experiment_id):
                    self._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, None, query)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                store = SupabaseStore()
                payload, _, err = _resolve_experiment(store, experiment_id, caller)
                if err == "forbidden":
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 403, "auth")
                    return
                if err == "unavailable":
                    self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 502, "persistence_error")
                    return
                if err == "missing" or payload is None:
                    self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 404, "not_found")
                    return
                self._send(200, json.dumps(payload), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
                return
        if path.startswith("/api/runs/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                run_id = parts[2]
                if not _is_valid_uuid(run_id):
                    self._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, None, query)
                if not ok:
                    self._finish(timer, request_id, "GET", path, 401, "auth")
                    return
                store = SupabaseStore()
                payload, err = _resolve_run(store, run_id, caller)
                if err == "forbidden":
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 403, "auth")
                    return
                if err == "unavailable":
                    self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 502, "persistence_error")
                    return
                if err == "missing" or payload is None:
                    self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 404, "not_found")
                    return
                self._send(200, json.dumps(payload), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
                return

        if path == "/app" or path.startswith("/app/"):
            # Canonical React product UI (production image builds it into
            # frontend-dist/; local dev serves it from Vite on :5173).
            # SPA fallback: unknown sub-paths serve index.html so
            # BrowserRouter deep links don't 404 on refresh/direct nav.
            dist = FRONTEND_DIST.resolve()
            rel = path[len("/app"):].lstrip("/") or "index.html"
            target = (dist / rel).resolve()
            if dist not in target.parents and target != dist:
                self._send(404, json.dumps({"error": "not found"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 404, "validation")
                return
            if not target.is_file():
                target = dist / "index.html"
            if not target.is_file():
                self._send(404, json.dumps({"error": "frontend not built"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 404, "not_found")
                return
            ctype = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".json": "application/json",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".ico": "image/x-icon",
                ".webmanifest": "application/manifest+json",
            }.get(target.suffix, "application/octet-stream")
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store" if target.suffix == ".html" else "public, max-age=31536000, immutable")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            if target.suffix == ".html":
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
            if request_id:
                self.send_header("X-Request-ID", request_id)
            for key, value in _cors_headers(self.headers.get("Origin")).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass
            self._finish(timer, request_id, "GET", path, 200)
            return
        self._send(404, json.dumps({"error": "not found"}), request_id=request_id)
        self._finish(timer, request_id, "GET", path, 404, "not_found")

    # -- POST -----------------------------------------------------------
    def do_POST(self):
        request_id = new_request_id()
        timer = Timer()
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._rate_limit(timer, request_id, "POST", path):
            return

        if path == "/api/experiments":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            owner, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                spec = validate_spec_payload(body if isinstance(body, dict) else {})
            except ValueError as exc:
                self._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            if require_user_id_enforced() and not owner:
                self._send(400, json.dumps({"error": "missing_user_id"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            store = SupabaseStore()
            if not store.configured:
                self._send(503, json.dumps({
                    "error": "persistence_not_configured",
                    "detail": "Set RIFT_SUPABASE_URL and RIFT_SUPABASE_KEY on the server.",
                }), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 503, "persistence_not_configured")
                return
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
                self._send(201, json.dumps(result.data), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201, extra_experiment="created")
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
                self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 502, "persistence_error")
            return

        if path == "/api/twin/reviews":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if not isinstance(body, dict):
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            owner, ok = self._identity(request_id, body, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .health import reviews as _rev
                from .health.monitoring import collector as _ops
                # Reviewer identity comes from the authenticated principal.
                # A caller-supplied reviewer_id that disagrees with it is
                # rejected (fail-closed identity); in open dev mode with no
                # authenticated principal the asserted id is accepted but
                # explicitly marked unverified in the audit entry.
                claimed = str(body.get("reviewer_id", "") or "").strip()
                from .auth_jwt import jwt_mode_enabled as _jwt_mode
                auth_on = service_token_configured() is not None or _jwt_mode()
                if owner:
                    if claimed and claimed != owner:
                        self._send(400, json.dumps({"error": "identity_mismatch", "detail": "reviewer_id must match the authenticated principal"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 400, "validation")
                        return
                    reviewer_id, verified = owner, True
                elif auth_on:
                    # Auth is configured but no principal resolved: a review
                    # without an attributable reviewer is not auditable.
                    self._send(400, json.dumps({"error": "missing_user_id", "detail": "submit user_id (service-token mode) or a Bearer token (JWT mode) so the review is attributable"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
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
                self._send(201, json.dumps(entry), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except ValueError as exc:
                self._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}),
                           request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
            except Exception:
                log_event("internal_error", request_id=request_id, route="twin-reviews")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}),
                           request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if (path.startswith("/api/experiments/") and (path.endswith("/runs") or path.endswith("/run"))):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                if not _is_valid_uuid(experiment_id):
                    self._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                body, raw = self._read_json()
                if body == "overflow":
                    self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 413, "validation")
                    return
                if body is None:
                    self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
                if not ok:
                    self._finish(timer, request_id, "POST", path, 401, "auth")
                    return
                try:
                    run = validate_run_payload(body if isinstance(body, dict) else {})
                except ValueError as exc:
                    self._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                store = SupabaseStore()
                if not store.configured:
                    self._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 503, "persistence_not_configured")
                    return
                try:
                    experiment, failed = self._load_row(
                        lambda: store.get_experiment(experiment_id),
                        timer, request_id, "POST", path,
                    )
                    if failed:
                        return
                    if require_user_id_enforced() and not caller:
                        self._send(400, json.dumps({"error": "missing_user_id"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 400, "validation")
                        return
                    if owner_mismatch(experiment.get("user_id"), caller):
                        self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 403, "auth")
                        return
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
                    self._send(201, json.dumps(result.data), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 201)
                except Exception:
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 502, "persistence_error")
                return

        if path.startswith("/api/experiments/") and path.endswith("/execute"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                if not _is_valid_uuid(experiment_id):
                    self._send(400, json.dumps({"error": "invalid_id"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                body, raw = self._read_json()
                if body == "overflow":
                    self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 413, "validation")
                    return
                if body is None:
                    body = {}
                caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
                if not ok:
                    self._finish(timer, request_id, "POST", path, 401, "auth")
                    return
                store = SupabaseStore()
                if not store.configured:
                    self._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 503, "persistence_not_configured")
                    return
                row, failed = self._load_row(
                    lambda: store.get_experiment(experiment_id),
                    timer, request_id, "POST", path,
                )
                if failed:
                    return
                if require_user_id_enforced() and not caller:
                    self._send(400, json.dumps({"error": "missing_user_id"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                if owner_mismatch(row.get("user_id"), caller):
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 403, "auth")
                    return
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
                    self._send(422, json.dumps({"error": "invalid experiment", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 422, "validation")
                    return
                try:
                    record = run_spec(spec)
                except ValueError as exc:
                    try:
                        store.update_experiment(experiment_id, {"status": "failed", "error": {"message": str(exc)[:300]}})
                    except Exception:
                        log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    self._send(422, json.dumps({"error": "invalid experiment", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 422, "validation")
                    return
                except Exception:
                    try:
                        store.update_experiment(experiment_id, {"status": "failed", "error": {"message": "execution failed"}})
                    except Exception:
                        log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    log_event("internal_error", request_id=request_id, route="execute")
                    self._send(500, json.dumps({"error": "execution_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 500, "internal")
                    return
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
                    self._send(201, json.dumps(created.data), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 201)
                except Exception:
                    log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 502, "persistence_error")
                return

        if path == "/api/billing/checkout":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            provider = LemonSqueezyProvider()
            if not provider.configured:
                self._send(503, json.dumps({
                    "error": "billing_not_configured",
                    "provider": "lemon_squeezy",
                    "detail": "Set RIFT_LEMON_SQUEEZY_API_KEY and RIFT_LEMON_SQUEEZY_STORE_ID on the server.",
                }), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 503, "billing_not_configured")
                return
            variant_id = (body.get("variant_id") if isinstance(body, dict) else None) or (
                provider.config.default_variant_id if provider.config else None)
            if isinstance(variant_id, int):
                variant_id = str(variant_id)
            if not isinstance(variant_id, str) or not variant_id.strip():
                self._send(400, json.dumps({"error": "variant_id is required"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            variant_id = variant_id.strip()
            email = body.get("email") if isinstance(body, dict) else None
            if email is not None and (not isinstance(email, str) or len(email) > 320 or "@" not in email):
                self._send(400, json.dumps({"error": "invalid email"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            try:
                checkout = provider.create_checkout(CheckoutRequest(
                    variant_id=str(variant_id),
                    email=email,
                    user_id=(body.get("user_id") if isinstance(body, dict) else None),
                    metadata=(body.get("metadata") if isinstance(body, dict) else None),
                ))
                self._send(201, json.dumps(checkout), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except BillingNotConfigured:
                self._send(503, json.dumps({"error": "billing_not_configured"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 503, "billing_not_configured")
            except ValueError as exc:
                self._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
            except Exception:
                log_event("dependency_failure", request_id=request_id, dependency="lemon_squeezy")
                self._send(502, json.dumps({"error": "billing_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 502, "billing_error")
            return

        if path == "/api/twin/prospective":
            # POST mirrors GET query-param handling inside POST body.
            # State-mutating (lock/reconcile): gated like the GET.
            parsed_q2 = {}
            body2, _ = self._read_json()
            if body2 == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body2 is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body2 if isinstance(body2, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .health import prospective as _pros2
                action = (body2 or {}).get("action") or "lock"
                if action == "lock":
                    from .health.demo_data import demo_series
                    from .health.ehr import demo_ehr, normalize_ehr
                    from .health.twin import DigitalTwin
                    ehr, _ = normalize_ehr(demo_ehr())
                    snap = DigitalTwin(ehr, demo_series()).update(10)
                    rec = _pros2.manager.lock_prediction(
                        patient_id=snap["patient_id"], day=snap["day_index"],
                        predicted_risk=snap["risk"]["risk"],
                        predicted_event=snap["risk"]["event_predicted"],
                        input_hash=snap["provenance"]["input_hash"])
                    self._send(200, json.dumps(rec), request_id=request_id)
                elif action == "reconcile":
                    lock_id = (body2 or {}).get("lock_id")
                    realized = (body2 or {}).get("realized_event")
                    if not lock_id or not isinstance(realized, bool):
                        self._send(400, json.dumps({"error": "lock_id and realized_event required"}),
                                   request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 400, "validation")
                        return
                    else:
                        self._send(200, json.dumps(_pros2.manager.reconcile_outcome(lock_id, realized)),
                                   request_id=request_id)
                else:
                    self._send(200, json.dumps(_pros2.manager.stats()), request_id=request_id)
            except Exception:
                self._send(500, json.dumps({"error": "prospective_error", "request_id": request_id}),
                           request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
                return
            self._finish(timer, request_id, "POST", path, 200)
            return
        if path == "/api/operations/incidents":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .operations import incident_store
                from .operations.incidents import IncidentType, IncidentSeverity

                incident = incident_store.create(
                    type=IncidentType(body.get("type", "manual")),
                    severity=IncidentSeverity(body.get("severity", "medium")),
                    title=body.get("title", ""),
                    description=body.get("description", ""),
                    trigger_alert_id=body.get("trigger_alert_id"),
                    tags=body.get("tags", []),
                )
                _publish_event("incidents.lifecycle", {"event": "created", "incident": incident.to_dict()})
                self._send(201, json.dumps(incident.to_dict()), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except ValueError as exc:
                self._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
            except Exception:
                log_event("internal_error", request_id=request_id, route="incidents-create")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path.startswith("/api/operations/incidents/") and path.endswith("/action"):
            parts = path.strip("/").split("/")
            if len(parts) == 5:
                incident_id = parts[3]
                body, raw = self._read_json()
                if body == "overflow":
                    self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 413, "validation")
                    return
                if body is None:
                    self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
                if not ok:
                    self._finish(timer, request_id, "POST", path, 401, "auth")
                    return
                try:
                    from .operations import incident_store
                    from .operations.incidents import IncidentStatus

                    incident = incident_store.get(incident_id)
                    if not incident:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 404, "not_found")
                        return
                    action = body.get("action", "")
                    note = body.get("note", "")
                    actor = caller or "anonymous"
                    if action == "acknowledge":
                        incident.acknowledge(actor, note)
                    elif action == "investigate":
                        incident.investigate(actor, note)
                    elif action == "resolve":
                        incident.resolve(actor, note)
                    elif action == "close":
                        incident.close(actor, note)
                    elif action == "reopen":
                        incident.reopen(actor, note)
                    else:
                        self._send(400, json.dumps({"error": "invalid_action"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 400, "validation")
                        return
                    _publish_event("incidents.lifecycle", {"event": action, "incident": incident.to_dict()})
                    self._send(200, json.dumps(incident.to_dict()), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 200)
                except ValueError as exc:
                    self._send(400, json.dumps({"error": "invalid_action", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                except Exception:
                    log_event("internal_error", request_id=request_id, route="incidents-action")
                    self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 500, "internal")
                return

        if path.startswith("/api/operations/decisions/") and path.endswith("/action"):
            parts = path.strip("/").split("/")
            if len(parts) == 5:
                decision_id = parts[3]
                body, raw = self._read_json()
                if body == "overflow":
                    self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 413, "validation")
                    return
                if body is None:
                    self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
                if not ok:
                    self._finish(timer, request_id, "POST", path, 401, "auth")
                    return
                try:
                    from .operations import decision_store
                    from .operations.decisions import DecisionAction

                    decision = decision_store.get(decision_id)
                    if not decision:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 404, "not_found")
                        return
                    action = body.get("action", "")
                    note = body.get("note", "")
                    actor = caller or "anonymous"
                    if action == "accept":
                        decision.accept(actor, note, body.get("guardian_verdict"))
                    elif action == "reject":
                        decision.reject(actor, note, body.get("guardian_verdict"))
                    elif action == "override":
                        decision.override(actor, note, body.get("guardian_verdict"))
                    elif action == "request_review":
                        decision.request_review(actor, note)
                    elif action == "execute":
                        decision.execute(actor, body.get("result", {}))
                    else:
                        self._send(400, json.dumps({"error": "invalid_action"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 400, "validation")
                        return
                    _publish_event("decisions.lifecycle", {"event": action, "decision": decision.to_dict()})
                    self._send(200, json.dumps(decision.to_dict()), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 200)
                except ValueError as exc:
                    self._send(400, json.dumps({"error": "invalid_action", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                except Exception:
                    log_event("internal_error", request_id=request_id, route="decisions-action")
                    self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 500, "internal")
                return

        if path == "/api/auth/session":
            # Exchange a service token for an HttpOnly session cookie so
            # browsers stop keeping the token in localStorage (XSS blast
            # radius). Service-token mode only; JWT mode keeps using
            # Authorization headers managed client-side.
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if not isinstance(body, dict):
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            from .auth import extract_bearer
            from .sessions import (
                cookie_secure, sessions,
                session_cookie_header, verify_service_token,
            )
            raw_token = body.get("token")
            token = raw_token if isinstance(raw_token, str) else extract_bearer(self.headers)
            if not verify_service_token(token):
                self._send(401, json.dumps({"error": "unauthorized"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            user_id = body.get("user_id")
            user_id = user_id.strip() if isinstance(user_id, str) and user_id.strip() else None
            if user_id is not None and len(user_id) > 128:
                self._send(400, json.dumps({"error": "user_id too long"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            try:
                session_id, expires_at = sessions.create(user_id)
                self._send(200, json.dumps({"user_id": user_id, "expires_at": expires_at}),
                           request_id=request_id,
                           extra_headers={"Set-Cookie": session_cookie_header(session_id, expires_at, cookie_secure())})
                self._finish(timer, request_id, "POST", path, 200)
            except Exception:
                log_event("internal_error", request_id=request_id, route="auth-session")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path == "/api/auth/logout":
            from .sessions import clear_session_cookie_header, cookie_secure, parse_session_cookie, sessions
            sessions.destroy(parse_session_cookie(self.headers.get("Cookie")))
            self._send(200, json.dumps({"logged_out": True}), request_id=request_id,
                       extra_headers={"Set-Cookie": clear_session_cookie_header(cookie_secure())})
            self._finish(timer, request_id, "POST", path, 200)
            return

        if path == "/api/billing/webhook":
            body, raw = self._read_json()
            config = get_billing_config()
            if config is None or not config.webhook_secret:
                self._send(503, json.dumps({
                    "error": "billing_webhook_not_configured",
                    "detail": "Set RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET on the server before receiving webhooks.",
                }), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 503, "billing_not_configured")
                return
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            signature = self.headers.get("X-Signature")
            if not verify_webhook_signature(raw, signature, config.webhook_secret):
                self._send(401, json.dumps({"error": "invalid_signature"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            try:
                event = parse_webhook_event(body)
            except ValueError as exc:
                self._send(400, json.dumps({"error": "invalid_webhook", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            key = billing_idempotency_key(body) or event.get("idempotency_key")
            if _seen_webhook_key(key):
                self._send(200, json.dumps({"received": True, "event": event["event_name"], "duplicate": True}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 200)
                return
            try:
                store = SupabaseStore()
                if store.configured:
                    if key:
                        try:
                            existing = store.find_billing_event(key).data or []
                            if existing:
                                # Resume, don't short-circuit: the event row may
                                # have been recorded while the subscription
                                # side effect below failed (502). Re-apply the
                                # update idempotently before acknowledging.
                                if not _apply_subscription_update(store, event, request_id):
                                    self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                                    self._finish(timer, request_id, "POST", path, 502, "persistence_error")
                                    return
                                _remember_webhook_key(key)
                                self._send(200, json.dumps({"received": True, "event": event["event_name"], "duplicate": True}), request_id=request_id)
                                self._finish(timer, request_id, "POST", path, 200)
                                return
                        except Exception:
                            log_event("dependency_failure", request_id=request_id, dependency="supabase")
                    try:
                        store.record_billing_event({
                            "event_name": event["event_name"],
                            "supported": event["supported"],
                            "provider_event_id": webhook_event_id(body),
                            "idempotency_key": key,
                            "lemon_customer_id": (event.get("data") or {}).get("id") if event["event_name"].startswith("order_") else None,
                            "payload": body,
                        })
                    except Exception as exc:
                        # The billing_events table carries a UNIQUE constraint
                        # on idempotency_key (migration 004): a concurrent
                        # duplicate delivery surfaces here as a constraint
                        # violation. Like the durable-duplicate path above, the
                        # subscription side effect must be resumed (not skipped)
                        # before acknowledging: the conflicting row proves the
                        # event was recorded, not that it was processed.
                        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower() or "23505" in str(exc):
                            if not _apply_subscription_update(store, event, request_id):
                                self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                                self._finish(timer, request_id, "POST", path, 502, "persistence_error")
                                return
                            _remember_webhook_key(key)
                            self._send(200, json.dumps({"received": True, "event": event["event_name"], "duplicate": True}), request_id=request_id)
                            self._finish(timer, request_id, "POST", path, 200)
                            return
                        # Durable processing failed: return 502 so Lemon Squeezy
                        # retries instead of believing the event was recorded.
                        log_event("dependency_failure", request_id=request_id, dependency="supabase")
                        self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 502, "persistence_error")
                        return
                    if not _apply_subscription_update(store, event, request_id):
                        self._send(502, json.dumps({"error": "persistence_error", "request_id": request_id}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 502, "persistence_error")
                        return
            except Exception:
                # Unconfigured store: no durability possible; accept as
                # best-effort dev-mode receipt (documented). Any configured-
                # store failure above already returned 502.
                log_event("dependency_failure", request_id=request_id, dependency="supabase")
            _remember_webhook_key(key)
            self._send(200, json.dumps({"received": True, "event": event["event_name"]}), request_id=request_id)
            self._finish(timer, request_id, "POST", path, 200)
            return

        # POST endpoints for Phase 10
        if path == "/api/experiments/templates":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .experiments import experiment_archive, ExperimentTemplate
                try:
                    spec = validate_spec_payload(body.get("spec") or {})
                except ValueError as exc:
                    self._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                name = str(body.get("name", "") or "").strip()
                if not name:
                    self._send(400, json.dumps({"error": "name is required"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
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
                self._send(201, json.dumps(template.to_dict()), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except Exception:
                log_event("internal_error", request_id=request_id, route="templates-create")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path.startswith("/api/experiments/") and path.endswith("/versions"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                body, raw = self._read_json()
                if body == "overflow":
                    self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 413, "validation")
                    return
                if body is None:
                    self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
                if not ok:
                    self._finish(timer, request_id, "POST", path, 401, "auth")
                    return
                try:
                    from .experiments import experiment_archive
                    exp = experiment_archive.get_experiment(experiment_id)
                    if not exp:
                        self._send(404, json.dumps({"error": "not_found"}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 404, "not_found")
                        return
                    # Validate the version spec through the canonical validator
                    # (module-global; must not be re-imported locally here or
                    # it shadows the global for every other do_POST path).
                    try:
                        spec = validate_spec_payload(body.get("spec") or {})
                    except ValueError as exc:
                        self._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
                        self._finish(timer, request_id, "POST", path, 400, "validation")
                        return
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
                    self._send(201, json.dumps({"experiment_id": experiment_id, "version": new_version}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 201)
                except Exception:
                    log_event("internal_error", request_id=request_id, route="versions-create")
                    self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 500, "internal")
                return

        if path == "/api/experiments/compare":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            caller, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .experiments import experiment_archive, comparison_engine
                comparison_type = body.get("type", "optimizer")
                baseline_id = body.get("baseline_id")
                candidate_ids = body.get("candidate_ids", [])
                if not baseline_id or not candidate_ids:
                    self._send(400, json.dumps({"error": "baseline_id and candidate_ids required"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                store = SupabaseStore()

                def _resolve(run_id: str):
                    # Supabase first when configured (ownership-enforced),
                    # then the local archive mirror (dual-written on create).
                    if store.configured:
                        try:
                            row, failed = self._load_row(
                                lambda: store.get_run(run_id),
                                timer, request_id, "POST", path,
                            )
                            if not failed and row:
                                if owner_mismatch(row.get("user_id"), caller):
                                    return "forbidden", None
                                exp_row, exp_failed = self._load_row(
                                    lambda: store.get_experiment(row.get("experiment_id", "")),
                                    timer, request_id, "POST", path,
                                )
                                if not exp_failed and exp_row:
                                    if owner_mismatch(exp_row.get("user_id"), caller):
                                        return "forbidden", None
                                    spec = _spec_from_experiment_row(exp_row)
                                    if spec is not None:
                                        run = _run_from_row(row, spec)
                                        if run is not None:
                                            return None, run
                        except Exception:
                            pass
                    run = experiment_archive.find_run(run_id)
                    return (None, run) if run is not None else ("missing", None)

                forbidden = False
                candidate_runs = []
                err, baseline_run = _resolve(str(baseline_id))
                if err == "forbidden":
                    forbidden = True
                else:
                    for cid in candidate_ids:
                        err, run = _resolve(str(cid))
                        if err == "forbidden":
                            forbidden = True
                            break
                        if run is not None:
                            candidate_runs.append(run)
                if forbidden:
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 403, "auth")
                    return
                if not baseline_run:
                    self._send(404, json.dumps({"error": "baseline_not_found"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 404, "not_found")
                    return
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
                    self._send(400, json.dumps({"error": "invalid_comparison_type"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                experiment_archive.store_comparison(result)
                self._send(201, json.dumps(result.to_dict()), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except Exception:
                log_event("internal_error", request_id=request_id, route="experiments-compare")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path == "/api/experiments/import":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .experiments import experiment_archive
                new_name = body.get("name")
                package = body.get("package")
                if not package:
                    self._send(400, json.dumps({"error": "package required"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                new_id = experiment_archive.import_experiment(package, new_name)
                self._send(201, json.dumps({"experiment_id": new_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except Exception:
                log_event("internal_error", request_id=request_id, route="experiments-import")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path == "/api/intelligence/scenario":
            # Natural language -> validated ExperimentSpec. The LLM proposes;
            # validate_spec_payload disposes: invalid specs 400, never execute.
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            description = str((body if isinstance(body, dict) else {}).get("description", "") or "").strip()
            if not description:
                self._send(400, json.dumps({"error": "description is required"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            try:
                from .advanced_intelligence import create_scenario_nl, llm_provider
                result = create_scenario_nl(description)
                result["provider"] = type(llm_provider).__name__
                result["mock"] = type(llm_provider).__name__ == "MockLLMProvider"
                status = 200 if result.get("valid") else 422
                self._send(status, json.dumps(result), request_id=request_id)
                self._finish(timer, request_id, "POST", path, status)
            except Exception:
                log_event("internal_error", request_id=request_id, route="intelligence-scenario")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path == "/api/intelligence/explain":
            # Grounded explanation of a twin snapshot: the snapshot is
            # computed deterministically first, the LLM only narrates it.
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                day = (body if isinstance(body, dict) else {}).get("day", 13)
                try:
                    day = int(day)
                except (TypeError, ValueError):
                    raise ValueError(f"invalid day: {day!r}")
                if not 0 <= day <= 13:
                    raise ValueError(f"day {day} out of range [0, 13]")
                from .health.demo_data import demo_stream
                from .health.ehr import demo_ehr, normalize_ehr
                from .health.twin import DigitalTwin
                from .advanced_intelligence import explain_grounded, llm_provider
                ehr, _ = normalize_ehr(demo_ehr())
                snapshot = DigitalTwin(ehr, demo_stream()).update(day)
                result = explain_grounded(snapshot, snapshot.get("guardian", {}))
                result["provider"] = type(llm_provider).__name__
                result["mock"] = type(llm_provider).__name__ == "MockLLMProvider"
                self._send(200, json.dumps(result), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 200)
            except (ValueError, KeyError, TypeError) as exc:
                self._send(422, json.dumps({"error": "invalid intelligence request", "detail": str(exc)[:300]}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 422, "validation")
            except Exception:
                log_event("internal_error", request_id=request_id, route="intelligence-explain")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        if path == "/api/experiments/scheduler/jobs":
            body, raw = self._read_json()
            if body == "overflow":
                self._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 413, "validation")
                return
            if body is None:
                self._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 400, "validation")
                return
            _, ok = self._identity(request_id, body if isinstance(body, dict) else None, None)
            if not ok:
                self._finish(timer, request_id, "POST", path, 401, "auth")
                return
            try:
                from .experiments import local_scheduler
                experiment_id = str(body.get("experiment_id", "") or "").strip()
                if not experiment_id:
                    self._send(400, json.dumps({"error": "experiment_id is required"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                try:
                    spec = validate_spec_payload(body.get("spec") or {})
                except ValueError as exc:
                    self._send(400, json.dumps({"error": "invalid_spec", "detail": str(exc)[:300]}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                run_at = body.get("run_at")
                repeat = body.get("repeat")
                if repeat not in (None, "hourly", "daily"):
                    self._send(400, json.dumps({"error": "repeat must be hourly, daily, or omitted"}), request_id=request_id)
                    self._finish(timer, request_id, "POST", path, 400, "validation")
                    return
                job_id = local_scheduler.schedule(experiment_id, spec, run_at=run_at, repeat=repeat)
                local_scheduler.start()
                self._send(201, json.dumps({"job_id": job_id, "status": "scheduled", "run_at": run_at, "repeat": repeat}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 201)
            except Exception:
                log_event("internal_error", request_id=request_id, route="scheduler-create")
                self._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
                self._finish(timer, request_id, "POST", path, 500, "internal")
            return

        self._send(404, json.dumps({"error": "not found"}), request_id=request_id)
        self._finish(timer, request_id, "POST", path, 404, "not_found")

    def do_PUT(self):
        request_id = new_request_id()
        self._send(405, json.dumps({"error": "method_not_allowed"}), request_id=request_id)

    def do_DELETE(self):
        request_id = new_request_id()
        self._send(405, json.dumps({"error": "method_not_allowed"}), request_id=request_id)

    def do_PATCH(self):
        request_id = new_request_id()
        self._send(405, json.dumps({"error": "method_not_allowed"}), request_id=request_id)

    def log_message(self, format, *args):
        return


def serve(host="0.0.0.0", port=8080):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    try:
        server.socket.settimeout(30)
    except Exception:  # nosec B110 -- without a timeout the socket just blocks longer; serve proceeds either way
        pass
    server.serve_forever()


def _main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="RIFT API server")
    parser.add_argument("--host", default=os.getenv("RIFT_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("RIFT_PORT", "8080")))
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    _main()
