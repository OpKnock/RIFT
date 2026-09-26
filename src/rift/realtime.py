"""Real-time Event Infrastructure: WebSocket/SSE, source registry, reconciliation (Phase 5 gaps)."""
from __future__ import annotations

import asyncio
import json
import uuid
import hashlib
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .health.sources import WearableSource, ReplaySource, PublicDatasetSource, LiveIngestSource
from .health.monitoring import collector as ops_collector


@dataclass
class SourceProbe:
    """Result of probing a source."""
    key: str
    ok: bool
    latency_ms: int
    checked_at: str
    detail: str | None = None


# --- WebSocket / SSE Server ---

class EventBus:
    """In-process event bus for real-time updates. Supports WebSocket and SSE clients."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, topic: str) -> asyncio.Queue:
        """Subscribe to a topic, returns async queue for messages."""
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers[topic].add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers[topic].discard(queue)

    def publish(self, topic: str, event: dict) -> int:
        """Publish event to all subscribers of topic. Returns count of deliveries."""
        if self._loop is None:
            return 0
        with self._lock:
            queues = list(self._subscribers.get(topic, set()))
        delivered = 0
        for q in queues:
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, event)
                delivered += 1
            except asyncio.QueueFull:
                pass
        return delivered

    def publish_sync(self, topic: str, event: dict) -> int:
        """Synchronous publish for non-async contexts."""
        return self.publish(topic, event)


# --- SSE Endpoint ---

class SSEConnection:
    """Single SSE connection handler."""

    def __init__(self, topics: list[str], event_bus: EventBus) -> None:
        self.topics = topics
        self.event_bus = event_bus
        self.queues: list[asyncio.Queue] = []
        self._closed = False

    async def __aiter__(self):
        for topic in self.topics:
            q = self.event_bus.subscribe(topic)
            self.queues.append(q)
        try:
            while not self._closed:
                # Wait for any queue to have data
                done, pending = await asyncio.wait(
                    [q.get() for q in self.queues],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=30.0,  # heartbeat
                )
                for task in done:
                    event = task.result()
                    yield f"data: {json.dumps(event)}\n\n"
                for task in pending:
                    task.cancel()
        finally:
            for q in self.queues:
                for topic in self.topics:
                    self.event_bus.unsubscribe(topic, q)

    def close(self) -> None:
        self._closed = True


# --- WebSocket Handler ---

class WSConnection:
    """WebSocket connection handler with topic subscriptions."""

    def __init__(self, websocket, event_bus: EventBus) -> None:
        self.ws = websocket
        self.event_bus = event_bus
        self.subscriptions: dict[str, asyncio.Queue] = {}

    async def handle(self) -> None:
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                await self._handle_message(data)
        except Exception:
            pass
        finally:
            await self._cleanup()

    async def _handle_message(self, data: dict) -> None:
        msg_type = data.get("type")
        if msg_type == "subscribe":
            for topic in data.get("topics", []):
                if topic not in self.subscriptions:
                    q = self.event_bus.subscribe(topic)
                    self.subscriptions[topic] = q
                    asyncio.create_task(self._forward(topic, q))
        elif msg_type == "unsubscribe":
            for topic in data.get("topics", []):
                if topic in self.subscriptions:
                    self.event_bus.unsubscribe(topic, self.subscriptions.pop(topic))
        elif msg_type == "ping":
            await self.ws.send(json.dumps({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}))

    async def _forward(self, topic: str, queue: asyncio.Queue) -> None:
        try:
            while True:
                event = await queue.get()
                await self.ws.send(json.dumps({"type": "event", "topic": topic, "data": event}))
        except Exception:
            pass

    async def _cleanup(self) -> None:
        for topic, q in self.subscriptions.items():
            self.event_bus.unsubscribe(topic, q)


# --- Canonical Event Bus ---
event_bus = EventBus()

# Standard topics
TOPICS = {
    "twin.updates": "Digital twin state updates",
    "guardian.verdicts": "Guardian verdicts (WITHHOLD/WARN/ALLOW)",
    "alerts.firing": "Alert rules firing/resolving",
    "incidents.lifecycle": "Incident create/ack/resolve/close",
    "decisions.lifecycle": "Decision propose/accept/reject/override/execute",
    "experiments.runs": "Experiment run created/completed/failed",
    "metrics.snapshot": "Periodic metrics snapshot (5s)",
    "sources.heartbeat": "Source registry probe results",
}


# --- Source Registry Enhancements ---

@dataclass
class SourceTrustScore:
    """Trust score for a data source based on historical reliability."""
    source_key: str
    score: float  # 0.0 - 1.0
    total_probes: int
    successful_probes: int
    avg_latency_ms: float
    last_updated: str
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_key": self.source_key,
            "trust_score": self.score,
            "total_probes": self.total_probes,
            "successful_probes": self.successful_probes,
            "success_rate": self.successful_probes / max(1, self.total_probes),
            "avg_latency_ms": self.avg_latency_ms,
            "last_updated": self.last_updated,
            "flags": self.flags,
        }


class SourceTrustManager:
    """Track and compute trust scores for all registered sources."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scores: dict[str, SourceTrustScore] = {}

    def record_probe(self, probe: SourceProbe) -> SourceTrustScore:
        with self._lock:
            ts = self._scores.get(probe.key)
            if ts is None:
                ts = SourceTrustScore(
                    source_key=probe.key,
                    score=1.0,
                    total_probes=0,
                    successful_probes=0,
                    avg_latency_ms=0.0,
                    last_updated=datetime.now(timezone.utc).isoformat(),
                )
                self._scores[probe.key] = ts

            ts.total_probes += 1
            if probe.ok:
                ts.successful_probes += 1
                # Exponential moving average for latency
                alpha = 0.3
                ts.avg_latency_ms = alpha * probe.latency_ms + (1 - alpha) * ts.avg_latency_ms
            else:
                ts.flags.append(f"FAIL at {probe.checked_at}")

            # Compute trust score: success rate * latency factor * recency factor
            success_rate = ts.successful_probes / ts.total_probes
            latency_factor = max(0.1, 1.0 - (ts.avg_latency_ms / 5000.0))  # 5s = 0.1
            recency_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.last_updated.replace('Z', '+00:00'))).total_seconds() / 3600
            recency_factor = max(0.1, 1.0 - (recency_hours / 168.0))  # 1 week decay

            ts.score = success_rate * latency_factor * recency_factor
            ts.last_updated = datetime.now(timezone.utc).isoformat()

            # Limit flags
            if len(ts.flags) > 10:
                ts.flags = ts.flags[-10:]

            return ts

    def get_score(self, source_key: str) -> SourceTrustScore | None:
        with self._lock:
            return self._scores.get(source_key)

    def get_all_scores(self) -> list[SourceTrustScore]:
        with self._lock:
            return list(self._scores.values())

    def get_untrustworthy(self, threshold: float = 0.3) -> list[SourceTrustScore]:
        with self._lock:
            return [ts for ts in self._scores.values() if ts.score < threshold]


