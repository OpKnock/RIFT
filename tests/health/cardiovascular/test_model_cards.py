"""Phase 13 tests: cards honest, structured, pinned to measured numbers."""
from __future__ import annotations

import json

from rift.health.cardiovascular import evaluate, model_cards


def _artifacts():
    report = json.loads((evaluate.EVAL_DIR / "report.json").read_text())
    calibration = json.loads((evaluate.EVAL_DIR / "calibration.json").read_text())
    explain = json.loads((evaluate.EVAL_DIR / "explainability.json").read_text())
    return report, calibration, explain


def test_cards_cover_all_models_with_required_fields():
    cards = model_cards.build_cards(*_artifacts())
    assert [c["model_id"] for c in cards] == [
        "cad-v1", "lad-stenosis-v1", "lcx-stenosis-v1", "rca-stenosis-v1"]
    for card in cards:
        for field in ("task", "intended_use", "training", "algorithm",
                      "hyperparameters", "test_metrics", "confusion",
                      "cv_roc_auc", "calibration", "top_drivers", "limitations"):
            assert field in card, (card["model_id"], field)
        assert len(card["top_drivers"]) == 5
        assert "not a medical device" in card["limitations"].lower()


def test_weak_models_flagged_in_plain_language():
    cards = {c["target"]: c for c in model_cards.build_cards(*_artifacts())}
    assert "NOT decision-grade" in cards["rca"]["limitations"]
    assert "does NOT rule out" in cards["lcx"]["limitations"]
    assert cards["rca"]["test_metrics"]["roc_auc"] < 0.65
    assert cards["lcx"]["test_metrics"]["recall"] < 0.5


def test_cards_match_committed_numbers():
    report, _, _ = _artifacts()
    cards = {c["target"]: c for c in model_cards.build_cards(*_artifacts())}
    for target in ("cad", "lad", "lcx", "rca"):
        assert cards[target]["test_metrics"] == {
            k: report["targets"][target]["test"][k]
            for k in ("accuracy", "precision", "recall", "f1", "roc_auc")}


def test_write_cards_deterministic_and_mirrored():
    first = model_cards.write_cards()
    second = model_cards.write_cards()
    assert first == second
    site = evaluate.DATA_DIR / "site" / "model_cards.json"
    mirror = (evaluate.DATA_DIR / ".." / ".." / "stitch-ui" / "live" / "cardio"
              / "model_cards.json").resolve()
    assert json.loads(site.read_text()) == first
    assert mirror.read_bytes() == site.read_bytes()
