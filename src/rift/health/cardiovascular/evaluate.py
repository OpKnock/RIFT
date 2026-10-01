"""Track-A evaluation (Phase 5): held-out test metrics + CV stability.

Validation protocol (documented, reproducible):
  raw 303 rows
   -> stratified split, seed 7 (train 183 / val 60 / test 60)
   -> algorithm selection on VAL by ROC-AUC (train.py; test untouched)
   -> winner refit on train+val
   -> THIS module scores the HELD-OUT TEST once per model
   -> 5-fold stratified CV on TRAIN reports stability (mean +/- std)

Metrics per target: accuracy, precision, recall, F1, ROC-AUC, plus
confusion counts. Report written to
``data/cardiovascular/evaluation/report.json`` with protocol, hashes,
and per-target numbers.

One command: ``python -m rift.health.cardiovascular.evaluate``
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import dataset, preprocessing, registry, schemas, targets
from .leakage import columns_for_target

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data" / "cardiovascular"
EVAL_DIR = DATA_DIR / "evaluation"

EVAL_SEED = 7
CV_FOLDS = 5


def _load_split_frames():
    import pandas as pd
    return {part: pd.read_csv(DATA_DIR / "processed" / ("%s.csv" % part))
            for part in ("train", "val", "test")}


def _split_xy(frames, parts: tuple, target: str, scaler: dict | None = None):
    import pandas as pd
    import numpy as np
    raw = pd.concat([frames[p][list(schemas.PREDICTOR_COLUMNS)] for p in parts],
                    ignore_index=True)
    columns_for_target(raw, target)
    y = np.concatenate([targets.read_labels(frames[p], target).to_numpy() for p in parts])
    if scaler is None:
        x_scaled, scaler = preprocessing.prepare_matrices(raw)
    else:
        x_scaled = preprocessing.apply_scaler(preprocessing.encoded_frame(raw), scaler)
    return x_scaled.to_numpy(), y, scaler


def binary_metrics(y_true, scores, threshold: float = 0.5) -> dict:
    """Accuracy/precision/recall/F1/ROC-AUC from first principles + sklearn AUC."""
    import numpy as np
    from sklearn.metrics import roc_auc_score
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    pred = (scores >= threshold).astype(int)
    tp = int(((pred == 1) & (y_true == 1)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    total = len(y_true)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "n": int(total),
        "threshold": float(threshold),
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": (2 * precision * recall / (precision + recall)
               if (precision + recall) else 0.0),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def evaluate_model(model_id: str) -> dict:
    """Score a registered model on the HELD-OUT test split."""
    estimator, record = registry.load_model(model_id)
    scaler = registry.load_scaler(model_id)
    frames = _load_split_frames()
    x_test, y_test, _ = _split_xy(frames, ("test",), record["target"], scaler)
    scores = [float(p) for p in estimator.predict_proba(x_test)[:, 1]]
    metrics = binary_metrics(y_test, scores)
    metrics["model_id"] = model_id
    metrics["target"] = record["target"]
    return metrics


def cross_validate(target: str, folds: int = CV_FOLDS, seed: int = EVAL_SEED) -> dict:
    """5-fold stratified CV on TRAIN with the registered winner config.

    Rebuilds the exact winning estimator from the registry record, so the
    stability numbers describe the shipped configuration, not a substitute.
    """
    import numpy as np
    from sklearn.model_selection import StratifiedKFold
    estimator, record = registry.load_model(registry.MODEL_IDS[target])
    frames = _load_split_frames()
    x_train, y_train, _ = _split_xy(frames, ("train",), target)
    aucs, f1s = [], []
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train_idx, val_idx in splitter.split(x_train, y_train):
        clone = _rebuild(record)
        clone.fit(x_train[train_idx], y_train[train_idx])
        scores = clone.predict_proba(x_train[val_idx])[:, 1]
        fold = binary_metrics(y_train[val_idx], scores)
        aucs.append(fold["roc_auc"])
        f1s.append(fold["f1"])
    aucs, f1s = np.array(aucs), np.array(f1s)
    return {
        "target": target,
        "model_id": record["model_id"],
        "folds": int(folds),
        "seed": int(seed),
        "roc_auc_mean": float(aucs.mean()),
        "roc_auc_std": float(aucs.std(ddof=1)) if folds > 1 else 0.0,
        "f1_mean": float(f1s.mean()),
        "f1_std": float(f1s.std(ddof=1)) if folds > 1 else 0.0,
        "roc_auc_folds": [float(v) for v in aucs],
    }


def _rebuild(record: dict):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    params = record["hyperparameters"]
    if record["algorithm"] == "logistic_regression":
        return LogisticRegression(C=params["C"], solver="lbfgs", max_iter=2000, random_state=7)
    return RandomForestClassifier(
        n_estimators=params["n_estimators"], max_depth=params["max_depth"],
        min_samples_leaf=params["min_samples_leaf"], random_state=7, n_jobs=1)


def evaluate_all() -> dict:
    """Held-out test metrics + CV stability for all four models."""
    manifest = json.loads((DATA_DIR / "manifests/dataset_manifest.json").read_text())
    report = {
        "protocol": ("stratified split seed 7 (train 183/val 60/test 60); "
                     "algorithm selected on val ROC-AUC; winner refit on train+val; "
                     "held-out test scored once; 5-fold stratified CV on train for stability"),
        "dataset_hash": manifest["source_hash"],
        "feature_schema_version": manifest["feature_schema_version"],
        "targets": {},
    }
    for target in ("cad", "lad", "lcx", "rca"):
        model_id = registry.MODEL_IDS[target]
        report["targets"][target] = {
            "model_id": model_id,
            "test": evaluate_model(model_id),
            "cv_train": cross_validate(target),
        }
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_DIR / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def print_report(report: dict) -> None:
    for target in ("cad", "lad", "lcx", "rca"):
        entry = report["targets"][target]
        test, cv = entry["test"], entry["cv_train"]
        print("%s [%s]" % (target.upper(), entry["model_id"]))
        print("  test  n=%d  acc=%.3f  prec=%.3f  rec=%.3f  f1=%.3f  auc=%.3f  %s" % (
            test["n"], test["accuracy"], test["precision"], test["recall"],
            test["f1"], test["roc_auc"], test["confusion"]))
        print("  cv5   auc=%.3f±%.3f  f1=%.3f±%.3f" % (
            cv["roc_auc_mean"], cv["roc_auc_std"], cv["f1_mean"], cv["f1_std"]))


if __name__ == "__main__":
    print_report(evaluate_all())
