"""Track-A model cards (Phase 13): one honest card per registered model.

Each card states intended use, training data, metrics, calibration, top
drivers, and LIMITATIONS generated from the measured numbers — weak
models get explicit do-not-use language. Cards are data, not prose:
built from registry records + committed evaluation JSONs, written to
``data/cardiovascular/site/model_cards.json`` and mirrored to the UI.

One command: ``python -m rift.health.cardiovascular.model_cards``
"""
from __future__ import annotations

import json

from . import evaluate, registry

TASKS = {
    "cad": "Predict coronary artery disease (Cath Normal vs CAD) from 55 clinical predictors.",
    "lad": "Predict left anterior descending artery stenosis (Normal vs Stenotic).",
    "lcx": "Predict left circumflex artery stenosis (Normal vs Stenotic).",
    "rca": "Predict right coronary artery stenosis (Normal vs Stenotic).",
}


def limitation_for(target: str, test: dict, cv: dict) -> str:
    """Rule-based limits from measured numbers; weak models flagged hard."""
    base = ("Single-center n=303 (Z-Alizadeh Sani Extension), no external "
            "validation; research prototype, not a medical device.")
    if target == "rca":
        return ("Near-chance discrimination (test AUC %.3f, CV %.3f±%.3f): "
                "RCA predictions are NOT decision-grade and are shown for "
                "completeness only. %s" % (
                    test["roc_auc"], cv["roc_auc_mean"], cv["roc_auc_std"], base))
    if target == "lcx":
        return ("Low recall (%.3f): the model finds a minority of LCX "
                "stenotics — a negative LCX prediction does NOT rule out "
                "LCX disease. %s" % (test["recall"], base))
    return "Held-out test n=60. %s" % base


def build_cards(report: dict, calibration: dict, explain: dict) -> list:
    """Assemble the four cards from records + evaluation artifacts."""
    cards = []
    for target in ("cad", "lad", "lcx", "rca"):
        model_id = registry.MODEL_IDS[target]
        _, record = registry.load_model(model_id)
        test = report["targets"][target]["test"]
        cv = report["targets"][target]["cv_train"]
        cal = calibration["models"][target]
        top = [row["feature"] for row in
               explain["targets"][target]["permutation_top15"][:5]]
        cards.append({
            "model_id": model_id,
            "target": target,
            "task": TASKS[target],
            "intended_use": ("Research decision-support prototype: rank and "
                             "explain stenosis risk for Track A demonstration. "
                             "Not for diagnosis, triage, or treatment."),
            "training": {
                "dataset": "UCI Z-Alizadeh Sani Extension (id 411)",
                "dataset_hash": report["dataset_hash"],
                "n_train": 183, "n_val": 60, "n_test": 60, "split_seed": 7,
                "n_predictors": 55,
                "feature_schema_version": report["feature_schema_version"],
                "leakage": ("LAD/LCX/RCA/Cath columns excluded per-target by "
                            "the firewall; scaler fit on train only."),
            },
            "algorithm": record["algorithm"],
            "hyperparameters": record["hyperparameters"],
            "test_metrics": {k: test[k] for k in
                             ("accuracy", "precision", "recall", "f1", "roc_auc")},
            "confusion": test["confusion"],
            "cv_roc_auc": {"mean": cv["roc_auc_mean"], "std": cv["roc_auc_std"]},
            "calibration": {"method": cal["method"],
                            "test_ece_before": cal["test"]["before"]["ece"],
                            "test_ece_after": cal["test"]["after"]["ece"]},
            "top_drivers": top,
            "limitations": limitation_for(target, test, cv),
        })
    return cards


def write_cards() -> list:
    """Build cards from committed artifacts; write site + UI mirror."""
    report = json.loads((evaluate.EVAL_DIR / "report.json").read_text())
    calibration = json.loads((evaluate.EVAL_DIR / "calibration.json").read_text())
    explain = json.loads((evaluate.EVAL_DIR / "explainability.json").read_text())
    cards = build_cards(report, calibration, explain)
    out = evaluate.DATA_DIR / "site" / "model_cards.json"
    out.write_text(json.dumps(cards, indent=1), encoding="utf-8")
    return cards


if __name__ == "__main__":
    cards = write_cards()
    print(json.dumps([{"model_id": c["model_id"],
                       "limitations": c["limitations"][:80] + "..."}
                      for c in cards], indent=1))
