"""Phase 7 tests: importance structure, determinism, clinical plausibility."""
from __future__ import annotations

import json

from rift.health.cardiovascular import evaluate, explain, registry


def test_feature_names_match_model_input_order():
    assert len(explain.feature_names()) == 59
    assert explain.feature_names() == list(
        __import__("rift.health.cardiovascular.preprocessing", fromlist=["x"]
                   ).feature_names())


def test_permutation_ranking_shape_and_order():
    ranked = explain.permutation_importance("cad")
    assert len(ranked) == 59
    drops = [row["auc_drop_mean"] for row in ranked]
    assert drops == sorted(drops, reverse=True)
    assert ranked[0]["auc_drop_mean"] > 0.01  # top driver actually matters
    assert all(set(row) == {"feature", "auc_drop_mean", "auc_drop_std"}
               for row in ranked)


def test_permutation_deterministic():
    first = explain.permutation_importance("lad")
    second = explain.permutation_importance("lad")
    assert first == second


def test_clinical_anchor_typical_chest_pain_leads_cad_and_lad():
    cad_top5 = [row["feature"] for row in explain.permutation_importance("cad")[:5]]
    lad_top5 = [row["feature"] for row in explain.permutation_importance("lad")[:5]]
    assert "Typical Chest Pain" in cad_top5
    assert "Typical Chest Pain" in lad_top5


def test_logistic_coefficients_only_for_logreg():
    cad_coefs = explain.logistic_coefficients("cad-v1")
    assert cad_coefs is not None and len(cad_coefs) == 59
    assert abs(cad_coefs[0]["coefficient"]) >= abs(cad_coefs[-1]["coefficient"])
    assert explain.logistic_coefficients("lad-stenosis-v1") is None


def test_explain_all_report_roundtrip():
    report = explain.explain_all()
    assert set(report["targets"]) == {"cad", "lad", "lcx", "rca"}
    for target in ("cad", "lad", "lcx", "rca"):
        entry = report["targets"][target]
        assert len(entry["permutation_top15"]) == 15
    on_disk = json.loads((evaluate.EVAL_DIR / "explainability.json").read_text())
    assert on_disk == report
