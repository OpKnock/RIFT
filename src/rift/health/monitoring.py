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
    def _percentile(sorted_values: list[float], pct: float) -> float | None:
        if not sorted_values:
            return None
        ordered = sorted(sorted_values)
        index = min(len(ordered) - 1, int(pct / 100 * len(ordered)))
        return ordered[index]

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


collector = MetricsCollector()
