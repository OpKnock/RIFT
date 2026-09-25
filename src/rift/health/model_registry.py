"""Model registry: every prediction traceable to an exact model version.

The registry is code + committed data (not a live service): entries pin the
weights digest, threshold, calibration method, and deployment status. At
prediction time the twin stamps each snapshot with the model_id and the
LIVE weights digest, so weight tampering or drift is detectable by
comparison (`verify_weights`). Status transitions (research → validated)
require evidence, never an edit made lightly — see deployment_gate().
"""
from __future__ import annotations

import hashlib
import json

REGISTRY = {
    # weights_digest pinned 2026-09-24 after review of RISK_WEIGHTS +
    # TRANSITION_WEIGHTS. Any weight edit changes the live digest and makes
    # verify_weights() report match=False. Update the pin only with a
    # reviewed commit that re-runs the full evidence suite.
    "cardiac-strain-v1": {
        "model_id": "cardiac-strain-v1",
        "target": "high cardiac-strain day (24h horizon)",
        "threshold": 0.6,
        "weights_digest": "cb5ee2d9a1a04c93dc4a4d13009cfcdbd19a823b036c3d3ab50ce96ff49ea1d3",
        "dataset_versions": ["synthetic-14d-v1", "synthetic-60d-v1", "synthetic-external-v1"],
        "schema_version": "patient-state-v1",
        "calibration": {"method": "platt-scaling", "fit": "days 30-44", "status": "demo-fit"},
        "status": "research",
        "deployment_gate": "closed",
    }
}

DEFAULT_MODEL_ID = "cardiac-strain-v1"