# --- Cross-Source Consistency ---

@dataclass
class ConsistencyCheck:
    """Result of cross-source consistency check."""
    check_id: str
    timestamp: str
    sources_compared: list[str]
    metric: str
    values: dict[str, float]
    consistent: bool
    max_deviation: float
    threshold: float
    details: str

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "timestamp": self.timestamp,
            "sources_compared": self.sources_compared,
            "metric": self.metric,
            "values": self.values,
            "consistent": self.consistent,
            "max_deviation": self.max_deviation,
            "threshold": self.threshold,
            "details": self.details,
        }


class CrossSourceConsistencyChecker:
    """Compare overlapping metrics across sources for consistency."""

    def __init__(self, deviation_threshold: float = 0.15) -> None:
        self.deviation_threshold = deviation_threshold
        self._lock = threading.Lock()
        self._history: list[ConsistencyCheck] = []

    def check_consistency(
        self,
        sources_data: dict[str, dict],  # source_key -> {metric: value}
        metrics: list[str] | None = None,
    ) -> list[ConsistencyCheck]:
        """Compare metrics across sources that report the same metric."""
        if metrics is None:
            # Auto-detect common metrics
            all_metrics = set()
            for data in sources_data.values():
                all_metrics.update(data.keys())
            metrics = list(all_metrics)

        checks = []
        for metric in metrics:
            values = {}
            for src, data in sources_data.items():
                if metric in data and isinstance(data[metric], (int, float)):
                    values[src] = float(data[metric])

            if len(values) < 2:
                continue

            vals = list(values.values())
            mean_val = sum(vals) / len(vals)
            max_dev = max(abs(v - mean_val) / max(abs(mean_val), 1e-9) for v in vals)
            consistent = max_dev <= self.deviation_threshold

            check = ConsistencyCheck(
                check_id=f"cons-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                sources_compared=list(values.keys()),
                metric=metric,
                values=values,
                consistent=consistent,
                max_deviation=max_dev,
                threshold=self.deviation_threshold,
                details=f"Mean: {mean_val:.3f}, Max deviation: {max_dev:.3f} ({'OK' if consistent else 'INCONSISTENT'})",
            )
            checks.append(check)

        with self._lock:
            self._history.extend(checks)
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

        return checks

    def get_history(self, limit: int = 100) -> list[ConsistencyCheck]:
        with self._lock:
            return self._history[-limit:]


# --- Automatic Reconciliation & Re-optimization ---

