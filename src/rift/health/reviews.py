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
import os
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
    """Append-only clinician-judgment log with tamper-evident chaining.

    Crash-safe JSONL durability by default (``RIFT_DATA_DIR``/``./data``;
    every record fsynced on append, replayed on startup). Set
    ``RIFT_REVIEWS_LEDGER`` to override the path, or to empty string to
    force pure in-memory mode (tests only — audit data is then lost on
    restart).
    """

    def __init__(self, store_path: str | None = None) -> None:
        from ..durable import JsonlStore
        self._entries: dict[str, dict] = {}
        self._order: list[str] = []
        self._head_hash = "GENESIS"
        self._store = JsonlStore(store_path) if store_path else None
        if self._store is not None:
            for entry in self._store.load():
                rid = entry.get("review_id")
                if isinstance(rid, str) and rid and rid not in self._entries:
                    self._entries[rid] = entry
                    self._order.append(rid)
                    self._head_hash = rid

    def record(self, *, action: str, evidence_id: str, reviewer_id: str,
               rationale: str = "", supersedes: str | None = None,
               identity_verified: bool = True) -> dict:
        """Append one review. Idempotent on identical inputs; raises ValueError otherwise.

        identity_verified records whether reviewer_id came from a verified
        principal (JWT sub / service-token session) as opposed to a
        caller-asserted value in open dev mode. It travels in the entry
        but is excluded from the dedup hash (same review content dedups
        regardless of how identity was established).
        """
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
                "identity_verified": bool(identity_verified),
                "rationale": rationale,
                "supersedes": supersedes,
                "prev_hash": self._head_hash,
                "recorded_at": time.time(),
            }
            self._entries[review_id] = entry
            self._order.append(review_id)
            self._head_hash = review_id
            if self._store is not None:
                self._store.append(entry)
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
        """Clear memory only. The durable file (if any) is never wiped by
        reset: audit data must be deleted by explicit operator action."""
        self._entries.clear()
        self._order.clear()
        self._head_hash = "GENESIS"

    @property
    def durable(self) -> bool:
        """True when backed by a crash-safe file, False when in-memory demo."""
        return self._store is not None


def _default_store_path(env_name: str, filename: str) -> str | None:
    """Durable-by-default ledger path.

    Explicit env value wins (empty string forces pure in-memory, e.g. for
    tests); otherwise ``RIFT_DATA_DIR``/``./data`` holds crash-safe JSONL.
    """
    explicit = os.environ.get(env_name)
    if explicit is not None:
        return explicit or None
    base = os.environ.get("RIFT_DATA_DIR", "data")
    return os.path.join(base, filename)


_ledger: ReviewLedger | None = None


def get_ledger() -> ReviewLedger:
    """Process-wide review ledger, constructed on first use.

    Lazy (not import-time) so importing the module never touches the
    filesystem: the durable JSONL file is created on first actual use.
    """
    global _ledger
    if _ledger is None:
        _ledger = ReviewLedger(store_path=_default_store_path("RIFT_REVIEWS_LEDGER", "reviews.jsonl"))
    return _ledger


def __getattr__(name: str):
    # Legacy attribute access (reviews.ledger) resolves through the
    # lazy singleton. Prefer get_ledger() in new code.
    if name == "ledger":
        return get_ledger()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
