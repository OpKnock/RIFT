"""Decision lifecycle management (Phase 6).

Tracks every operational decision from proposal through approval/
rejection/override to execution and postmortem. Integrates with
Guardian verdicts and incident linkage.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DecisionAction(Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    REQUEST_REVIEW = "request_review"
    EXECUTED = "executed"
    EXPIRED = "expired"


class DecisionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    UNDER_REVIEW = "under_review"
    EXECUTED = "executed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class DecisionEvent:
    """Immutable event in the decision timeline."""
    timestamp: str
    actor: str
    action: DecisionAction
    note: str
    guardian_verdict: dict | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action.value,
            "note": self.note,
            "guardian_verdict": self.guardian_verdict,
            "metadata": self.metadata,
        }


@dataclass
class Decision:
    """Operational decision with full lifecycle and Guardian integration."""
    id: str
    scenario_id: str
    policy: dict
    proposed_by: str
    proposed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: DecisionStatus = DecisionStatus.PENDING
    guardian_verdict: dict | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    overridden_by: str | None = None
    overridden_at: str | None = None
    executed_at: str | None = None
    expired_at: str | None = None
    execution_result: dict | None = None
    linked_incident_id: str | None = None
    review_requested_by: str | None = None
    review_requested_at: str | None = None
    timeline: list[DecisionEvent] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_event(
        self,
        actor: str,
        action: DecisionAction,
        note: str,
        guardian_verdict: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.timeline.append(DecisionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            note=note,
            guardian_verdict=guardian_verdict,
            metadata=metadata or {},
        ))

    def accept(self, actor: str, note: str, guardian_verdict: dict | None = None) -> None:
        if self.status != DecisionStatus.PENDING:
            raise ValueError(f"Cannot accept decision in status {self.status.value}")
        self.status = DecisionStatus.APPROVED
        self.approved_by = actor
        self.approved_at = datetime.now(timezone.utc).isoformat()
        self.guardian_verdict = guardian_verdict
        self.add_event(actor, DecisionAction.ACCEPTED, note, guardian_verdict)

    def reject(self, actor: str, note: str, guardian_verdict: dict | None = None) -> None:
        if self.status not in (DecisionStatus.PENDING, DecisionStatus.UNDER_REVIEW):
            raise ValueError(f"Cannot reject decision in status {self.status.value}")
        self.status = DecisionStatus.REJECTED
        self.rejected_by = actor
        self.rejected_at = datetime.now(timezone.utc).isoformat()
        self.guardian_verdict = guardian_verdict
        self.add_event(actor, DecisionAction.REJECTED, note, guardian_verdict)

    def override(self, actor: str, note: str, guardian_verdict: dict | None = None) -> None:
        if self.status != DecisionStatus.REJECTED:
            raise ValueError(f"Can only override a rejected decision, current status: {self.status.value}")
        self.status = DecisionStatus.OVERRIDDEN
        self.overridden_by = actor
        self.overridden_at = datetime.now(timezone.utc).isoformat()
        self.guardian_verdict = guardian_verdict
        self.add_event(actor, DecisionAction.OVERRIDDEN, note, guardian_verdict)

    def request_review(self, actor: str, note: str) -> None:
        if self.status not in (DecisionStatus.PENDING, DecisionStatus.REJECTED):
            raise ValueError(f"Cannot request review in status {self.status.value}")
        self.status = DecisionStatus.UNDER_REVIEW
        self.review_requested_by = actor
        self.review_requested_at = datetime.now(timezone.utc).isoformat()
        self.add_event(actor, DecisionAction.REQUEST_REVIEW, note)

    def execute(self, actor: str, result: dict) -> None:
        if self.status != DecisionStatus.APPROVED:
            raise ValueError(f"Can only execute approved decision, current status: {self.status.value}")
        self.status = DecisionStatus.EXECUTED
        self.executed_at = datetime.now(timezone.utc).isoformat()
        self.execution_result = result
        self.add_event(actor, DecisionAction.EXECUTED, "Decision executed", metadata={"result": result})

    def expire(self, actor: str = "system", note: str = "Decision expired without action") -> None:
        if self.status in (DecisionStatus.EXECUTED, DecisionStatus.EXPIRED):
            return
        self.status = DecisionStatus.EXPIRED
        self.expired_at = datetime.now(timezone.utc).isoformat()
        self.add_event(actor, DecisionAction.EXPIRED, note)

    def link_incident(self, incident_id: str) -> None:
        self.linked_incident_id = incident_id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "policy": self.policy,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "status": self.status.value,
            "guardian_verdict": self.guardian_verdict,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejected_by": self.rejected_by,
            "rejected_at": self.rejected_at,
            "overridden_by": self.overridden_by,
            "overridden_at": self.overridden_at,
            "executed_at": self.executed_at,
            "expired_at": self.expired_at,
            "execution_result": self.execution_result,
            "linked_incident_id": self.linked_incident_id,
            "review_requested_by": self.review_requested_by,
            "review_requested_at": self.review_requested_at,
            "timeline": [e.to_dict() for e in self.timeline],
            "metadata": self.metadata,
        }


class DecisionStore:
    """Thread-safe in-memory decision store with query support."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decisions: dict[str, Decision] = {}

    def create(
        self,
        scenario_id: str,
        policy: dict,
        proposed_by: str,
        guardian_verdict: dict | None = None,
        metadata: dict | None = None,
    ) -> Decision:
        with self._lock:
            decision_id = f"dec-{uuid.uuid4().hex[:12]}"
            decision = Decision(
                id=decision_id,
                scenario_id=scenario_id,
                policy=policy,
                proposed_by=proposed_by,
                guardian_verdict=guardian_verdict,
                metadata=metadata or {},
            )
            self._decisions[decision_id] = decision
            return decision

    def get(self, decision_id: str) -> Decision | None:
        with self._lock:
            return self._decisions.get(decision_id)

    def list(
        self,
        status: DecisionStatus | None = None,
        scenario_id: str | None = None,
        proposed_by: str | None = None,
        limit: int = 100,
    ) -> list[Decision]:
        with self._lock:
            decisions = list(self._decisions.values())
            if status:
                decisions = [d for d in decisions if d.status == status]
            if scenario_id:
                decisions = [d for d in decisions if d.scenario_id == scenario_id]
            if proposed_by:
                decisions = [d for d in decisions if d.proposed_by == proposed_by]
            decisions.sort(key=lambda d: d.proposed_at, reverse=True)
            return decisions[:limit]

    def stats(self) -> dict:
        with self._lock:
            total = len(self._decisions)
            by_status = {}
            for dec in self._decisions.values():
                by_status[dec.status.value] = by_status.get(dec.status.value, 0) + 1
            return {
                "total": total,
                "by_status": by_status,
            }


decision_store = DecisionStore()