"""Phase 4 tests: registry completeness, hash integrity, reproducibility."""
import hashlib
import json
import pickle

import pytest

from rift.health.cardiovascular import leakage, registry, schemas


def test_all_four_models_registered():
    records = {r["model_id"]: r for r in registry.list_models()}
    assert set(records) == {"cad-v1", "lad-stenosis-v1", "lcx-stenosis-v1", "rca-stenosis-v1"}
    for target, model_id in registry.MODEL_IDS.items():
        assert records[model_id]["target"] == target


def test_records_complete_and_versions_pinned():
    for record in registry.list_models():
        for field in registry.REQUIRED_RECORD_FIELDS:
            assert field in record, (record["model_id"], field)
        assert record["feature_schema_version"] == schemas.FEATURE_SCHEMA_VERSION
        assert record["preprocessing_version"] == schemas.PREPROCESSING_VERSION
        assert record["split_seed"] == 7
        cal = record["calibration"]  # Phase 6 fills this
        assert cal["method"] in ("sigmoid", "isotonic")
        for key in ("oof_ece_before", "oof_ece_after", "oof_brier_before",
                    "oof_brier_after", "test_ece_before", "test_ece_after",
                    "test_brier_before", "test_brier_after"):
            assert isinstance(cal[key], float)
        leakage.assert_no_leakage(record["features"])
        assert len(record["features"]) == 59


def test_weights_hash_matches_artifact():
    for model_id in registry.MODEL_IDS.values():
        raw = (registry.REGISTRY_DIR / model_id / "model.pkl").read_bytes()
        record = json.loads((registry.REGISTRY_DIR / model_id / "record.json").read_text())
        assert record["weights_hash"] == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_tampered_weights_rejected():
    import copy
    model_id = "cad-v1"
    record = json.loads((registry.REGISTRY_DIR / model_id / "record.json").read_text())
    bad = copy.deepcopy(record)
    bad["weights_hash"] = "sha256:" + "0" * 64
    (registry.REGISTRY_DIR / model_id / "record.json").write_text(json.dumps(bad))
    try:
        with pytest.raises(ValueError, match="weights hash mismatch"):
            registry.load_model(model_id)
    finally:
        (registry.REGISTRY_DIR / model_id / "record.json").write_text(json.dumps(record))


def test_retraining_is_bitwise_reproducible():
    # Refit CAD winner config manually and compare weights bytes.
    from sklearn.linear_model import LogisticRegression
    from rift.health.cardiovascular import dataset, preprocessing, targets
    import pandas as pd
    _, record = registry.load_model("cad-v1")
    assert record["algorithm"] == "logistic_regression"
    frames = {p: pd.read_csv(
        dataset.DATA_DIR / "processed" / ("%s.csv" % p)) for p in ("train", "val")}
    train_raw = frames["train"][list(schemas.PREDICTOR_COLUMNS)]
    val_raw = frames["val"][list(schemas.PREDICTOR_COLUMNS)]
    import numpy as np
    y = np.concatenate([targets.read_labels(frames["train"], "cad").to_numpy(),
                        targets.read_labels(frames["val"], "cad").to_numpy()])
    refit_raw = pd.concat([train_raw, val_raw], ignore_index=True)
    x_refit, _ = preprocessing.prepare_matrices(refit_raw)
    params = record["hyperparameters"]
    fresh = LogisticRegression(C=params["C"], solver="lbfgs", max_iter=2000, random_state=7)
    fresh.fit(x_refit.to_numpy(), y)
    assert (pickle.dumps(fresh, protocol=4) ==
            (registry.REGISTRY_DIR / "cad-v1" / "model.pkl").read_bytes())
