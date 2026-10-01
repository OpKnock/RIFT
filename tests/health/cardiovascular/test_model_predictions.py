"""Phase 4 tests: prediction entry point behavior."""
import pytest

from rift.health.cardiovascular import dataset, predict, registry, schemas
from rift.health.cardiovascular.leakage import TargetLeakageError


def _predictor_frame():
    df = dataset.load_raw_frame()
    return df[list(schemas.PREDICTOR_COLUMNS)].iloc[:10].copy()


def test_probabilities_valid_and_provenanced():
    for model_id in registry.MODEL_IDS.values():
        out = predict.predict_proba(model_id, _predictor_frame())
        assert len(out["probabilities"]) == 10
        assert all(0.0 <= p <= 1.0 for p in out["probabilities"])
        assert out["weights_hash"].startswith("sha256:")
        assert out["feature_schema_version"] == schemas.FEATURE_SCHEMA_VERSION


def test_predictions_deterministic_across_loads():
    first = predict.predict_proba("cad-v1", _predictor_frame())["probabilities"]
    second = predict.predict_proba("cad-v1", _predictor_frame())["probabilities"]
    assert first == second


def test_prediction_firewall_rejects_leaked_frame():
    frame = _predictor_frame()
    frame["Cath"] = 1
    with pytest.raises(TargetLeakageError):
        predict.predict_proba("cad-v1", frame)


def test_unknown_model_id_rejected():
    with pytest.raises((ValueError, FileNotFoundError, OSError)):
        predict.predict_proba("nope-v9", _predictor_frame())
