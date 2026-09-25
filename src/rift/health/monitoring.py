"""In-process operations monitoring skeleton (Phase 18, no live paging).

Collects request/latency/failure counters, prediction-distribution
sketches, Guardian rejection rates, and missingness signals behind a
thread-safe collector. Alert rules evaluate to data (firing/not-firing
with reasons) — delivery (paging, webhooks, tickets) is intentionally
absent: alerting without an operator and an on-call rotation would be
theater. Wire `record_request` into the HTTP layer; read `report()` from
an operations endpoint or test harness.
"""
from __future__ import annotations

import threading
import time

# Alert thresholds: explicit constants, tunable per deployment.
ALERT_P95_LATENCY_MS = 5000.0
ALERT_FAILURE_RATE = 0.10
ALERT_GUARDIAN_REJECT_RATE = 0.50
ALERT_MISSINGNESS_RATE = 0.30
MIN_SAMPLES_FOR_ALERTS = 20
LATENCY_WINDOW = 500  # ring size per route


class MetricsCollector:
    """Thread-safe in-memory operational telemetry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._requests: dict[str, int] = {}
        self._failures: dict[str, int] = {}
        self._latencies: dict[str, list[float]] = {}
        self._guardian = {"allow": 0, "warn": 0, "withhold": 0}
        self._risks: list[float] = []
        self._missingness: list[float] = []

    def record_request(self, route: str, status: int, duration_ms: float) -> None:
        with self._lock:
            self._requests[route] = self._requests.get(route, 0) + 1
            if status >= 500:
                self._failures[route] = self._failures.get(route, 0) + 1
            window = self._latencies.setdefault(route, [])
            window.append(duration_ms)
            if len(window) > LATENCY_WINDOW:
                del window[:len(window) - LATENCY_WINDOW]

    def record_prediction(self, risk: float, guardian_action: str, missingness: float) -> None:
        with self._lock:
            self._risks.append(float(risk))
            if len(self._risks) > LATENCY_WINDOW:
                del self._risks[:len(self._risks) - LATENCY_WINDOW]
            normalized = str(guardian_action or "").lower()
            if normalized in self._guardian:
                self._guardian[normalized] += 1
            self._missingness.append(max(0.0, min(1.0, missingness)))

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float | None:
        """Linear-interpolation percentile (type-7, like numpy default).

        The previous index-truncation version returned wrong results
        (e.g. P50 of [1, 3] gave 3 instead of 2.0).
        """
        if not values:
            return None
        if not 0.0 <= pct <= 100.0:
            raise ValueError(f"percentile {pct} out of range [0, 100]")
        ordered = sorted(values)
        if len(ordered) == 1:
            return float(ordered[0])
        rank = pct / 100.0 * (len(ordered) - 1)
        low = int(rank)
        frac = rank - low
        if frac == 0.0:
            return float(ordered[low])
        return float(ordered[low] * (1.0 - frac) + ordered[low + 1] * frac)

    def report(self) -> dict:
        """Point-in-time operations snapshot (JSON-safe)."""
        with self._lock:
            total = sum(self._requests.values())
            failures = sum(self._failures.values())
            routes = {}
            for route, count in sorted(self._requests.items()):
                routes[route] = {
                    "requests": count,
                    "failures": self._failures.get(route, 0),
                    "p50_ms": self._percentile(self._latencies.get(route, []), 50),
                    "p95_ms": self._percentile(self._latencies.get(route, []), 95),
                }
            guardian_total = sum(self._guardian.values())
            return {
                "uptime_s": time.monotonic() - self._started,
                "requests_total": total,
                "failure_rate": (failures / total) if total else 0.0,
                "routes": routes,
                "guardian": dict(self._guardian),
                "guardian_reject_rate": (self._guardian["withhold"] / guardian_total)
                if guardian_total else 0.0,
                "prediction_count": len(self._risks),
                "risk_mean": (sum(self._risks) / len(self._risks)) if self._risks else None,
                "missingness_mean": (sum(self._missingness) / len(self._missingness))
                if self._missingness else None,
            }

    def check_alerts(self) -> list[dict]:
        """Evaluate alert rules against current counters. Data, not paging."""
        snapshot = self.report()
        alerts: list[dict] = []
        if snapshot["requests_total"] < MIN_SAMPLES_FOR_ALERTS:
            return [{"rule": "insufficient-traffic", "firing": False,
                     "reason": f"only {snapshot['requests_total']} requests "
                               f"(< {MIN_SAMPLES_FOR_ALERTS}): alerts suppressed, not absent"}]
        if snapshot["failure_rate"] >= ALERT_FAILURE_RATE:
            alerts.append({"rule": "failure-rate", "firing": True,
                           "reason": f"failure rate {snapshot['failure_rate']:.2f} >= {ALERT_FAILURE_RATE}"})
        for route, stats in snapshot["routes"].items():
            p95 = stats["p95_ms"]
            if p95 is not None and p95 >= ALERT_P95_LATENCY_MS:
                alerts.append({"rule": "latency-p95", "firing": True,
                               "reason": f"{route} p95 {p95:.0f}ms >= {ALERT_P95_LATENCY_MS:.0f}ms"})
        if snapshot["guardian_reject_rate"] >= ALERT_GUARDIAN_REJECT_RATE:
            alerts.append({"rule": "guardian-reject-rate", "firing": True,
                           "reason": f"withhold rate {snapshot['guardian_reject_rate']:.2f}"})
        missing = snapshot["missingness_mean"]
        if missing is not None and missing >= ALERT_MISSINGNESS_RATE:
            alerts.append({"rule": "missingness", "firing": True,
                           "reason": f"mean missingness {missing:.2f}"})
        if not alerts:
            alerts.append({"rule": "all-clear", "firing": False,
                           "reason": "all rules evaluated, none firing"})
        return alerts

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._failures.clear()
            self._latencies.clear()
            self._guardian = {"allow": 0, "warn": 0, "withhold": 0}
            self._risks.clear()
            self._missingness.clear()
            self._started = time.monotonic()


# Canonical Prometheus metric vocabulary exported by /metrics.
# Prometheus rules and Grafana dashboards MUST only reference names in
# this set (see tests/test_internal_audit_regression.py::test_monitoring_contract).
# Aspirational metrics (twin risk gauges, drift scores, SLO budgets, ...)
# live in monitoring/prometheus/rules/rift_future_alerts.yml.disabled until
# a real exporter produces them.
EXPORTED_METRICS = frozenset({
    "rift_api_requests_total",
    "rift_api_request_failures_total",
    "rift_api_latency_p50_ms",
    "rift_api_latency_p95_ms",
    "rift_guardian_actions_total",
    "rift_failure_rate",
    "rift_guardian_reject_rate",
    "rift_prediction_count",
    "rift_missingness_mean",
    "rift_risk_mean",
})


def _quote_label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def render_prometheus(snapshot: dict) -> str:
    """Render a collector snapshot as Prometheus text exposition (0.0.4)."""
    lines = [
        "# HELP rift_api_requests_total Total HTTP requests by route.",
        "# TYPE rift_api_requests_total counter",
    ]
    routes = snapshot.get("routes") or {}
    for route in sorted(routes):
        stats = routes[route] or {}
        lines.append(f'rift_api_requests_total{{route="{_quote_label(route)}"}} {stats.get("requests", 0)}')
    lines += [
        "# HELP rift_api_request_failures_total Total HTTP 5xx responses by route.",
        "# TYPE rift_api_request_failures_total counter",
    ]
    for route in sorted(routes):
        stats = routes[route] or {}
        lines.append(f'rift_api_request_failures_total{{route="{_quote_label(route)}"}} {stats.get("failures", 0)}')
    lines += [
        "# HELP rift_api_latency_p50_ms Per-route median latency.",
        "# TYPE rift_api_latency_p50_ms gauge",
    ]
    for route in sorted(routes):
        stats = routes[route] or {}
        if stats.get("p50_ms") is not None:
            lines.append(f'rift_api_latency_p50_ms{{route="{_quote_label(route)}"}} {stats["p50_ms"]}')
    lines += [
        "# HELP rift_api_latency_p95_ms Per-route 95th-percentile latency.",
        "# TYPE rift_api_latency_p95_ms gauge",
    ]
    for route in sorted(routes):
        stats = routes[route] or {}
        if stats.get("p95_ms") is not None:
            lines.append(f'rift_api_latency_p95_ms{{route="{_quote_label(route)}"}} {stats["p95_ms"]}')
    lines += [
        "# HELP rift_guardian_actions_total Guardian verdicts by action.",
        "# TYPE rift_guardian_actions_total counter",
    ]
    for action, count in sorted((snapshot.get("guardian") or {}).items()):
        lines.append(f'rift_guardian_actions_total{{action="{_quote_label(action)}"}} {count}')
    lines += [
        "# HELP rift_failure_rate Overall 5xx failure rate.",
        "# TYPE rift_failure_rate gauge",
        f"rift_failure_rate {snapshot.get('failure_rate', 0.0)}",
        "# HELP rift_guardian_reject_rate Guardian WITHHOLD rate.",
        "# TYPE rift_guardian_reject_rate gauge",
        f"rift_guardian_reject_rate {snapshot.get('guardian_reject_rate', 0.0)}",
        "# HELP rift_prediction_count Predictions recorded.",
        "# TYPE rift_prediction_count counter",
        f"rift_prediction_count {snapshot.get('prediction_count', 0)}",
        "# HELP rift_missingness_mean Mean input missingness over recorded predictions.",
        "# TYPE rift_missingness_mean gauge",
        f"rift_missingness_mean {snapshot.get('missingness_mean') if snapshot.get('missingness_mean') is not None else 0.0}",
        "# HELP rift_risk_mean Mean predicted risk over recorded predictions.",
        "# TYPE rift_risk_mean gauge",
        f"rift_risk_mean {snapshot.get('risk_mean') if snapshot.get('risk_mean') is not None else 0.0}",
    ]
    return "\n".join(lines) + "\n"


collector = MetricsCollector()
