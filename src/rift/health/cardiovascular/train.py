"""Model training (Phase 4): baseline family per target, Val-selected.

For each of CAD/LAD/LCX/RCA, trains LogisticRegression (C grid) and
RandomForest (small grid) on the train split with the shared 59-feature
contract, selects by validation ROC-AUC (no test peeking: the test split
is never touched here; Phase 5 evaluates it), refits the winner on
train+val, and writes a registry record.

Determinism: fixed seed everywhere, single-threaded estimators, fixed
grids. Retraining the same data yields byte-identical weights
(asserted in tests).

One command: ``python -m rift.health.cardiovascular.train``
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import dataset, preprocessing, registry, schemas, targets
from .leakage import columns_for_target

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data" / "cardiovascular"

TRAIN_SEED = 7
LOGREG_C_GRID = (0.01, 0.1, 1.0, 10.0)
RF_GRID = (
    {"n_estimators": 100, "max_depth": None, "min_samples_leaf": 1},
    {"n_estimators": 100, "max_depth": 5, "min_samples_leaf": 1},
    {"n_estimators": 200, "max_depth": 5, "min_samples_leaf": 5},
)


def _load_split_frames():
    import pandas as pd
    frames = {}
    for part in ("train", "val", "test"):
        frames[part] = pd.read_csv(DATA_DIR / "processed" / ("%s.csv" % part))
    return frames


def _roc_auc(y_true, scores) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y_true, scores))


def _candidates():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    for c in LOGREG_C_GRID:
        yield ("logistic_regression", {"C": c, "solver": "lbfgs", "max_iter": 2000},
               lambda params: LogisticRegression(C=params["C"], solver="lbfgs",
                                                 max_iter=2000, random_state=TRAIN_SEED))
    for params in RF_GRID:
        yield ("random_forest", dict(params),
               lambda params: RandomForestClassifier(
                   n_estimators=params["n_estimators"], max_depth=params["max_depth"],
                   min_samples_leaf=params["min_samples_leaf"],
                   random_state=TRAIN_SEED, n_jobs=1))


def train_target(target: str) -> dict:
    """Train, select, refit, and register one target model. Returns record."""
    frames = _load_split_frames()
    manifest = json.loads((DATA_DIR / "manifests/dataset_manifest.json").read_text())
    features = preprocessing.feature_names()

    train_raw = frames["train"][list(schemas.PREDICTOR_COLUMNS)]
    val_raw = frames["val"][list(schemas.PREDICTOR_COLUMNS)]
    y_train = targets.read_labels(frames["train"], target).to_numpy()
    y_val = targets.read_labels(frames["val"], target).to_numpy()

    # Scaler fit on TRAIN only; val transformed with train params.
    x_train, scaler = preprocessing.prepare_matrices(train_raw)
    x_val, _ = preprocessing.prepare_matrices(val_raw, scaler)
    assert list(x_train.columns) == features
    columns_for_target(train_raw, target)  # firewall on the real input frame

    best = None
    for algorithm, params, factory in _candidates():
        estimator = factory(params)
        estimator.fit(x_train.to_numpy(), y_train)
        score = _roc_auc(y_val, estimator.predict_proba(x_val.to_numpy())[:, 1])
        if best is None or score > best[0]:
            best = (score, algorithm, params, estimator)
    val_auc, algorithm, params, _ = best

    # Refit winner on train+val (documented); test stays untouched.
    import pandas as pd
    import numpy as np
    refit_raw = pd.concat([train_raw, val_raw], ignore_index=True)
    y_refit = np.concatenate([y_train, y_val])
    x_refit, scaler_refit = preprocessing.prepare_matrices(refit_raw)
    _, _, factory = next(c for c in _candidates()
                         if c[0] == algorithm and c[1] == params)
    final = factory(params)
    final.fit(x_refit.to_numpy(), y_refit)

    split_sizes = {p: len(frames[p]) for p in ("train", "val", "test")}
    record = registry.save_model(
        model_id=registry.MODEL_IDS[target], target=target, algorithm=algorithm,
        hyperparameters=params, estimator=final, feature_names=features,
        dataset_hash=manifest["source_hash"], split_seed=manifest["split"]["seed"],
        split_sizes=split_sizes,
        validation_metrics={"roc_auc_val": val_auc, "refit_rows": int(len(x_refit))},
        scaler={"means": scaler_refit["means"], "stds": scaler_refit["stds"],
                "features": scaler_refit["features"]},
    )
    return record


def train_all() -> dict:
    records = {}
    for target in ("cad", "lad", "lcx", "rca"):
        records[target] = train_target(target)
        print("%s -> %s %s val_auc=%.4f" % (
            target, records[target]["model_id"], records[target]["algorithm"],
            records[target]["validation_metrics"]["roc_auc_val"]), flush=True)
    return records


if __name__ == "__main__":
    train_all()
