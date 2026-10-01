"""Track-A explainability (Phase 7): permutation importance + coefficients.

Method (documented, reproducible):
  * Permutation importance (model-agnostic: works for logreg and forest
    alike) with ROC-AUC drop, 10 repeats, seed 7, computed on the HELD-OUT
    TEST split. Test is used for explanation ONLY — importance scores tune
    nothing and change no weights, so the Phase 5 metrics stay valid.
  * Logistic-regression coefficients (standardized space) as a second,
    directional view for the two logreg models (CAD, RCA).
  * No SHAP dependency: permutation importance is exact, seed-fixed, and
    needs nothing beyond sklearn.

Artifact: ``data/cardiovascular/evaluation/explainability.json`` with the
top-15 features per target (mean AUC drop +/- std) and coefficients
where applicable.

One command: ``python -m rift.health.cardiovascular.explain``
"""
from __future__ import annotations

import json

from . import evaluate, preprocessing, registry

N_REPEATS = 10
EXPLAIN_SEED = 7
TOP_K = 15


def feature_names() -> list:
    """Model-input column order (59 standardized features)."""
    return list(preprocessing.feature_names())


def permutation_importance(target: str, n_repeats: int = N_REPEATS,
                           seed: int = EXPLAIN_SEED) -> list:
    """AUC-drop importance on held-out test; sorted descending."""
    from sklearn.inspection import permutation_importance as _pi
    estimator, record = registry.load_model(registry.MODEL_IDS[target])
    frames = evaluate._load_split_frames()
    scaler = registry.load_scaler(record["model_id"])
    x_test, y_test, _ = evaluate._split_xy(frames, ("test",), target, scaler)
    result = _pi(estimator, x_test, y_test, n_repeats=n_repeats,
                 random_state=seed, scoring="roc_auc")
    names = feature_names()
    ranked = sorted(
        ({"feature": names[i],
          "auc_drop_mean": float(result.importances_mean[i]),
          "auc_drop_std": float(result.importances_std[i])}
         for i in range(len(names))),
        key=lambda row: row["auc_drop_mean"], reverse=True)
    return ranked


def logistic_coefficients(model_id: str) -> list | None:
    """Directional coefficients for logreg models; None for forests."""
    estimator, record = registry.load_model(model_id)
    if record["algorithm"] != "logistic_regression":
        return None
    names = feature_names()
    coefs = [float(v) for v in estimator.coef_[0]]
    return sorted(
        ({"feature": name, "coefficient": coef}
         for name, coef in zip(names, coefs)),
        key=lambda row: abs(row["coefficient"]), reverse=True)


def explain_all() -> dict:
    """Top-15 permutation features per target + logreg coefficients."""
    report = {
        "protocol": ("permutation importance, ROC-AUC drop, 10 repeats, seed 7, "
                      "held-out test split, explanation-only; logreg coefficients "
                      "in standardized space"),
        "targets": {},
    }
    for target in ("cad", "lad", "lcx", "rca"):
        model_id = registry.MODEL_IDS[target]
        report["targets"][target] = {
            "model_id": model_id,
            "permutation_top15": permutation_importance(target)[:TOP_K],
            "logistic_coefficients": logistic_coefficients(model_id),
        }
    out = evaluate.EVAL_DIR / "explainability.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def print_report(report: dict) -> None:
    for target in ("cad", "lad", "lcx", "rca"):
        print("%s [%s]" % (target.upper(), report["targets"][target]["model_id"]))
        for row in report["targets"][target]["permutation_top15"][:10]:
            print("  %-22s auc-drop %.4f ± %.4f" % (
                row["feature"], row["auc_drop_mean"], row["auc_drop_std"]))


if __name__ == "__main__":
    print_report(explain_all())
