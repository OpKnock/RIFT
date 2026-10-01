"""Phase 5 tests: metric correctness, held-out protocol, report integrity."""
from __future__ import annotations

import json

from rift.health.cardiovascular import evaluate, registry


def test_binary_metrics_hand_computed():
    # y=[1,1,0,0], scores=[0.9,0.4,0.6,0.1] @0.5 -> pred=[1,0,1,0]:
    # tp=1 tn=1 fp=1 fn=1 -> acc=0.5 prec=0.5 rec=0.5 f1=0.5
    m = evaluate.binary_metrics([1, 1, 0, 0], [0.9, 0.4, 0.6, 0.1])
    assert m["n"] == 4
    assert m["accuracy"] == 0.5
    assert m["precision"] == 0.5
    assert m["recall"] == 0.5
    assert m["f1"] == 0.5
    assert m["confusion"] == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}
    assert 0.0 <= m["roc_auc"] <= 1.0


def test_binary_metrics_perfect_separation():
    m = evaluate.binary_metrics([1, 1, 0, 0], [0.99, 0.8, 0.2, 0.01])
    assert m["accuracy"] == 1.0
    assert m["f1"] == 1.0
    assert m["roc_auc"] == 1.0


def test_test_split_size_is_60():
    frames = evaluate._load_split_frames()
    assert len(frames["test"]) == 60
    assert len(frames["train"]) == 183


def test_evaluate_model_uses_held_out_test():
    for target in ("cad", "lad", "lcx", "rca"):
        m = evaluate.evaluate_model(registry.MODEL_IDS[target])
        assert m["n"] == 60
        assert m["target"] == target
        for key in ("accuracy", "precision", "recall", "f1", "roc_auc"):
            assert 0.0 <= m[key] <= 1.0
        c = m["confusion"]
        assert c["tp"] + c["tn"] + c["fp"] + c["fn"] == 60


def test_cross_validate_shape_and_bounds():
    cv = evaluate.cross_validate("cad")
    assert cv["folds"] == 5
    assert len(cv["roc_auc_folds"]) == 5
    assert 0.0 <= cv["roc_auc_mean"] <= 1.0
    assert cv["roc_auc_std"] >= 0.0


def test_evaluate_all_report_roundtrip():
    report = evaluate.evaluate_all()
    assert "stratified split seed 7" in report["protocol"]
    assert set(report["targets"]) == {"cad", "lad", "lcx", "rca"}
    on_disk = json.loads((evaluate.EVAL_DIR / "report.json").read_text())
    assert on_disk == report


def test_evaluation_deterministic():
    first = {t: evaluate.evaluate_model(registry.MODEL_IDS[t])["roc_auc"]
             for t in ("cad", "lad", "lcx", "rca")}
    second = {t: evaluate.evaluate_model(registry.MODEL_IDS[t])["roc_auc"]
              for t in ("cad", "lad", "lcx", "rca")}
    assert first == second