class ReconciliationEngine:
    """Automatically reconcile state discrepancies and trigger re-optimization."""

    def __init__(
        self,
        consistency_checker: CrossSourceConsistencyChecker,
        event_bus: EventBus,
    ) -> None:
        self.consistency_checker = consistency_checker
        self.event_bus = event_bus
        self._lock = threading.Lock()
        self._reconciliation_rules: list[Callable[[list[ConsistencyCheck]], Optional[dict]]] = []

    def add_rule(self, rule: Callable[[list[ConsistencyCheck]], Optional[dict]]) -> None:
        """Add a reconciliation rule. Returns action dict or None."""
        with self._lock:
            self._reconciliation_rules.append(rule)

    def run_reconciliation(self, sources_data: dict[str, dict]) -> list[dict]:
        """Run consistency checks and apply reconciliation rules."""
        checks = self.consistency_checker.check_consistency(sources_data)
        actions = []

        for rule in self._reconciliation_rules:
            try:
                action = rule(checks)
                if action:
                    actions.append(action)
                    self.event_bus.publish("reconciliation.action", action)
            except Exception as e:
                actions.append({"error": str(e), "rule": str(rule)})

        return actions


class ReoptimizationTrigger:
    """Trigger re-optimization when state changes materially."""

    def __init__(
        self,
        event_bus: EventBus,
        twin_factory: Callable[[], Any],  # Callable that creates DigitalTwin
        optimizer_fn: Callable[[dict], dict],  # state -> optimized policy
        materiality_threshold: float = 0.05,  # 5% risk change
    ) -> None:
        self.event_bus = event_bus
        self.twin_factory = twin_factory
        self.optimizer_fn = optimizer_fn
        self.materiality_threshold = materiality_threshold
        self._last_state: dict | None = None
        self._last_optimization: dict | None = None
        self._lock = threading.Lock()

    def check_and_trigger(self, current_state: dict) -> Optional[dict]:
        """Check if state change is material, trigger re-optimization if so."""
        with self._lock:
            if self._last_state is None:
                self._last_state = current_state
                return None

            # Compare key metrics
            last_risk = self._last_state.get("risk", {}).get("risk", 0)
            curr_risk = current_state.get("risk", {}).get("risk", 0)
            risk_change = abs(curr_risk - last_risk) / max(abs(last_risk), 1e-6)

            # Check guardian action change
            last_guardian = self._last_state.get("guardian", {}).get("action")
            curr_guardian = current_state.get("guardian", {}).get("action")
            guardian_changed = last_guardian != curr_guardian

            material = risk_change > self.materiality_threshold or guardian_changed

            if material:
                # Trigger re-optimization
                try:
                    new_policy = self.optimizer_fn(current_state)
                    action = {
                        "trigger_id": f"reopt-{uuid.uuid4().hex[:8]}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason": f"risk_change={risk_change:.3f}" + (" guardian_changed" if guardian_changed else ""),
                        "previous_risk": last_risk,
                        "current_risk": curr_risk,
                        "previous_policy": self._last_optimization.get("policy") if self._last_optimization else None,
                        "new_policy": new_policy,
                        "material": True,
                    }
                    self._last_state = current_state
                    self._last_optimization = {"policy": new_policy, "timestamp": action["timestamp"]}
                    self.event_bus.publish("reoptimization.triggered", action)
                    return action
                except Exception as e:
                    return {"error": str(e), "material": True}

            return None


# --- Canonical Instances ---
source_trust_manager = SourceTrustManager()
consistency_checker = CrossSourceConsistencyChecker()
reconciliation_engine = ReconciliationEngine(consistency_checker, event_bus)


# --- Default Reconciliation Rules ---

def default_reconciliation_rules(checks: list) -> Optional[dict]:
    """Default: flag inconsistent sources, alert operators."""
    inconsistent = [c for c in checks if not c.consistent]
    if not inconsistent:
        return None

    return {
        "action": "alert",
        "type": "cross_source_inconsistency",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inconsistent_checks": [c.to_dict() for c in inconsistent],
        "recommendation": "Review source data quality; consider manual reconciliation",
    }


reconciliation_engine.add_rule(default_reconciliation_rules)


# --- Integration with Sources ---

def probe_all_sources_and_update_trust() -> dict[str, SourceTrustScore]:
    """Probe all sources and update trust scores."""
    # In real implementation, would probe actual endpoints
    # For now, return current trust scores
    return {ts.source_key: ts for ts in source_trust_manager.get_all_scores()}


# --- SSE / WebSocket Integration Helpers ---

def create_sse_response(topics: list[str]) -> tuple[str, dict]:
    """Create SSE response headers and initial event."""
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    # Initial connection event
    initial = f"event: connected\ndata: {json.dumps({'topics': topics, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
    return initial, headers


async def sse_stream(topics: list[str], event_bus: EventBus):
    """Async generator for SSE stream."""
    conn = SSEConnection(topics, event_bus)
    async for event in conn:
        yield event


# --- Topics for Frontend ---
FRONTEND_TOPICS = [
    "twin.updates",
    "guardian.verdicts",
    "alerts.firing",
    "incidents.lifecycle",
    "decisions.lifecycle",
    "metrics.snapshot",
    "sources.heartbeat",
]