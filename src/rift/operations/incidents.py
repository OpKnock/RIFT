"""Incident lifecycle management (Phase 6).

In-process incident store with full lifecycle: open → acknowledged →
investigating → resolved → closed. Every transition is recorded with
operator, timestamp, and note. Incidents link to triggering alerts,
affected decisions, and Guardian findings.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class IncidentSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentStatus(Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentType(Enum):
    ALERT_FIRING = "alert_firing"
    GUARDIAN_WITHHOLD = "guardian_withhold"
    PREDICTION_ANOMALY = "prediction_anomaly"
    DATA_QUALITY = "data_quality"
    MODEL_DRIFT = "model_drift"
    DECISION_FAILURE = "decision_failure"
    MANUAL = "manual"


@dataclass(frozen=True)
class IncidentEvent:
    """Immutable event in the incident timeline."""
    timestamp: str
    actor: str
    action: str
    note: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "note": self.note,
            "metadata": self.metadata,
        }


@dataclass
class Incident:
    """Operational incident with full audit trail."""
    id: str
    type: IncidentType
    severity: IncidentSeverity
    title: str
    description: str
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    closed_at: str | None = None
    owner: str | None = None
    trigger_alert_id: str | None = None
    affected_decision_ids: list[str] = field(default_factory=list)
    guardian_findings: list[dict] = field(default_factory=list)
    timeline: list[IncidentEvent] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_event(self, actor: str, action: str, note: str, metadata: dict | None = None) -> None:
        self.timeline.append(IncidentEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            note=note,
            metadata=metadata or {},
        ))
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def acknowledge(self, actor: str, note: str = "") -> None:
        if self.status != IncidentStatus.OPEN:
            raise ValueError(f"Cannot acknowledge incident in status {self.status.value}")
        self.status = IncidentStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(timezone.utc).isoformat()
        self.owner = actor
        self.add_event(actor, "acknowledge", note or "Incident acknowledged")

    def investigate(self, actor: str, note: str) -> None:
        if self.status not in (IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED):
            raise ValueError(f"Cannot investigate incident in status {self.status.value}")
        self.status = IncidentStatus.INVESTIGATING
        self.add_event(actor, "investigate", note)

    def resolve(self, actor: str, note: str) -> None:
        if self.status not in (IncidentStatus.ACKNOWLEDGED, IncidentStatus.INVESTIGATING):
            raise ValueError(f"Cannot resolve incident in status {self.status.value}")
        self.status = IncidentStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc).isoformat()
        self.add_event(actor, "resolve", note)

    def close(self, actor: str, note: str = "") -> None:
        if self.status != IncidentStatus.RESOLVED:
            raise ValueError(f"Cannot close incident in status {self.status.value}")
        self.status = IncidentStatus.CLOSED
        self.closed_at = datetime.now(timezone.utc).isoformat()
        self.add_event(actor, "close", note or "Incident closed")

    def reopen(self, actor: str, note: str) -> None:
        if self.status != IncidentStatus.CLOSED:
            raise ValueError(f"Cannot reopen incident in status {self.status.value}")
        self.status = IncidentStatus.OPEN
        self.add_event(actor, "reopen", note)

    def add_decision_link(self, decision_id: str) -> None:
        if decision_id not in self.affected_decision_ids:
            self.affected_decision_ids.append(decision_id)
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_guardian_finding(self, finding: dict) -> None:
        self.guardian_findings.append(finding)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "closed_at": self.closed_at,
            "owner": self.owner,
            "trigger_alert_id": self.trigger_alert_id,
            "affected_decision_ids": self.affected_decision_ids,
            "guardian_findings": self.guardian_findings,
            "timeline": [e.to_dict() for e in self.timeline],
            "tags": self.tags,
            "metadata": self.metadata,
        }


class IncidentStore:
    """Thread-safe in-memory incident store with query support."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._incidents: dict[str, Incident] = {}
        self._alert_to_incident: dict[str, str] = {}

    def create(
        self,
        type: IncidentType,
        severity: IncidentSeverity,
        title: str,
        description: str,
        trigger_alert_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Incident:
        with self._lock:
            incident_id = f"inc-{uuid.uuid4().hex[:12]}"
            incident = Incident(
                id=incident_id,
                type=type,
                severity=severity,
                title=title,
                description=description,
                trigger_alert_id=trigger_alert_id,
                tags=tags or [],
                metadata=metadata or {},
            )
            self._incidents[incident_id] = incident
            if trigger_alert_id:
                self._alert_to_incident[trigger_alert_id] = incident_id
            return incident

    def get(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def list(
        self,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        type: IncidentType | None = None,
        owner: str | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        with self._lock:
            incidents = list(self._incidents.values())
            if status:
                incidents = [i for i in incidents if i.status == status]
            if severity:
                incidents = [i for i in incidents if i.severity == severity]
            if type:
                incidents = [i for i in incidents if i.type == type]
            if owner:
                incidents = [i for i in incidents if i.owner == owner]
            incidents.sort(key=lambda i: i.created_at, reverse=True)
            return incidents[:limit]

    def by_alert(self, alert_id: str) -> Incident | None:
        with self._lock:
            incident_id = self._alert_to_incident.get(alert_id)
            if incident_id:
                return self._incidents.get(incident_id)
            return None

    def stats(self) -> dict:
        with self._lock:
            total = len(self._incidents)
            by_status = {}
            by_severity = {}
            for inc in self._incidents.values():
                by_status[inc.status.value] = by_status.get(inc.status.value, 0) + 1
                by_severity[inc.severity.value] = by_severity.get(inc.severity.value, 0) + 1
            open_critical = sum(1 for i in self._incidents.values()
                                if i.status == IncidentStatus.OPEN and i.severity == IncidentSeverity.CRITICAL)
            return {
                "total": total,
                "by_status": by_status,
                "by_severity": by_severity,
                "open_critical": open_critical,
            }


incident_store = IncidentStore()