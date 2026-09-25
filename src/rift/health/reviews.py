"""Clinician review ledger: ACCEPT / REJECT / OVERRIDE / REQUEST_REVIEW (Phase 14).

Append-only, hash-chained, in-memory. Every review attaches to an evidence
bundle and records who judged what and why. An OVERRIDE never edits a
prediction or a prior review — it appends a superseding judgment that
references the entry it supersedes, so the full disagreement history stays
auditable.

Fail-closed validation: unknown actions, missing reviewer, missing evidence
reference, and rationale-free OVERRIDE/REJECT are rejected, never stored.

Durable persistence (a reviews table behind the API) is required before any
clinical use; `export()` produces the handoff payload. The in-memory ledger
is demonstration-grade by design, like the prospective ledger.
"""
from __future__ import annotations

import hashlib
import json
import time

ACTIONS = ("ACCEPT", "REJECT", "OVERRIDE", "REQUEST_REVIEW")

# Rationale is mandatory where the clinician disagrees or takes
# responsibility; ACCEPT and REQUEST_REVIEW may carry an empty note.
RATIONALE_REQUIRED = frozenset({"REJECT", "OVERRIDE"})

MAX_REVIEWS_LISTED = 200


def _canonical(action: str, evidence_id: str, reviewer_id: str,
               rationale: str, supersedes: str | None) -> str:
    return json.dumps(
        {"action": action, "evidence_id": evidence_id,
         "reviewer_id": reviewer_id, "rationale": rationale or "",
         "supersedes": supersedes or ""},
        sort_keys=True, separators=(",", ":"))


class ReviewLedger:
    """Append-only clinician-judgment log with tamper-evident chaining."""

    def __init__(self) -> None:
        self._entries: dict[str, dict] = {}
        self._order: list[str] = []
        self._head_hash = "GENESIS"

    def record(self, *, action: str, evidence_id: str, reviewer_id: str,
               rationale: str = "", supersedes: str | None = None) -> dict:
        """Append one review. Idempotent on identical inputs; raises ValueError otherwise."""
        action = str(action or "").upper()
        if action not in ACTIONS:
            raise ValueError(f"unknown review action {action!r}; expected one of {list(ACTIONS)}")
        evidence_id = str(evidence_id or "").strip()
        if not evidence_id:
            raise ValueError("evidence_id is required: a review must attach to an evidence bundle")
        reviewer_id = str(reviewer_id or "").strip()
        if not reviewer_id:
            raise ValueError("reviewer_id is required: anonymous reviews are not auditable")
        rationale = str(rationale or "")
        if action in RATIONALE_REQUIRED and not rationale.strip():
            raise ValueError(f"rationale is required for {action}: disagreement without reason is not auditable")
        if supersedes is not None and supersedes not in self._entries:
            raise ValueError(f"supersedes references unknown review {supersedes!r}")
        review_id = hashlib.sha256(_canonical(
            action, evidence_id, reviewer_id, rationale, supersedes).encode()).hexdigest()
        if review_id not in self._entries:
            entry = {
                "review_id": review_id,
                "action": action,
                "evidence_id": evidence_id,
                "reviewer_id": reviewer_id,
                "rationale": rationale,
                "supersedes": supersedes,
                "prev_hash": self._head_hash,
                "recorded_at": time.time(),
            }
            self._entries[review_id] = entry
            self._order.append(review_id)
            self._head_hash = review_id
        return dict(self._entries[review_id])

    def list(self, limit: int = MAX_REVIEWS_LISTED) -> list[dict]:
        """Newest first, capped like list_runs (200)."""
        limit = max(0, int(limit))
        return [dict(self._entries[rid]) for rid in reversed(self._order[-limit:] if limit else [])]

    def stats(self) -> dict:
        counts = {action: 0 for action in ACTIONS}
        for rid in self._order:
            counts[self._entries[rid]["action"]] += 1
        return {"total": len(self._order), "by_action": counts, "head_hash": self._head_hash}

    def export(self) -> list[dict]:
        """Full ordered payload for durable persistence handoff."""
        return [dict(self._entries[rid]) for rid in self._order]

    def reset(self) -> None:
        self._entries.clear()
        self._order.clear()
        self._head_hash = "GENESIS"


ledger = ReviewLedger()
