"""Phase 18 tests: safety verdicts refuse, flag, and list OOD fields."""
from __future__ import annotations

import pytest

from rift.health.cardiovascular import registry, safety, schemas


def _predictors():
    import pandas as pd
    from rift.health.cardiovascular import evaluate
    frame = pd.read_csv(evaluate.DATA_DIR / "processed" / "test.csv")
    row = frame.iloc[0]
    return {c: (row[c].item() if hasattr(row[c], "item") else row[c])
            for c in schemas.PREDICTOR_COLUMNS}


def test_in_distribution_cad_prediction_shows():
    verdict = safety.assess_prediction("cad-v1", _predictors(), 0.83)
    assert verdict["safe_to_show"] is True
    assert verdict["out_of_distribution_fields"] == []
    assert "not a medical device" in verdict["disclaimer"].lower()


def test_rca_always_carries_not_decision_grade():
    verdict = safety.assess_prediction("rca-stenosis-v1", _predictors(), 0.4)
    assert verdict["safe_to_show"] is True
    assert any("NOT decision-grade" in w for w in verdict["warnings"])


def test_negative_lcx_carries_does_not_rule_out():
    low = safety.assess_prediction("lcx-stenosis-v1", _predictors(), 0.2)
    assert any("does NOT rule out" in w for w in low["warnings"])
    high = safety.assess_prediction("lcx-stenosis-v1", _predictors(), 0.8)
    assert not any("does NOT rule out" in w for w in high["warnings"])


def test_out_of_range_age_flagged_by_name():
    predictors = _predictors()
    predictors["Age"] = 250
    verdict = safety.assess_prediction("cad-v1", predictors, 0.5)
    assert verdict["safe_to_show"] is True  # flagged, not refused
    assert "Age" in verdict["out_of_distribution_fields"]
    assert any("Out-of-distribution" in w for w in verdict["warnings"])


def test_unseen_category_flagged():
    predictors = _predictors()
    predictors["Sex"] = "alien"
    verdict = safety.assess_prediction("cad-v1", predictors, 0.5)
    assert "Sex" in verdict["out_of_distribution_fields"]


def test_missing_calibration_refuses(monkeypatch):
    _, record = registry.load_model("cad-v1")
    record = dict(record, calibration=None)
    monkeypatch.setattr(registry, "load_model", lambda model_id: (None, record))
    verdict = safety.assess_prediction("cad-v1", _predictors(), 0.5)
    assert verdict["safe_to_show"] is False
    assert any("no recorded calibration" in w for w in verdict["warnings"])


def test_nonfinite_probability_refuses():
    for bad in (float("nan"), -0.1, 1.1):
        verdict = safety.assess_prediction("cad-v1", _predictors(), bad)
        assert verdict["safe_to_show"] is False
