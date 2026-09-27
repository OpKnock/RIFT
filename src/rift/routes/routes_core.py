"""Route handlers (split verbatim from api.py; see package README)."""
from __future__ import annotations

from .support import FRONTEND_DIST, _ClientGone, _cors_headers, configured_scenario, scenario_payload
from rift import __version__ as ENGINE_VERSION
from rift.settings import billing_status, get_billing_config, supabase_status
from datetime import datetime, timezone
from rift.limits import describe_limits
import json
from rift.observability import log_event
from rift.auth import service_token_configured
import time


def get_root(h, request_id, timer, path, query):
    """Route if path == "/": unified frontend entry (redirects to /app/)."""
    # The React bundle lives under /app (vite base + router basename);
    # the API root redirects there so ingress `/` and `/app` resolve to
    # one canonical UI instead of a 404 at the production root.
    h.send_response(302)
    h.send_header("Location", "/app/")
    h.send_header("Content-Length", "0")
    h.send_header("Cache-Control", "no-store")
    if request_id:
        h.send_header("X-Request-ID", request_id)
    for key, value in _cors_headers(h.headers.get("Origin")).items():
        h.send_header(key, value)
    h.end_headers()
    h._finish(timer, request_id, "GET", path, 302)
    return True


def get_api_ops_monitor(h, request_id, timer, path, query):
    """Route if path == "/api/ops/monitor": (moved verbatim from api.py do_GET)."""
    # Operational telemetry is gated like persistence endpoints: open
    # in dev mode, bearer-gated when JWT/service-token auth is set.
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.health.monitoring import collector as ops_collector

        snapshot = ops_collector.report()
        alerts = ops_collector.check_alerts()
        h._send(200, json.dumps({"monitor": snapshot, "alerts": alerts}),
                   request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "monitor_error", "request_id": request_id}),
                   request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True
    return False


def get_api_events_stream(h, request_id, timer, path, query):
    """Route if path == "/api/events/stream": (moved verbatim from api.py do_GET)."""
    # Server-Sent Events over plain HTTP (no WebSocket upgrade on
    # the stdlib server). Auth-gated like the monitor endpoint.
    # Query: ?topics=a,b (defaults to the frontend topic set).
    # Each connection occupies one server thread until the client
    # disconnects; sized for local/dev fan-out, not internet scale.
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    from rift.realtime import FRONTEND_TOPICS, event_bus
    raw_topics = (query.get("topics") or [""])[0]
    topics = [t.strip() for t in raw_topics.split(",") if t.strip()] or FRONTEND_TOPICS
    topics = [t for t in topics if t in FRONTEND_TOPICS]
    if not topics:
        h._send(400, json.dumps({"error": "no valid topics"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 400, "validation")
        return True
    queues = [(t, event_bus.subscribe_sync(t)) for t in topics]
    try:
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.send_header("Cache-Control", "no-cache")
        h.send_header("Connection", "keep-alive")
        h.send_header("X-Accel-Buffering", "no")
        if request_id:
            h.send_header("X-Request-ID", request_id)
        for key, value in _cors_headers(h.headers.get("Origin")).items():
            h.send_header(key, value)
        h.end_headers()
        hello = json.dumps({"topics": topics, "timestamp": datetime.now(timezone.utc).isoformat()})
        h.wfile.write(f"event: connected\ndata: {hello}\n\n".encode())
        h.wfile.flush()
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
                    h.wfile.write(f"event: message\ndata: {payload}\n\n".encode())
                    h.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    raise _ClientGone()
            if not got_one and time.monotonic() - last_beat > 15.0:
                try:
                    h.wfile.write(b": heartbeat\n\n")
                    h.wfile.flush()
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
        h._finish(timer, request_id, "GET", path, 200)
    return True
    return False


def get_metrics(h, request_id, timer, path, query):
    """Route if path == "/metrics": (moved verbatim from api.py do_GET)."""
    # Prometheus exposition for the deployment scrape config.
    # The metric vocabulary is defined once in
    # rift.health.monitoring (EXPORTED_METRICS / render_prometheus);
    # rules and dashboards must reference only those names.
    # Gated like persistence endpoints: open in dev mode,
    # bearer-gated when JWT/service-token auth is set, so the
    # production Ingress cannot expose telemetry anonymously.
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, "GET", path, 401, "auth")
        return True
    try:
        from rift.health.monitoring import collector as ops_collector
        from rift.health.monitoring import render_prometheus

        body = render_prometheus(ops_collector.report())
        h._send(200, body, content_type="text/plain; version=0.0.4",
                   request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        h._send(500, json.dumps({"error": "monitor_error", "request_id": request_id}),
                   request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True
    return False


def get_api_health(h, request_id, timer, path, query):
    """Route if path == "/api/health": (moved verbatim from api.py do_GET)."""
    from rift.qpu import backend_status
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
    h._send(200, json.dumps(payload), request_id=request_id)
    h._finish(timer, request_id, "GET", path, 200)
    return True
    return False


def get_api_meta(h, request_id, timer, path, query):
    """Route if path == "/api/meta": (moved verbatim from api.py do_GET)."""
    from rift.qpu import backend_status
    qb = backend_status()
    h._send(200, json.dumps({
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
    h._finish(timer, request_id, "GET", path, 200)
    return True
    return False


def get_api_persistence_status(h, request_id, timer, path, query):
    """Route if path == "/api/persistence/status": (moved verbatim from api.py do_GET)."""
    h._send(200, json.dumps(supabase_status()), request_id=request_id)
    h._finish(timer, request_id, "GET", path, 200)
    return True
    return False


def get_api_demo(h, request_id, timer, path, query):
    """Route if path == "/api/demo": (moved verbatim from api.py do_GET)."""
    try:
        h._send(200, json.dumps(scenario_payload(configured_scenario(query))), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except (ValueError, KeyError, TypeError) as exc:
        log_event("validation_failure", request_id=request_id, detail=str(exc)[:200])
        h._send(422, json.dumps({"error": "invalid scenario", "detail": str(exc)[:300]}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 422, "validation")
    except Exception:
        log_event("internal_error", request_id=request_id, route="demo")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True
    return False


def get_app_app(h, request_id, timer, path, query):
    """Route if path == "/app" or path.startswith("/app/"): (moved verbatim from api.py do_GET)."""
    # Canonical React product UI (production image builds it into
    # frontend-dist/; local dev serves it from Vite on :5173).
    # SPA fallback: unknown sub-paths serve index.html so
    # BrowserRouter deep links don't 404 on refresh/direct nav.
    dist = FRONTEND_DIST.resolve()
    rel = path[len("/app"):].lstrip("/") or "index.html"
    target = (dist / rel).resolve()
    if dist not in target.parents and target != dist:
        h._send(404, json.dumps({"error": "not found"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 404, "validation")
        return True
    if not target.is_file():
        target = dist / "index.html"
    if not target.is_file():
        h._send(404, json.dumps({"error": "frontend not built"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 404, "not_found")
        return True
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
    h.send_response(200)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(raw)))
    h.send_header("Cache-Control", "no-store" if target.suffix == ".html" else "public, max-age=31536000, immutable")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("X-Frame-Options", "DENY")
    h.send_header("Referrer-Policy", "no-referrer")
    if target.suffix == ".html":
        h.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
    if request_id:
        h.send_header("X-Request-ID", request_id)
    for key, value in _cors_headers(h.headers.get("Origin")).items():
        h.send_header(key, value)
    h.end_headers()
    try:
        h.wfile.write(raw)
    except (BrokenPipeError, ConnectionResetError):
        pass
    h._finish(timer, request_id, "GET", path, 200)
    return True
    return False
