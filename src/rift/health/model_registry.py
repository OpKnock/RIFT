"""Model registry: every prediction traceable to an exact model version.

The registry is code + committed data (not a live service): entries pin the
weights digest, threshold, calibration method, and deployment status. At
prediction time the twin stamps each snapshot with the model_id and the
LIVE weights digest, so weight tampering or drift is detectable by
comparison (`verify_weights`). Status transitions (research → validated)
require evidence, never an edit made lightly — see deployment_gate().

Phase 11 additions:
- Model versioning with semantic versioning
- Model metadata and provenance
- Model digests/hashes
- Model validation status
- Model evidence requirements
- Model shadow mode
- Champion/challenger testing
- Model regression testing
- Model drift monitoring
- Calibration monitoring
- Lineage tracking (model-to-data, model-to-experiment, model-to-decision)
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

REGISTRY = {
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
        # Phase 11 additions
        "version": "1.0.0",
        "created_at": "2026-09-24T00:00:00Z",
        "created_by": "system",
        "description": "Initial cardiac strain risk model",
        "hyperparameters": {"platt_scaling": True, "baseline_window": 7},
        "training_data_hash": "synthetic-14d-v1-hash",
        "validation_metrics": {"auc": 0.72, "brier": 0.18, "calibration_slope": 0.95},
        "evidence_requirements": {"min_events": 100, "min_non_events": 100, "calibrated": True, "clinical_review": True, "non_synthetic": True},
        "shadow_mode": False,
        "challenger_id": None,
        "lineage": {"data": [], "experiments": [], "decisions": []},
        "drift_metrics": {},
        "calibration_history": [],
    }
}

DEFAULT_MODEL_ID = "cardiac-strain-v1"

STATUS_LIFECYCLE = ("research", "candidate", "validated", "approved", "deployed", "retired", "blocked")

# Thread-safe audit log
_AUDIT_LOCK = threading.Lock()
AUDIT_LOG: list[dict] = []

# Drift monitoring storage
_DRIFT_LOCK = threading.Lock()
DRIFT_HISTORY: dict[str, list[dict]] = {}

# Lineage tracking
_LINEAGE_LOCK = threading.Lock()
MODEL_LINEAGE: dict[str, dict] = {}  # model_id -> {data: [], experiments: [], decisions: []}


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
    """Should clinical-use mode be enabled? Decided by evidence, not optimism."""
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


# --- Phase 11: Model Versioning & Metadata ---

@dataclass(frozen=True)
class ModelVersion:
    """A specific version of a model with full metadata."""
    model_id: str
    version: str  # semantic version: MAJOR.MINOR.PATCH
    weights_digest: str
    description: str
    hyperparameters: dict
    training_data_hash: str
    validation_metrics: dict
    evidence: dict
    status: str
    created_at: str
    created_by: str
    parent_version: str | None = None
    changelog: str = ""

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "weights_digest": self.weights_digest,
            "description": self.description,
            "hyperparameters": self.hyperparameters,
            "training_data_hash": self.training_data_hash,
            "validation_metrics": self.validation_metrics,
            "evidence": self.evidence,
            "status": self.status,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "parent_version": self.parent_version,
            "changelog": self.changelog,
        }


# Version store per model
_VERSION_STORE: dict[str, list[ModelVersion]] = {}
_VERSION_LOCK = threading.Lock()


def register_model_version(
    model_id: str,
    version: str,
    weights_digest: str,
    description: str,
    hyperparameters: dict,
    training_data_hash: str,
    validation_metrics: dict,
    evidence: dict,
    status: str = "research",
    created_by: str = "system",
    parent_version: str | None = None,
    changelog: str = "",
) -> ModelVersion:
    """Register a new version of a model."""
    with _VERSION_LOCK:
        if model_id not in _VERSION_STORE:
            _VERSION_STORE[model_id] = []
        # Check version format
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError("version must be semantic MAJOR.MINOR.PATCH")
        # Check if version already exists
        for v in _VERSION_STORE[model_id]:
            if v.version == version:
                raise ValueError(f"version {version} already exists for {model_id}")
        mv = ModelVersion(
            model_id=model_id,
            version=version,
            weights_digest=weights_digest,
            description=description,
            hyperparameters=hyperparameters,
            training_data_hash=training_data_hash,
            validation_metrics=validation_metrics,
            evidence=evidence,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
            parent_version=parent_version,
            changelog=changelog,
        )
        _VERSION_STORE[model_id].append(mv)
        return mv


def get_model_versions(model_id: str) -> list[ModelVersion]:
    """Get all versions of a model, sorted by semantic version."""
    with _VERSION_LOCK:
        versions = list(_VERSION_STORE.get(model_id, []))
        versions.sort(key=lambda v: tuple(map(int, v.version.split("."))))
        return versions


def get_latest_version(model_id: str) -> ModelVersion | None:
    """Get the latest version of a model."""
    versions = get_model_versions(model_id)
    return versions[-1] if versions else None


# --- Phase 11: Shadow Mode & Champion/Challenger ---

@dataclass
class ShadowModeConfig:
    """Configuration for shadow mode deployment."""
    model_id: str
    champion_id: str
    challenger_id: str
    traffic_fraction: float  # 0.0 to 1.0
    enabled: bool = True
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "champion_id": self.champion_id,
            "challenger_id": self.challenger_id,
            "traffic_fraction": self.traffic_fraction,
            "enabled": self.enabled,
            "started_at": self.started_at,
            "metrics": self.metrics,
        }


_SHADOW_CONFIGS: dict[str, ShadowModeConfig] = {}
_SHADOW_LOCK = threading.Lock()


def set_shadow_mode(config: ShadowModeConfig) -> ShadowModeConfig:
    """Enable shadow mode for a model."""
    with _SHADOW_LOCK:
        if config.model_id not in REGISTRY:
            raise KeyError(f"unknown model_id: {config.model_id}")
        if config.champion_id not in REGISTRY:
            raise KeyError(f"unknown champion_id: {config.champion_id}")
        if config.challenger_id not in REGISTRY:
            raise KeyError(f"unknown challenger_id: {config.challenger_id}")
        if not 0.0 <= config.traffic_fraction <= 1.0:
            raise ValueError("traffic_fraction must be between 0.0 and 1.0")
        config.model_id = config.model_id
        _SHADOW_CONFIGS[config.model_id] = config
        REGISTRY[config.model_id]["shadow_mode"] = True
        REGISTRY[config.model_id]["challenger_id"] = config.challenger_id
        return config


def get_shadow_mode(model_id: str) -> ShadowModeConfig | None:
    """Get shadow mode configuration."""
    with _SHADOW_LOCK:
        return _SHADOW_CONFIGS.get(model_id)


def disable_shadow_mode(model_id: str) -> bool:
    """Disable shadow mode."""
    with _SHADOW_LOCK:
        if model_id in _SHADOW_CONFIGS:
            del _SHADOW_CONFIGS[model_id]
            if model_id in REGISTRY:
                REGISTRY[model_id]["shadow_mode"] = False
                REGISTRY[model_id]["challenger_id"] = None
            return True
        return False


def evaluate_shadow_mode(model_id: str, input_data: dict, champion_result: dict, challenger_result: dict) -> dict:
    """Evaluate champion vs challenger on a single input."""
    config = get_shadow_mode(model_id)
    if not config or not config.enabled:
        return {"shadow_mode": False}

    # Compare results
    comparison = {
        "model_id": model_id,
        "champion_id": config.champion_id,
        "challenger_id": config.challenger_id,
        "champion_risk": champion_result.get("risk"),
        "challenger_risk": challenger_result.get("risk"),
        "risk_diff": (challenger_result.get("risk", 0) - champion_result.get("risk", 0))
        if champion_result.get("risk") is not None and challenger_result.get("risk") is not None
        else None,
        "champion_uncertainty": champion_result.get("uncertainty"),
        "challenger_uncertainty": challenger_result.get("uncertainty"),
        "agreement": champion_result.get("risk") is not None and challenger_result.get("risk") is not None
        and abs(champion_result["risk"] - challenger_result["risk"]) < 0.05,
    }

    # Update metrics
    with _SHADOW_LOCK:
        config.metrics.setdefault("total", 0)
        config.metrics["total"] += 1
        if comparison["agreement"]:
            config.metrics.setdefault("agreements", 0)
            config.metrics["agreements"] += 1
        else:
            config.metrics.setdefault("disagreements", 0)
            config.metrics["disagreements"] += 1

    return {
        "shadow_mode": True,
        "comparison": comparison,
        "metrics": config.metrics,
    }


# --- Phase 11: Model Drift Monitoring ---

@dataclass(frozen=True)
class DriftMetrics:
    """Model drift metrics."""
    model_id: str
    timestamp: str
    population_drift: float  # KL divergence from training distribution
    concept_drift: float  # Change in prediction distribution
    feature_drift: dict[str, float]  # Per-feature drift scores
    data_quality: float  # Input data quality score
    prediction_volume: int  # Number of predictions in window
    threshold_breached: bool = False

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "timestamp": self.timestamp,
            "population_drift": self.population_drift,
            "concept_drift": self.concept_drift,
            "feature_drift": self.feature_drift,
            "data_quality": self.data_quality,
            "prediction_volume": self.prediction_volume,
            "threshold_breached": self.threshold_breached,
        }


DRIFT_THRESHOLDS = {
    "population_drift": 0.1,
    "concept_drift": 0.05,
    "data_quality": 0.5,
}


def record_drift_metrics(model_id: str, metrics: DriftMetrics) -> DriftMetrics:
    """Record drift metrics for a model."""
    with _DRIFT_LOCK:
        DRIFT_HISTORY.setdefault(model_id, []).append(metrics)
        # Keep last 1000 entries
        if len(DRIFT_HISTORY[model_id]) > 1000:
            DRIFT_HISTORY[model_id] = DRIFT_HISTORY[model_id][-1000:]
        # Check thresholds
        breached = (
            metrics.population_drift > DRIFT_THRESHOLDS["population_drift"]
            or metrics.concept_drift > DRIFT_THRESHOLDS["concept_drift"]
            or metrics.data_quality < DRIFT_THRESHOLDS["data_quality"]
        )
        if breached:
            # Could trigger alert here
            pass
    return metrics


def get_drift_history(model_id: str, limit: int = 100) -> list[DriftMetrics]:
    """Get drift history for a model."""
    with _DRIFT_LOCK:
        return DRIFT_HISTORY.get(model_id, [])[-limit:]


def get_drift_summary(model_id: str) -> dict:
    """Get drift summary for a model."""
    with _DRIFT_LOCK:
        history = DRIFT_HISTORY.get(model_id, [])
        if not history:
            return {"model_id": model_id, "status": "no_data"}
        latest = history[-1]
        avg_pop = sum(h.population_drift for h in history) / len(history)
        avg_concept = sum(h.concept_drift for h in history) / len(history)
        avg_quality = sum(h.data_quality for h in history) / len(history)
        return {
            "model_id": model_id,
            "latest": latest.to_dict(),
            "averages": {
                "population_drift": avg_pop,
                "concept_drift": avg_concept,
                "data_quality": avg_quality,
            },
            "thresholds": DRIFT_THRESHOLDS,
            "alert": latest.threshold_breached,
            "entries": len(history),
        }


# --- Phase 11: Calibration Monitoring ---

@dataclass(frozen=True)
class CalibrationMetrics:
    """Calibration monitoring metrics."""
    model_id: str
    timestamp: str
    brier_score: float
    calibration_slope: float
    calibration_intercept: float
    ece: float  # Expected Calibration Error
    mce: float  # Maximum Calibration Error
    bin_counts: list[int]
    bin_accuracies: list[float]
    bin_confidences: list[float]

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "timestamp": self.timestamp,
            "brier_score": self.brier_score,
            "calibration_slope": self.calibration_slope,
            "calibration_intercept": self.calibration_intercept,
            "ece": self.ece,
            "mce": self.mce,
            "bin_counts": self.bin_counts,
            "bin_accuracies": self.bin_accuracies,
            "bin_confidences": self.bin_confidences,
        }


_CALIBRATION_HISTORY: dict[str, list[CalibrationMetrics]] = {}
_CALIBRATION_LOCK = threading.Lock()


def record_calibration_metrics(model_id: str, metrics: CalibrationMetrics) -> CalibrationMetrics:
    """Record calibration metrics for a model."""
    with _CALIBRATION_LOCK:
        _CALIBRATION_HISTORY.setdefault(model_id, []).append(metrics)
        if len(_CALIBRATION_HISTORY[model_id]) > 1000:
            _CALIBRATION_HISTORY[model_id] = _CALIBRATION_HISTORY[model_id][-1000:]
    return metrics


def get_calibration_history(model_id: str, limit: int = 100) -> list[CalibrationMetrics]:
    """Get calibration history for a model."""
    with _CALIBRATION_LOCK:
        return _CALIBRATION_HISTORY.get(model_id, [])[-limit:]


def get_calibration_summary(model_id: str) -> dict:
    """Get calibration summary for a model."""
    with _CALIBRATION_LOCK:
        history = _CALIBRATION_HISTORY.get(model_id, [])
        if not history:
            return {"model_id": model_id, "status": "no_data"}
        latest = history[-1]
        return {
            "model_id": model_id,
            "latest": latest.to_dict(),
            "trend": {
                "brier_score": [h.brier_score for h in history[-10:]],
                "ece": [h.ece for h in history[-10:]],
            },
            "entries": len(history),
        }


# --- Phase 11: Model Regression Testing ---

@dataclass(frozen=True)
class RegressionTestResult:
    """Result of a model regression test."""
    test_id: str
    model_id: str
    baseline_version: str
    candidate_version: str
    dataset_id: str
    passed: bool
    metrics: dict  # metric -> {baseline: val, candidate: val, diff: val, threshold: val}
    regressions: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "model_id": self.model_id,
            "baseline_version": self.baseline_version,
            "candidate_version": self.candidate_version,
            "dataset_id": self.dataset_id,
            "passed": self.passed,
            "metrics": self.metrics,
            "regressions": self.regressions,
            "timestamp": self.timestamp,
        }


_REGRESSION_TESTS: dict[str, list[RegressionTestResult]] = {}
_REGRESSION_LOCK = threading.Lock()


def run_regression_test(
    model_id: str,
    baseline_version: str,
    candidate_version: str,
    dataset_id: str,
    test_fn: callable,
    thresholds: dict[str, float] | None = None,
) -> RegressionTestResult:
    """Run a regression test comparing two model versions."""
    thresholds = thresholds or {
        "brier_score": 0.01,
        "ece": 0.02,
        "auc": -0.01,  # negative means AUC drop is regression
    }
    # Run test function on both versions
    baseline_result = test_fn(baseline_version)
    candidate_result = test_fn(candidate_version)

    metrics = {}
    regressions = []
    for metric, baseline_val in baseline_result.items():
        candidate_val = candidate_result.get(metric)
        if candidate_val is None:
            continue
        diff = candidate_val - baseline_val
        threshold = thresholds.get(metric, 0.0)
        is_regression = False
        if metric in ("brier_score", "ece"):  # lower is better
            is_regression = diff > threshold
        elif metric in ("auc", "calibration_slope"):  # higher is better
            is_regression = diff < -threshold
        metrics[metric] = {
            "baseline": baseline_val,
            "candidate": candidate_val,
            "diff": diff,
            "threshold": threshold,
            "regression": is_regression,
        }
        if is_regression:
            regressions.append(f"{metric}: {diff:.4f} exceeds threshold {threshold}")

    result = RegressionTestResult(
        test_id=f"reg-{uuid.uuid4().hex[:12]}",
        model_id=model_id,
        baseline_version=baseline_version,
        candidate_version=candidate_version,
        dataset_id=dataset_id,
        passed=len(regressions) == 0,
        metrics=metrics,
        regressions=regressions,
    )
    with _REGRESSION_LOCK:
        _REGRESSION_TESTS.setdefault(model_id, []).append(result)
    return result


def get_regression_history(model_id: str, limit: int = 100) -> list[RegressionTestResult]:
    """Get regression test history for a model."""
    with _REGRESSION_LOCK:
        return _REGRESSION_TESTS.get(model_id, [])[-limit:]


# --- Phase 11: Lineage Tracking ---

def add_data_lineage(model_id: str, dataset_id: str, dataset_hash: str, description: str = "") -> None:
    """Record model-to-data lineage."""
    with _LINEAGE_LOCK:
        MODEL_LINEAGE.setdefault(model_id, {"data": [], "experiments": [], "decisions": []})
        MODEL_LINEAGE[model_id]["data"].append({
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "description": description,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })


def add_experiment_lineage(model_id: str, experiment_id: str, run_id: str, description: str = "") -> None:
    """Record model-to-experiment lineage."""
    with _LINEAGE_LOCK:
        MODEL_LINEAGE.setdefault(model_id, {"data": [], "experiments": [], "decisions": []})
        MODEL_LINEAGE[model_id]["experiments"].append({
            "experiment_id": experiment_id,
            "run_id": run_id,
            "description": description,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })


def add_decision_lineage(model_id: str, decision_id: str, outcome: str = "") -> None:
    """Record model-to-decision lineage."""
    with _LINEAGE_LOCK:
        MODEL_LINEAGE.setdefault(model_id, {"data": [], "experiments": [], "decisions": []})
        MODEL_LINEAGE[model_id]["decisions"].append({
            "decision_id": decision_id,
            "outcome": outcome,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })


def get_model_lineage(model_id: str) -> dict:
    """Get complete lineage for a model."""
    with _LINEAGE_LOCK:
        return MODEL_LINEAGE.get(model_id, {"data": [], "experiments": [], "decisions": []})


# --- Phase 11: Compatibility Checks ---

def check_model_compatibility(model_id: str, target_schema_version: str) -> dict:
    """Check if model is compatible with target schema version."""
    entry = get_model(model_id)
    current_schema = entry.get("schema_version", "unknown")
    compatible = current_schema == target_schema_version
    return {
        "model_id": model_id,
        "current_schema": current_schema,
        "target_schema": target_schema_version,
        "compatible": compatible,
        "note": f"Schema {'matches' if compatible else 'mismatch'}: {current_schema} vs {target_schema_version}",
    }


# --- Promotion / Rollback (existing, enhanced) ---

def promote(model_id: str = DEFAULT_MODEL_ID, target: str = "candidate",
            evidence: dict | None = None, approver: str = "",
            notes: str = "") -> dict:
    """Move a model one lifecycle step forward under evidence rules."""
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
    with _AUDIT_LOCK:
        AUDIT_LOG.append({"model_id": model_id, "from": previous, "to": target,
                          "approver": approver.strip() or None, "notes": notes.strip(),
                          "timestamp": datetime.now(timezone.utc).isoformat()})
    return {"model_id": model_id, "from": previous, "to": target}


def rollback(model_id: str = DEFAULT_MODEL_ID, reason: str = "") -> dict:
    """Return a model to its previous recorded promotion status."""
    if model_id not in REGISTRY:
        raise KeyError(f"unknown model_id: {model_id!r}")
    if not reason.strip():
        raise ValueError("rollback requires a reason")
    entry = REGISTRY[model_id]
    current = entry.get("status", "research")
    previous = None
    with _AUDIT_LOCK:
        for record in reversed(AUDIT_LOG):
            if record["model_id"] != model_id or record["to"] != current:
                continue
            if str(record.get("notes") or "").startswith("ROLLBACK:"):
                continue
            previous = record["from"]
            break
    if previous is None:
        raise ValueError(f"no recorded previous status to roll back from {current!r}")
    entry["status"] = previous
    entry["deployment_gate"] = "closed"
    with _AUDIT_LOCK:
        AUDIT_LOG.append({"model_id": model_id, "from": current, "to": previous,
                          "approver": None, "notes": f"ROLLBACK: {reason.strip()}",
                          "timestamp": datetime.now(timezone.utc).isoformat()})
    return {"model_id": model_id, "from": current, "to": previous}


def get_audit_log(model_id: str | None = None) -> list[dict]:
    """Copy of the promotion/rollback audit trail, optionally filtered."""
    with _AUDIT_LOCK:
        return [dict(r) for r in AUDIT_LOG if model_id is None or r["model_id"] == model_id]


# Initialize default version
register_model_version(
    model_id="cardiac-strain-v1",
    version="1.0.0",
    weights_digest="cb5ee2d9a1a04c93dc4a4d13009cfcdbd19a823b036c3d3ab50ce96ff49ea1d3",
    description="Initial cardiac strain risk model",
    hyperparameters={"platt_scaling": True, "baseline_window": 7},
    training_data_hash="synthetic-14d-v1-hash",
    validation_metrics={"auc": 0.72, "brier": 0.18, "calibration_slope": 0.95},
    evidence={"events": 5, "non_events": 54, "calibrated": False, "clinical_review": False, "synthetic": True},
    status="research",
    created_by="system",
)