"""RIFT HTTP boundary (stdlib only): lab demo + persistence + billing.

Security posture (see docs/security.md):
- Optional service-token gate (RIFT_API_TOKEN) on persistence/checkout/entitlement.
- Webhooks authenticate via HMAC X-Signature, never bearer tokens.
- Upstream exception details are logged server-side and never echoed to clients.
- Every response carries request ID + baseline security headers.
"""
import json
import uuid
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

ROOT = Path(__file__).resolve().parents[2] / "web"
PERTURBATIONS = [
    {"smoke": 2.0},
    {"crowd": 80.0},
    {"smoke": 2.0, "crowd": 80.0},
    {"corridor_capacity": -70.0},
]
POLICY_VARIABLES = ("route_a", "route_c", "stairwell_b")

# In-memory webhook dedup for offline mode (bounded; DB is authoritative).
_SEEN_WEBHOOK_KEYS: list[str] = []


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
        # Same-origin lab: no cross-origin auto-allow. Fronted deployments
        # should set explicit ACAO at the edge, not here.
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
            payload = {
                "status": "ok",
                "engine": "rift",
                "version": ENGINE_VERSION,
                "quantum_backend": "statevector-simulator",
                "persistence": supabase_status(),
                "billing": billing_status(),
            }
            self._send(200, json.dumps(payload), request_id=request_id)
            self._finish(timer, request_id, "GET", path, 200)
            return
        if path == "/api/meta":
            self._send(200, json.dumps({
                "engine": "rift",
                "engine_version": ENGINE_VERSION,
                "quantum_backend": "statevector-simulator",
                "capabilities": ["demo", "experiments", "runs", "billing", "guardian"],
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
                )
                external = external_validation(
                    stream=demo_series(
                        seed=EXTERNAL_SERIES_CONFIG["seed"],
                        days=EXTERNAL_SERIES_CONFIG["days"],
                        spells=EXTERNAL_SERIES_CONFIG["spells"],
                    ),
                    ehr=ehr,
                    params=calibration["params"],
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
                        "method": "platt-scaling fit on days 30-44 only",
                        "params": calibration["params"],
                        "test_window": "days 45-59 (untouched)",
                        "raw": {k: calibration["raw"][k] for k in ("brier", "ece")},
                        "calibrated": {k: calibration["calibrated"][k] for k in ("brier", "ece")},
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
                if not store.configured:
                    self._send(503, json.dumps({
                        "error": "persistence_not_configured",
                        "detail": "Set RIFT_SUPABASE_URL and RIFT_SUPABASE_KEY on the server.",
                    }), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 503, "persistence_not_configured")
                    return
                row, failed = self._load_row(
                    lambda: store.get_experiment(experiment_id),
                    timer, request_id, "GET", path,
                )
                if failed:
                    return
                if owner_mismatch(row.get("user_id"), caller):
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 403, "auth")
                    return
                self._send(200, json.dumps(row), request_id=request_id)
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
                if not store.configured:
                    self._send(503, json.dumps({"error": "persistence_not_configured"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 503, "persistence_not_configured")
                    return
                row, failed = self._load_row(
                    lambda: store.get_run(run_id),
                    timer, request_id, "GET", path,
                )
                if failed:
                    return
                if owner_mismatch(row.get("user_id"), caller):
                    self._send(403, json.dumps({"error": "forbidden"}), request_id=request_id)
                    self._finish(timer, request_id, "GET", path, 403, "auth")
                    return
                self._send(200, json.dumps(row), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 200)
                return

        files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.js": "app.js",
            "/styles.css": "styles.css",
        }
        if path in files:
            filename = files[path]
            ext = Path(filename).suffix
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
            }
            target = (ROOT / filename).resolve()
            if ROOT.resolve() not in target.parents and target != ROOT.resolve():
                self._send(404, json.dumps({"error": "not found"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 404, "validation")
                return
            if not target.is_file():
                self._send(404, json.dumps({"error": "asset not found"}), request_id=request_id)
                self._finish(timer, request_id, "GET", path, 404, "not_found")
                return
            ctype = content_types[ext]
            if ext == ".html":
                # Tighten document framing for the served lab page.
                raw = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'")
                self.send_header("X-Request-ID", request_id)
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                self._finish(timer, request_id, "GET", path, 200)
                return
            self._send(200, target.read_bytes(), ctype, request_id=request_id)
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
                entry = _rev.ledger.record(
                    action=body.get("action", ""),
                    evidence_id=body.get("evidence_id", ""),
                    reviewer_id=body.get("reviewer_id", "") or (owner or ""),
                    rationale=body.get("rationale", ""),
                    supersedes=body.get("supersedes"),
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


def serve(host="127.0.0.1", port=8080):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    try:
        server.socket.settimeout(30)
    except Exception:  # nosec B110 -- without a timeout the socket just blocks longer; serve proceeds either way
        pass
    server.serve_forever()
