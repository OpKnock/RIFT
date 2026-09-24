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
    "cardiac-strain-v1": {
        "model_id": "cardiac-strain-v1",
        "target": "high cardiac-strain day (24h horizon)",
        "threshold": 0.6,
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
    """Check live weights against the registry pin (drift/tamper detection)."""
    entry = get_model(model_id)
    live = weights_digest()
    pinned = entry.get("weights_digest")
    return {
        "model_id": model_id,
        "live_digest": live,
        "pinned_digest": pinned,
        "match": pinned is None or pinned == live,
        "note": "pin the digest after review to enforce exact-weight deployment",
    }


def deployment_gate(model_id: str = DEFAULT_MODEL_ID) -> dict:
    """Should clinical-use mode be enabled? Decided by evidence, not optimism.

    Closed until: adequate independent events, calibrated probabilities on
    held-out data, and human clinical review — all recorded, none assumed.
    """
    entry = get_model(model_id)
    reasons = [
        "external evidence below the 100/100 adequacy bar (5 events / 54 non-events)",
        "probabilities uncalibrated for deployment (demo Platt fit only)",
        "no clinical review recorded",
        "synthetic weights and outcome rule throughout",
    ]
    open_gate = entry.get("status") == "validated" and entry.get("deployment_gate") == "open"
    return {
        "model_id": model_id,
        "clinical_use": "open" if open_gate else "closed",
        "reasons": [] if open_gate else reasons,
    }
