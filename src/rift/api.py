import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .benchmark import benchmark_suite
from .billing import (
    BillingNotConfigured,
    CheckoutRequest,
    LemonSqueezyProvider,
    parse_webhook_event,
    verify_webhook_signature,
)
from .causal import emergency_causal_graph
from .counterfactual import generate_futures
from .futures import branch_futures
from .models import Scenario
from .multivariable import (
    build_robust_qubo_projection,
    exact_multivariable_robust_minimize,
    optimize_policy_space,
)
from .optimizer import QUBO, QuantumOptimizer, exact_minimize
from .robust import rank_robust_candidates
from .robust_qubo import build_robust_qubo, robust_policy_cost
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
            "quadratic": robust_qubo.quadratic,
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
    }


def configured_scenario(query):
    scenario = emergency_building()
    for key in ("crowd", "smoke", "corridor_capacity"):
        if key in query:
            try:
                scenario.initial_state[key] = float(query[key][0])
            except (ValueError, TypeError):
                pass
    if query.get("block_b", ["0"])[0].lower() in ("1", "true", "yes"):
        scenario.initial_state["blocked_b_penalty"] = 35.0
    return scenario


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, data, content_type="application/json"):
        raw = data if isinstance(data, bytes) else data.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self, limit_bytes=1_000_000):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > limit_bytes:
            return b""
        return self.rfile.read(length)

    def _read_json(self):
        raw = self._read_body()
        if not raw:
            return {}, b""
        try:
            return json.loads(raw.decode("utf-8")), raw
        except (ValueError, UnicodeDecodeError):
            return None, raw

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/health":
            return self._send(
                200,
                json.dumps(
                    {
                        "status": "ok",
                        "engine": "rift",
                        "version": "0.6.0",
                        "quantum_backend": "statevector-simulator",
                        "persistence": supabase_status(),
                        "billing": billing_status(),
                    }
                ),
            )
        if path == "/api/persistence/status":
            return self._send(200, json.dumps(supabase_status()))
        if path == "/api/billing/status":
            return self._send(200, json.dumps(billing_status()))
        if path == "/api/demo":
            try:
                return self._send(
                    200, json.dumps(scenario_payload(configured_scenario(query)))
                )
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(
                    422, json.dumps({"error": "invalid scenario", "detail": str(exc)})
                )
        if path.startswith("/api/experiments/") and path.endswith("/runs"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                store = SupabaseStore()
                if not store.configured:
                    return self._send(
                        503,
                        json.dumps(
                            {
                                "error": "persistence_not_configured",
                                "detail": "Set RIFT_SUPABASE_URL and "
                                "RIFT_SUPABASE_KEY on the server.",
                            }
                        ),
                    )
                try:
                    result = store.list_runs(experiment_id)
                    return self._send(200, json.dumps(result.data))
                except Exception as exc:  # network/supabase errors only
                    return self._send(
                        502, json.dumps({"error": "persistence_error", "detail": str(exc)})
                    )
        if path.startswith("/api/experiments/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                experiment_id = parts[2]
                store = SupabaseStore()
                if not store.configured:
                    return self._send(
                        503,
                        json.dumps(
                            {
                                "error": "persistence_not_configured",
                                "detail": "Set RIFT_SUPABASE_URL and "
                                "RIFT_SUPABASE_KEY on the server.",
                            }
                        ),
                    )
                try:
                    result = store.get_experiment(experiment_id)
                    return self._send(200, json.dumps(result.data))
                except Exception as exc:
                    return self._send(
                        502, json.dumps({"error": "persistence_error", "detail": str(exc)})
                    )
        if path.startswith("/api/runs/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                run_id = parts[2]
                store = SupabaseStore()
                if not store.configured:
                    return self._send(
                        503,
                        json.dumps({"error": "persistence_not_configured"}),
                    )
                try:
                    result = store.get_run(run_id)
                    return self._send(200, json.dumps(result.data))
                except Exception as exc:
                    return self._send(
                        502, json.dumps({"error": "persistence_error", "detail": str(exc)})
                    )

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
            target = ROOT / filename
            if not target.is_file():
                return self._send(404, json.dumps({"error": "asset not found"}))
            return self._send(200, target.read_bytes(), content_types[ext])
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/experiments":
            body, _ = self._read_json()
            if body is None:
                return self._send(400, json.dumps({"error": "invalid_json"}))
            if not isinstance(body, dict) or not body.get("name") or not body.get("scenario"):
                return self._send(
                    400,
                    json.dumps({"error": "name and scenario are required"}),
                )
            store = SupabaseStore()
            if not store.configured:
                return self._send(
                    503,
                    json.dumps(
                        {
                            "error": "persistence_not_configured",
                            "detail": "Set RIFT_SUPABASE_URL and "
                            "RIFT_SUPABASE_KEY on the server.",
                        }
                    ),
                )
            try:
                result = store.create_experiment(
                    {
                        "name": body["name"],
                        "description": body.get("description", ""),
                        "scenario": body["scenario"],
                        "status": "created",
                    }
                )
                return self._send(201, json.dumps(result.data))
            except Exception as exc:
                return self._send(
                    502, json.dumps({"error": "persistence_error", "detail": str(exc)})
                )

        if path.startswith("/api/experiments/") and path.endswith("/runs"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                experiment_id = parts[2]
                body, _ = self._read_json()
                if body is None:
                    return self._send(400, json.dumps({"error": "invalid_json"}))
                if not isinstance(body, dict) or not body.get("optimizer"):
                    return self._send(
                        400, json.dumps({"error": "optimizer is required"})
                    )
                store = SupabaseStore()
                if not store.configured:
                    return self._send(
                        503, json.dumps({"error": "persistence_not_configured"})
                    )
                try:
                    result = store.create_run(
                        {
                            "experiment_id": experiment_id,
                            "optimizer": body["optimizer"],
                            "result": body.get("result"),
                            "metrics": body.get("metrics") or {},
                            "seed": body.get("seed"),
                        }
                    )
                    return self._send(201, json.dumps(result.data))
                except Exception as exc:
                    return self._send(
                        502, json.dumps({"error": "persistence_error", "detail": str(exc)})
                    )

        if path == "/api/billing/checkout":
            body, _ = self._read_json()
            if body is None:
                return self._send(400, json.dumps({"error": "invalid_json"}))
            provider = LemonSqueezyProvider()
            if not provider.configured:
                return self._send(
                    503,
                    json.dumps(
                        {
                            "error": "billing_not_configured",
                            "provider": "lemon_squeezy",
                            "detail": "Set RIFT_LEMON_SQUEEZY_API_KEY and "
                            "RIFT_LEMON_SQUEEZY_STORE_ID on the server.",
                        }
                    ),
                )
            variant_id = (
                body.get("variant_id")
                if isinstance(body, dict)
                else None
            ) or (provider.config.default_variant_id if provider.config else None)
            if not variant_id:
                return self._send(400, json.dumps({"error": "variant_id is required"}))
            try:
                checkout = provider.create_checkout(
                    CheckoutRequest(
                        variant_id=str(variant_id),
                        email=(body.get("email") if isinstance(body, dict) else None),
                        user_id=(body.get("user_id") if isinstance(body, dict) else None),
                        metadata=(body.get("metadata") if isinstance(body, dict) else None),
                    )
                )
                return self._send(201, json.dumps(checkout))
            except BillingNotConfigured as exc:
                return self._send(
                    503, json.dumps({"error": "billing_not_configured", "detail": str(exc)})
                )
            except ValueError as exc:
                return self._send(400, json.dumps({"error": "invalid_request", "detail": str(exc)}))
            except Exception as exc:
                return self._send(
                    502, json.dumps({"error": "billing_error", "detail": str(exc)})
                )

        if path == "/api/billing/webhook":
            body, raw = self._read_json()
            config = get_billing_config()
            if config is None or not config.webhook_secret:
                # Fail closed: never accept unverified webhooks.
                return self._send(
                    503,
                    json.dumps(
                        {
                            "error": "billing_webhook_not_configured",
                            "detail": "Set RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET "
                            "on the server before receiving webhooks.",
                        }
                    ),
                )
            signature = self.headers.get("X-Signature")
            if not verify_webhook_signature(raw, signature, config.webhook_secret):
                return self._send(401, json.dumps({"error": "invalid_signature"}))
            if body is None:
                return self._send(400, json.dumps({"error": "invalid_json"}))
            try:
                event = parse_webhook_event(body)
            except ValueError as exc:
                return self._send(400, json.dumps({"error": "invalid_webhook", "detail": str(exc)}))
            # Best-effort audit log; webhook acceptance must not depend on Supabase.
            try:
                store = SupabaseStore()
                if store.configured:
                    data = event.get("data") or {}
                    store.record_billing_event(
                        {
                            "event_name": event["event_name"],
                            "supported": event["supported"],
                            "payload": body,
                        }
                    )
            except Exception:
                pass
            return self._send(200, json.dumps({"received": True, "event": event["event_name"]}))

        return self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, format, *args):
        return


def serve(host="127.0.0.1", port=8080):
    ThreadingHTTPServer((host, port), Handler).serve_forever()
