"""Prediction entry point (Phase 4): registry model + stored scaler.

Every call runs the leakage firewall on the input frame first, so even
a hand-built feature frame with a forbidden column fails closed here.
Calibration (Phase 6) and explanations (Phase 7) attach later; this
module returns raw model probabilities with provenance.
"""
from __future__ import annotations

from . import preprocessing, registry, schemas
from .leakage import assert_no_leakage


def predict_proba(model_id: str, raw_frame):
    """Probabilities for the positive class, plus model provenance."""
    estimator, record = registry.load_model(model_id)
    assert_no_leakage(raw_frame)
    scaler = registry.load_scaler(model_id)
    numeric = preprocessing.encoded_frame(raw_frame)
    scaled = preprocessing.apply_scaler(numeric, scaler)
    if list(scaled.columns) != record["features"]:
        raise ValueError("feature order mismatch for %r" % model_id)
    probabilities = [float(p) for p in estimator.predict_proba(scaled.to_numpy())[:, 1]]
    return {
        "model_id": model_id,
        "target": record["target"],
        "algorithm": record["algorithm"],
        "probabilities": probabilities,
        "weights_hash": record["weights_hash"],
        "feature_schema_version": record["feature_schema_version"],
    }
