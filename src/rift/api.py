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

from .routes import routes_auth, routes_billing, routes_core, routes_experiments, routes_operations, routes_twin
from .routes.support import FRONTEND_DIST, PERTURBATIONS, POLICY_VARIABLES, _ClientGone, _SEEN_WEBHOOK_KEYS, _apply_subscription_update, _bounded_float, _cors_allowed_origins, _cors_headers, _is_not_found_error, _is_valid_uuid, _mirror_experiment_to_archive, _mirror_run_to_archive, _publish_event, _remember_webhook_key, _resolve_experiment, _resolve_run, _run_from_row, _seen_webhook_key, _spec_from_experiment_row, configured_scenario, scenario_payload


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

        if path == "/":
            if routes_core.get_root(self, request_id, timer, path, query):
                return
        if path == "/api/ops/monitor":
            if routes_core.get_api_ops_monitor(self, request_id, timer, path, query):
                return
        if path == "/api/events/stream":
            if routes_core.get_api_events_stream(self, request_id, timer, path, query):
                return
        if path == "/metrics":
            if routes_core.get_metrics(self, request_id, timer, path, query):
                return
        if path == "/api/health":
            if routes_core.get_api_health(self, request_id, timer, path, query):
                return
        if path == "/api/meta":
            if routes_core.get_api_meta(self, request_id, timer, path, query):
                return
        if path == "/api/persistence/status":
            if routes_core.get_api_persistence_status(self, request_id, timer, path, query):
                return
        if path == "/api/billing/status":
            if routes_billing.get_api_billing_status(self, request_id, timer, path, query):
                return
        if path == "/api/billing/entitlement":
            if routes_billing.get_api_billing_entitlement(self, request_id, timer, path, query):
                return
        if path == "/api/auth/session-info":
            if routes_auth.get_api_auth_session_info(self, request_id, timer, path, query):
                return
        if path == "/api/demo":
            if routes_core.get_api_demo(self, request_id, timer, path, query):
                return
        if path == "/api/twin/demo":
            if routes_twin.get_api_twin_demo(self, request_id, timer, path, query):
                return
        if path == "/api/twin/prospective":
            if routes_twin.get_api_twin_prospective(self, request_id, timer, path, query):
                return
        if path == "/api/twin/reviews":
            if routes_twin.get_api_twin_reviews(self, request_id, timer, path, query):
                return
        if path == "/api/operations/incidents":
            if routes_operations.get_api_operations_incidents(self, request_id, timer, path, query):
                return
        if path.startswith("/api/operations/incidents/") and not path.endswith("/action"):
            if routes_operations.get_api_operations_incidents_action(self, request_id, timer, path, query):
                return
        if path == "/api/operations/decisions":
            if routes_operations.get_api_operations_decisions(self, request_id, timer, path, query):
                return
        if path.startswith("/api/operations/decisions/") and not path.endswith("/action"):
            if routes_operations.get_api_operations_decisions_action(self, request_id, timer, path, query):
                return
        if path == "/api/explainability/audit":
            if routes_twin.get_api_explainability_audit(self, request_id, timer, path, query):
                return
        if path == "/api/explainability/evidence":
            if routes_twin.get_api_explainability_evidence(self, request_id, timer, path, query):
                return
        if path == "/api/intelligence/status":
            if routes_twin.get_api_intelligence_status(self, request_id, timer, path, query):
                return
        if path == "/api/twin/evidence":
            if routes_twin.get_api_twin_evidence(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/runs"):
            if routes_experiments.get_api_experiments_runs(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/templates":
            if routes_experiments.get_api_experiments_templates(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/templates/"):
            if routes_experiments.get_api_experiments_templates_2(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/versions"):
            if routes_experiments.get_api_experiments_versions(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and "/runs/" in path:
            if routes_experiments.get_api_experiments_runs_3(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/snapshots"):
            if routes_experiments.get_api_experiments_snapshots(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/benchmarks":
            if routes_experiments.get_api_experiments_benchmarks(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/evidence"):
            if routes_experiments.get_api_experiments_evidence(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/export"):
            if routes_experiments.get_api_experiments_export(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/replay"):
            if routes_experiments.get_api_experiments_replay(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/scheduler/jobs":
            if routes_experiments.get_api_experiments_scheduler_jobs(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/"):
            if routes_experiments.get_api_experiments(self, request_id, timer, path, query):
                return
        if path.startswith("/api/runs/"):
            if routes_experiments.get_api_runs(self, request_id, timer, path, query):
                return
        if path == "/app" or path.startswith("/app/"):
            if routes_core.get_app_app(self, request_id, timer, path, query):
                return
        self._send(404, json.dumps({"error": "not found"}), request_id=request_id)
        self._finish(timer, request_id, "GET", path, 404, "not_found")
    def do_POST(self):
        request_id = new_request_id()
        timer = Timer()
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if not self._rate_limit(timer, request_id, "POST", path):
            return

        if path == "/api/experiments":
            if routes_experiments.post_api_experiments(self, request_id, timer, path, query):
                return
        if path == "/api/twin/reviews":
            if routes_twin.post_api_twin_reviews(self, request_id, timer, path, query):
                return
        if (path.startswith("/api/experiments/") and (path.endswith("/runs") or path.endswith("/run"))):
            if routes_experiments.post_api_experiments_runs_run(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/execute"):
            if routes_experiments.post_api_experiments_execute(self, request_id, timer, path, query):
                return
        if path == "/api/billing/checkout":
            if routes_billing.post_api_billing_checkout(self, request_id, timer, path, query):
                return
        if path == "/api/twin/prospective":
            if routes_twin.post_api_twin_prospective(self, request_id, timer, path, query):
                return
        if path == "/api/operations/incidents":
            if routes_operations.post_api_operations_incidents(self, request_id, timer, path, query):
                return
        if path.startswith("/api/operations/incidents/") and path.endswith("/action"):
            if routes_operations.post_api_operations_incidents_action(self, request_id, timer, path, query):
                return
        if path.startswith("/api/operations/decisions/") and path.endswith("/action"):
            if routes_operations.post_api_operations_decisions_action(self, request_id, timer, path, query):
                return
        if path == "/api/auth/session":
            if routes_auth.post_api_auth_session(self, request_id, timer, path, query):
                return
        if path == "/api/auth/logout":
            if routes_auth.post_api_auth_logout(self, request_id, timer, path, query):
                return
        if path == "/api/billing/webhook":
            if routes_billing.post_api_billing_webhook(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/templates":
            if routes_experiments.post_api_experiments_templates(self, request_id, timer, path, query):
                return
        if path.startswith("/api/experiments/") and path.endswith("/versions"):
            if routes_experiments.post_api_experiments_versions(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/compare":
            if routes_experiments.post_api_experiments_compare(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/import":
            if routes_experiments.post_api_experiments_import(self, request_id, timer, path, query):
                return
        if path == "/api/intelligence/scenario":
            if routes_twin.post_api_intelligence_scenario(self, request_id, timer, path, query):
                return
        if path == "/api/intelligence/explain":
            if routes_twin.post_api_intelligence_explain(self, request_id, timer, path, query):
                return
        if path == "/api/experiments/scheduler/jobs":
            if routes_experiments.post_api_experiments_scheduler_jobs(self, request_id, timer, path, query):
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
