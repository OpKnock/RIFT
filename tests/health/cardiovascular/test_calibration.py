"""Phase 6 tests: ECE/Brier correctness, calibrator honesty, persistence."""
from __future__ import annotations

import json

from rift.health.cardiovascular import calibration, evaluate, registry


def test_ece_perfect_model_is_zero():
    ece = calibration.expected_calibration_error([1, 1, 0, 0], [1.0, 1.0, 0.0, 0.0])
    assert ece == 0.0


def test_ece_hand_computed():
    # Two bins of width 0.5: bin0 probs {0.1,0.2} labels {0,0} -> acc 0, conf .15;
    # bin1 probs {0.8,0.9} labels {1,0} -> acc .5, conf .85. ECE=.5*.15+.5*.35=.25
    ece = calibration.expected_calibration_error(
        [0, 0, 1, 0], [0.1, 0.2, 0.8, 0.9], n_bins=2)
    assert abs(ece - 0.25) < 1e-9


def test_brier_hand_computed():
    assert calibration.brier_score([1, 0], [1.0, 0.0]) == 0.0
    assert calibration.brier_score([1, 0], [0.5, 0.5]) == 0.25


def test_reliability_bins_cover_all_rows():
    curve = calibration.reliability_curve([1, 1, 0, 0], [0.9, 0.4, 0.6, 0.1])
    assert len(curve) == 10
    assert sum(b["count"] for b in curve) == 4


def test_oof_never_touches_test():
    y_oof, _ = calibration.out_of_fold_scores("cad")
    assert len(y_oof) == 183 + 60  # train+val only, test (60) excluded


def test_calibrate_all_persists_and_updates_registry():
    summary = calibration.calibrate_all()
    assert set(summary["models"]) == {"cad", "lad", "lcx", "rca"}
    for target in ("cad", "lad", "lcx", "rca"):
        entry = summary["models"][target]
        assert entry["method"] in ("sigmoid", "isotonic")
        model_dir = registry.REGISTRY_DIR / entry["model_id"]
        assert (model_dir / "calibrator.pkl").exists()
        record = json.loads((model_dir / "record.json").read_text())
        assert record["calibration"]["method"] == entry["method"]
        for key in ("oof_ece_before", "test_brier_after"):
            assert isinstance(record["calibration"][key], float)
    on_disk = json.loads((evaluate.EVAL_DIR / "calibration.json").read_text())
    assert set(on_disk["models"]) == {"cad", "lad", "lcx", "rca"}


def test_calibrated_predictions_bounded_and_sized():
    import pandas as pd
    frames = evaluate._load_split_frames()
    sample = frames["test"].head(5)
    for target in ("cad", "lad", "lcx", "rca"):
        probs = calibration.predict_calibrated(registry.MODEL_IDS[target], sample)
        assert len(probs) == 5
        assert all(0.0 <= float(p) <= 1.0 for p in probs)
