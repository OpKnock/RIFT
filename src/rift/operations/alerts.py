"""Alert routing and notification (Phase 6).

Routes evaluated alert rules to operators via configured channels.
In-process implementation; production would wire to PagerDuty/Slack/email.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class AlertChannel(Enum):
    LOG = "log"
    CONSOLE = "console"
    WEBHOOK = "webhook"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    SLACK = "slack"


@dataclass
class AlertRoute:
    """Routing rule: which alerts go to which channels."""
    name: str
    channels: list[AlertChannel]
    severity_filter: list[str] = field(default_factory=lambda: ["critical", "high", "medium", "low"])
    rule_filter: list[str] = field(default_factory=list)  # empty = all rules
    handler: Callable[[dict], None] | None = None


@dataclass
class Notification:
    """A delivered notification."""
    alert_rule: str
    severity: str
    reason: str
    channels: list[AlertChannel]
    delivered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delivery_results: dict[str, str] = field(default_factory=dict)


class AlertRouter:
    """Routes alerts to configured notification channels."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._routes: list[AlertRoute] = []
        self._history: list[Notification] = []
        self._handlers: dict[AlertChannel, Callable[[dict], None]] = {}
        # Default: log everything
        self.add_route(AlertRoute(
            name="default-log",
            channels=[AlertChannel.LOG],
            severity_filter=["critical", "high", "medium", "low"],
        ))

    def register_handler(self, channel: AlertChannel, handler: Callable[[dict], None]) -> None:
        with self._lock:
            self._handlers[channel] = handler

    def add_route(self, route: AlertRoute) -> None:
        with self._lock:
            self._routes.append(route)

    def remove_route(self, name: str) -> bool:
        with self._lock:
            for i, route in enumerate(self._routes):
                if route.name == name:
                    del self._routes[i]
                    return True
            return False

    def route(self, alert: dict) -> Notification:
        """Route an alert through matching routes."""
        severity = alert.get("severity", "medium").lower()
        rule = alert.get("rule", "")
        matched_channels: set[AlertChannel] = set()

        with self._lock:
            routes = list(self._routes)

        for route in routes:
            if severity not in route.severity_filter:
                continue
            if route.rule_filter and rule not in route.rule_filter:
                continue
            matched_channels.update(route.channels)

        notification = Notification(
            alert_rule=rule,
            severity=severity,
            reason=alert.get("reason", ""),
            channels=list(matched_channels),
        )

        for channel in matched_channels:
            handler = self._handlers.get(channel)
            if handler:
                try:
                    payload = {
                        "rule": rule,
                        "severity": severity,
                        "reason": alert.get("reason", ""),
                        "firing": alert.get("firing", True),
                        "timestamp": notification.delivered_at,
                    }
                    handler(payload)
                    notification.delivery_results[channel.value] = "delivered"
                except Exception as e:
                    notification.delivery_results[channel.value] = f"failed: {e}"
            else:
                notification.delivery_results[channel.value] = "no handler"

        with self._lock:
            self._history.append(notification)
            # Keep last 1000
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

        return notification

    def history(self, limit: int = 100) -> list[Notification]:
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def stats(self) -> dict:
        with self._lock:
            by_channel = {}
            for n in self._history:
                for ch in n.channels:
                    by_channel[ch.value] = by_channel.get(ch.value, 0) + 1
            return {
                "total_routed": len(self._history),
                "by_channel": by_channel,
                "routes_configured": len(self._routes),
            }


def default_log_handler(payload: dict) -> None:
    """Default handler writes to stdout (captured by logging)."""
    import logging
    logger = logging.getLogger("rift.alerts")
    logger.warning("ALERT: rule=%s severity=%s reason=%s firing=%s",
                   payload["rule"], payload["severity"], payload["reason"], payload["firing"])


alert_router = AlertRouter()
alert_router.register_handler(AlertChannel.LOG, default_log_handler)
alert_router.register_handler(AlertChannel.CONSOLE, lambda p: print(f"[ALERT] {p}"))