def weights_digest() -> str:
    """Live SHA-256 over the canonical risk + transition weights."""
    from .risk import RISK_WEIGHTS
    from .transition import TRANSITION_WEIGHTS

    canonical = json.dumps(
        {"risk": RISK_WEIGHTS, "transition": TRANSITION_WEIGHTS}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_model(model_id: str = DEFAULT_MODEL_ID) -> dict:
    """Return a copy of a registry entry; KeyError on unknown ids."""
    if model_id not in REGISTRY:
        raise KeyError(f"unknown model_id: {model_id!r}")
    return dict(REGISTRY[model_id])


def verify_weights(model_id: str = DEFAULT_MODEL_ID) -> dict:
    """Check live weights against the registry pin (drift/tamper detection).

    An UNPINNED entry (no digest recorded) reports match=False with an
    explicit unpinned flag — never a silent True. Only an exact digest
    match counts as verified.
    """
    entry = get_model(model_id)
    live = weights_digest()
    pinned = entry.get("weights_digest")
    if pinned is None:
        return {
            "model_id": model_id,
            "live_digest": live,
            "pinned_digest": None,
            "match": False,
            "unpinned": True,
            "note": "no digest recorded: pin after review to enforce exact-weight deployment",
        }
    return {
        "model_id": model_id,
        "live_digest": live,
        "pinned_digest": pinned,
        "match": pinned == live,
        "unpinned": False,
        "note": "exact digest match required",
    }


def deployment_gate(model_id: str = DEFAULT_MODEL_ID, evidence: dict | None = None) -> dict:
    """Should clinical-use mode be enabled? Decided by evidence, not optimism.

    Consumes an evidence artifact — {"events": int, "non_events": int,
    "calibrated": bool, "clinical_review": bool, "synthetic": bool} —
    rather than baking one dataset's numbers into source. Without an
    explicit artifact, falls back to the clearly labeled bundled synthetic
    snapshot. Closed until: adequate independent events, calibrated
    probabilities on held-out data, and human clinical review — all
    recorded, none assumed.
    """
    entry = get_model(model_id)
    if evidence is None:
        evidence = {
            "source": "bundled synthetic snapshot (not a live assessment)",
            "events": 5,
            "non_events": 54,
            "calibrated": False,
            "clinical_review": False,
            "synthetic": True,
        }
    reasons: list[str] = []
    if evidence.get("events", 0) < 100 or evidence.get("non_events", 0) < 100:
        reasons.append(
            f"external evidence below the 100/100 adequacy bar "
            f"({evidence.get('events')} events / {evidence.get('non_events')} non-events)"
        )
    if not evidence.get("calibrated"):
        reasons.append("probabilities uncalibrated for deployment (demo Platt fit only)")
    if not evidence.get("clinical_review"):
        reasons.append("no clinical review recorded")
    if evidence.get("synthetic", True):
        reasons.append("synthetic weights and outcome rule throughout")
    open_gate = (
        entry.get("status") == "validated"
        and entry.get("deployment_gate") == "open"
        and not reasons
    )
    return {
        "model_id": model_id,
        "clinical_use": "open" if open_gate else "closed",
        "evidence_source": evidence.get("source", "caller-supplied"),
        "reasons": [] if open_gate else reasons,
    }


STATUS_LIFECYCLE = ("research", "candidate", "validated", "approved",
                    "deployed", "retired", "blocked")

AUDIT_LOG: list[dict] = []


def promote(model_id: str = DEFAULT_MODEL_ID, target: str = "candidate",
            evidence: dict | None = None, approver: str = "",
            notes: str = "") -> dict:
    """Move a model one lifecycle step forward under evidence rules.

    - Exactly one step at a time (no skipping research → deployed).
    - research → candidate: any recorded evidence artifact.
    - candidate → validated: adequate events, calibrated, non-synthetic,
      clinical review recorded.
    - validated → approved / approved → deployed: require approver identity
      plus the validated evidence re-supplied (no stale approvals).
    - deployed → retired, or any → blocked with a reason in notes.
    Every decision appends to AUDIT_LOG. Raises ValueError on violation.
    """
    if model_id not in REGISTRY:
        raise KeyError(f"unknown model_id: {model_id!r}")
    if target not in STATUS_LIFECYCLE:
        raise ValueError(f"unknown status {target!r}")
    entry = REGISTRY[model_id]
    current = entry.get("status", "research")
    if target == current:
        raise ValueError(f"already at status {current!r}: transitions must move")
    order = list(STATUS_LIFECYCLE)
    if target == "blocked":
        allowed_from = [s for s in order if s != "blocked"]
    elif target == "retired":
        allowed_from = ["deployed", "approved", "validated", "candidate", "research"]
    else:
        allowed_from = [order[order.index(target) - 1]] if target in order[1:] else []
        if target == "research":
            allowed_from = []
    if current not in allowed_from:
        raise ValueError(f"illegal transition {current!r} → {target!r}: one step at a time")
    evidence = evidence or {}
    if target in ("validated", "approved", "deployed"):
        missing = [k for k in ("events", "non_events", "calibrated", "clinical_review", "synthetic")
                   if k not in evidence]
        if missing:
            raise ValueError(f"promotion to {target!r} requires evidence keys: {missing}")
        if target == "validated" and (
                evidence["events"] < 100 or evidence["non_events"] < 100
                or not evidence["calibrated"] or evidence["synthetic"]
                or not evidence["clinical_review"]):
            raise ValueError("promotion to 'validated' requires adequate, calibrated, "
                             "reviewed, non-synthetic evidence")
    if target in ("approved", "deployed") and not approver.strip():
        raise ValueError(f"promotion to {target!r} requires an approver identity")
    if not notes.strip():
        raise ValueError("promotion requires written notes (why, on what evidence)")
    previous = current
    entry["status"] = target
    if target == "deployed":
        entry["deployment_gate"] = "open"
    if target in ("retired", "blocked"):
        entry["deployment_gate"] = "closed"
    AUDIT_LOG.append({"model_id": model_id, "from": previous, "to": target,
                      "approver": approver.strip() or None, "notes": notes.strip()})
    return {"model_id": model_id, "from": previous, "to": target}


def rollback(model_id: str = DEFAULT_MODEL_ID, reason: str = "") -> dict:
    """Return a deployed/approved model to its previous recorded status.

    Rollback never deletes history: it appends, like every other transition.
    """
    if model_id not in REGISTRY:
        raise KeyError(f"unknown model_id: {model_id!r}")
    if not reason.strip():
        raise ValueError("rollback requires a reason")
    entry = REGISTRY[model_id]
    current = entry.get("status", "research")
    previous = None
    for record in reversed(AUDIT_LOG):
        if record["model_id"] == model_id and record["to"] == current:
            previous = record["from"]
            break
    if previous is None:
        raise ValueError(f"no recorded previous status to roll back from {current!r}")
    entry["status"] = previous
    entry["deployment_gate"] = "closed"
    AUDIT_LOG.append({"model_id": model_id, "from": current, "to": previous,
                      "approver": None, "notes": f"ROLLBACK: {reason.strip()}"})
    return {"model_id": model_id, "from": current, "to": previous}


def get_audit_log(model_id: str | None = None) -> list[dict]:
    """Copy of the promotion/rollback audit trail, optionally filtered."""
    return [dict(r) for r in AUDIT_LOG if model_id is None or r["model_id"] == model_id]
