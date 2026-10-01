"""Model registry (Phase 4): versioned records + weight artifacts.

Each model id (``cad-v1``, ``lad-stenosis-v1``, ...) gets
``data/cardiovascular/registry/<model_id>/`` containing:

- ``model.pkl`` — pickled sklearn estimator (research artifact),
- ``record.json`` — dataset version, feature version, split seed,
  algorithm, hyperparameters, training timestamp, weights SHA-256,
  validation metrics, feature list, calibration status.

The feature list is firewall-checked at write time, so a registry
record can never bless a leaked model.
"""
from __future__ import annotations

import hashlib
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path

from . import schemas
from .leakage import assert_no_leakage

REPO_ROOT = Path(__file__).resolve().parents[4]
REGISTRY_DIR = REPO_ROOT / "data" / "cardiovascular" / "registry"

MODEL_IDS = {
    "cad": "cad-v1",
    "lad": "lad-stenosis-v1",
    "lcx": "lcx-stenosis-v1",
    "rca": "rca-stenosis-v1",
}

REQUIRED_RECORD_FIELDS = (
    "model_id", "target", "algorithm", "hyperparameters",
    "dataset_hash", "feature_schema_version", "preprocessing_version",
    "split_seed", "split_sizes", "trained_at_utc", "weights_hash",
    "validation_metrics", "features", "calibration",
)


def _weights_hash(model_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(model_bytes).hexdigest()


def save_model(model_id: str, target: str, algorithm: str,
               hyperparameters: dict, estimator, feature_names: list,
               dataset_hash: str, split_seed: int, split_sizes: dict,
               validation_metrics: dict, scaler: dict | None = None) -> dict:
    """Persist estimator + record; return the record dict."""
    if target not in schemas.TARGETS:
        raise ValueError("unknown cardiovascular target: %r" % target)
    assert_no_leakage(list(feature_names))
    model_bytes = pickle.dumps(estimator, protocol=4)
    record = {
        "model_id": model_id,
        "target": target,
        "algorithm": algorithm,
        "hyperparameters": dict(hyperparameters),
        "dataset_hash": dataset_hash,
        "feature_schema_version": schemas.FEATURE_SCHEMA_VERSION,
        "preprocessing_version": schemas.PREPROCESSING_VERSION,
        "split_seed": int(split_seed),
        "split_sizes": dict(split_sizes),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "weights_hash": _weights_hash(model_bytes),
        "validation_metrics": dict(validation_metrics),
        "features": list(feature_names),
        "calibration": None,  # filled by calibration.py (Phase 6)
    }
    model_dir = REGISTRY_DIR / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.pkl").write_bytes(model_bytes)
    if scaler is not None:
        (model_dir / "scaler.json").write_text(json.dumps(scaler, indent=1), encoding="utf-8")
    (model_dir / "record.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


def load_model(model_id: str):
    """Load (estimator, record); verifies weights hash on read."""
    model_dir = REGISTRY_DIR / model_id
    record = json.loads((model_dir / "record.json").read_text(encoding="utf-8"))
    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            raise ValueError("registry record %r missing field %r" % (model_id, field))
    model_bytes = (model_dir / "model.pkl").read_bytes()
    if _weights_hash(model_bytes) != record["weights_hash"]:
        raise ValueError("weights hash mismatch for %r: artifact changed since training" % model_id)
    assert_no_leakage(record["features"])
    return pickle.loads(model_bytes), record


def load_scaler(model_id: str) -> dict:
    """Load the train-fit scaler stored beside a registered model."""
    scaler_file = REGISTRY_DIR / model_id / "scaler.json"
    if not scaler_file.is_file():
        raise ValueError("no scaler stored for %r" % model_id)
    return json.loads(scaler_file.read_text(encoding="utf-8"))


def list_models() -> list:
    """All registry records on disk."""
    if not REGISTRY_DIR.exists():
        return []
    records = []
    for child in sorted(REGISTRY_DIR.iterdir()):
        record_file = child / "record.json"
        if record_file.is_file():
            records.append(json.loads(record_file.read_text(encoding="utf-8")))
    return records
