"""Track-A calibration (Phase 6): Platt vs isotonic, OOF-fit, ECE-measured.

Honesty protocol: the shipped estimators were refit on train+val, so no
fresh calibration split exists. The calibrator is therefore fit on
OUT-OF-FOLD predictions (5-fold stratified ``cross_val_predict`` on
train+val with the exact registered winner config) — never on test.
Per target we fit both sigmoid (Platt) and isotonic, keep the one with
lower Brier score on the OOF predictions, and report ECE/Brier before
and after on both OOF and the held-out test split.

Artifacts: ``calibrator.pkl`` beside each registry entry, the registry
record's ``calibration`` slot filled in, and
``data/cardiovascular/evaluation/calibration.json``.

One command: ``python -m rift.health.cardiovascular.calibration``
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

from . import dataset, evaluate, preprocessing, registry, schemas, targets
from .leakage import columns_for_target

CALIBRATION_BINS = 10


def expected_calibration_error(y_true, probs, n_bins: int = CALIBRATION_BINS) -> float:
    """Mean |accuracy - confidence| weighted by bin mass (equal-width bins)."""
    import numpy as np
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        if high == 1.0:
            mask = (probs >= low) & (probs <= high)
        else:
            mask = (probs >= low) & (probs < high)
        mass = int(mask.sum())
        if not mass:
            continue
        acc = float(y_true[mask].mean())
        conf = float(probs[mask].mean())
        ece += (mass / len(y_true)) * abs(acc - conf)
    return float(ece)


def brier_score(y_true, probs) -> float:
    import numpy as np
    y_true = np.asarray(y_true, dtype=float)
    probs = np.asarray(probs, dtype=float)
    return float(((probs - y_true) ** 2).mean())


def reliability_curve(y_true, probs, n_bins: int = CALIBRATION_BINS) -> list:
    """Per-bin (center, accuracy, confidence, count) for reliability plots."""
    import numpy as np
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = []
    for low, high in zip(edges[:-1], edges[1:]):
        mask = ((probs >= low) & (probs <= high)) if high == 1.0 else (
            (probs >= low) & (probs < high))
        count = int(mask.sum())
        bins.append({
            "center": float((low + high) / 2),
            "count": count,
            "accuracy": float(y_true[mask].mean()) if count else 0.0,
            "confidence": float(probs[mask].mean()) if count else 0.0,
        })
    return bins


def _trainval_xy(target: str):
    import numpy as np
    frames = evaluate._load_split_frames()
    raw = frames["train"][list(schemas.PREDICTOR_COLUMNS)]
    import pandas as pd
    raw = pd.concat([raw, frames["val"][list(schemas.PREDICTOR_COLUMNS)]],
                    ignore_index=True)
    columns_for_target(raw, target)
    y = np.concatenate([targets.read_labels(frames["train"], target).to_numpy(),
                        targets.read_labels(frames["val"], target).to_numpy()])
    x_scaled, _ = preprocessing.prepare_matrices(raw)
    return x_scaled.to_numpy(), y


def out_of_fold_scores(target: str, folds: int = 5, seed: int = 7):
    """OOF positive-class scores on train+val for the winner config."""
    import numpy as np
    from sklearn.model_selection import cross_val_predict
    _, record = registry.load_model(registry.MODEL_IDS[target])
    x, y = _trainval_xy(target)
    estimator = evaluate._rebuild(record)
    scores = cross_val_predict(estimator, x, y, cv=_stratified(folds, seed),
                               method="predict_proba", n_jobs=1)[:, 1]
    return np.asarray(y, dtype=int), np.asarray(scores, dtype=float)


def _stratified(folds: int, seed: int):
    from sklearn.model_selection import StratifiedKFold
    return StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)


def fit_calibrator(target: str) -> dict:
    """Fit Platt + isotonic on OOF scores, keep lower-Brier method."""
    import numpy as np
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    y_oof, s_oof = out_of_fold_scores(target)
    candidates = {}
    platt = LogisticRegression(solver="lbfgs")
    platt.fit(s_oof.reshape(-1, 1), y_oof)
    p_platt = platt.predict_proba(s_oof.reshape(-1, 1))[:, 1]
    candidates["sigmoid"] = (platt, p_platt)
    iso = IsotonicRegression(out_of_bounds="clip")
    p_iso = iso.fit_transform(s_oof, y_oof)
    candidates["isotonic"] = (iso, np.asarray(p_iso, dtype=float))
    scored = {name: (est, brier_score(y_oof, p))
              for name, (est, p) in candidates.items()}
    method = min(scored, key=lambda name: scored[name][1])
    estimator, _ = scored[method]

    before = {"ece": expected_calibration_error(y_oof, s_oof),
              "brier": brier_score(y_oof, s_oof)}
    after_probs = np.asarray(candidates[method][1], dtype=float)
    after = {"ece": expected_calibration_error(y_oof, after_probs),
             "brier": brier_score(y_oof, after_probs)}

    # Held-out test check (report only; calibrator never saw test).
    _, record = registry.load_model(registry.MODEL_IDS[target])
    frames = evaluate._load_split_frames()
    scaler = registry.load_scaler(record["model_id"])
    x_test, y_test, _ = evaluate._split_xy(frames, ("test",), target, scaler)
    raw_probs = np.asarray(
        record_estimator(record).predict_proba(x_test)[:, 1], dtype=float)
    cal_probs = np.asarray(apply_estimator(estimator, raw_probs), dtype=float)
    test = {
        "before": {"ece": expected_calibration_error(y_test, raw_probs),
                   "brier": brier_score(y_test, raw_probs)},
        "after": {"ece": expected_calibration_error(y_test, cal_probs),
                  "brier": brier_score(y_test, cal_probs)},
        "reliability_before": reliability_curve(y_test, raw_probs),
        "reliability_after": reliability_curve(y_test, cal_probs),
    }
    return {
        "target": target,
        "model_id": record["model_id"],
        "method": method,
        "estimator": estimator,
        "oof": {"before": before, "after": after, "n": int(len(y_oof))},
        "test": test,
    }


def record_estimator(record: dict):
    estimator, _ = registry.load_model(record["model_id"])
    return estimator


def apply_estimator(calibrator, probs):
    import numpy as np
    probs = np.asarray(probs, dtype=float)
    if hasattr(calibrator, "predict_proba"):
        return calibrator.predict_proba(probs.reshape(-1, 1))[:, 1]
    return calibrator.predict(probs)


def predict_calibrated(model_id: str, frame):
    """Calibrated positive-class probabilities (falls back to raw scores)."""
    import numpy as np
    from .predict import predict_proba
    raw = np.asarray(predict_proba(model_id, frame)["probabilities"], dtype=float)
    path = registry.REGISTRY_DIR / model_id / "calibrator.pkl"
    if not path.exists():
        return [float(v) for v in raw]
    calibrator = pickle.loads(path.read_bytes())
    return [float(v) for v in apply_estimator(calibrator, raw)]


def calibrate_all() -> dict:
    """Fit, persist, and record calibration for all four models."""
    summary = {"protocol": ("OOF 5-fold scores on train+val fit Platt+isotonic; "
                             "lower OOF Brier wins; test reported once, never fit"),
               "models": {}}
    for target in ("cad", "lad", "lcx", "rca"):
        result = fit_calibrator(target)
        model_dir = registry.REGISTRY_DIR / result["model_id"]
        (model_dir / "calibrator.pkl").write_bytes(pickle.dumps(result["estimator"]))
        record_path = model_dir / "record.json"
        record = json.loads(record_path.read_text())
        record["calibration"] = {
            "method": result["method"],
            "oof_ece_before": result["oof"]["before"]["ece"],
            "oof_ece_after": result["oof"]["after"]["ece"],
            "oof_brier_before": result["oof"]["before"]["brier"],
            "oof_brier_after": result["oof"]["after"]["brier"],
            "test_ece_before": result["test"]["before"]["ece"],
            "test_ece_after": result["test"]["after"]["ece"],
            "test_brier_before": result["test"]["before"]["brier"],
            "test_brier_after": result["test"]["after"]["brier"],
        }
        record_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        summary["models"][target] = {k: v for k, v in result.items()
                                     if k != "estimator"}
    out = evaluate.EVAL_DIR / "calibration.json"
    out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def print_summary(summary: dict) -> None:
    for target in ("cad", "lad", "lcx", "rca"):
        entry = summary["models"][target]
        print("%s [%s | %s]" % (target.upper(), entry["model_id"], entry["method"]))
        print("  oof   ece %.3f -> %.3f   brier %.3f -> %.3f" % (
            entry["oof"]["before"]["ece"], entry["oof"]["after"]["ece"],
            entry["oof"]["before"]["brier"], entry["oof"]["after"]["brier"]))
        print("  test  ece %.3f -> %.3f   brier %.3f -> %.3f" % (
            entry["test"]["before"]["ece"], entry["test"]["after"]["ece"],
            entry["test"]["before"]["brier"], entry["test"]["after"]["brier"]))


if __name__ == "__main__":
    print_summary(calibrate_all())
