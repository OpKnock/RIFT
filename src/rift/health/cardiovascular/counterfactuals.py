"""Track-A counterfactuals (Phase 11): minimal single-feature what-ifs.

For one patient row and one model, every predictor is perturbed on its own
over values actually observed in TRAIN (numeric: 10/25/50/75/90th
percentiles; categorical/binary: observed levels), all candidates scored in
one batch with calibrated probabilities. Edits that move the prediction
across 0.5 are ranked corrective-first (toward the true label) then by
smallest standardized-space distance.

These explain MODEL BEHAVIOR, not physiology: a counterfactual says "the
model would change its mind if ...", never "the patient should change ...".
Research prototype; not medical advice.

One command: ``python -m rift.health.cardiovascular.counterfactuals``
"""
from __future__ import annotations

import json

from . import calibration, evaluate, preprocessing, registry, schemas, targets
from .leakage import columns_for_target

THRESHOLD = 0.5
TOP_K = 5
# Observed train values per numeric feature: extremes included so confident
# predictions still get reachable what-ifs; every value is real, none invented.
QUANTILES = (0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 1.0)

# Demographics/history a patient cannot change: valid model explanations,
# flagged so no UI ever presents them as recommendations.
NON_ACTIONABLE = {"Age", "Sex", "FH"}


def _train_predictors():
    import pandas as pd
    frames = evaluate._load_split_frames()
    return frames["train"][list(schemas.PREDICTOR_COLUMNS)]


def candidate_values(train) -> dict:
    """Observed train values per feature: quantiles or levels."""
    values = {}
    for column in train.columns:
        observed = train[column].dropna().unique().tolist()
        if train[column].dtype == object or set(observed) <= {0, 1, "0", "1"}:
            values[column] = sorted(observed, key=str)
        else:
            values[column] = sorted(float(train[column].quantile(q)) for q in QUANTILES)
    return values


def _loaded(model_id: str):
    estimator, _ = registry.load_model(model_id)
    scaler = registry.load_scaler(model_id)
    try:
        calibrator = registry.load_calibrator(model_id)
    except ValueError:
        calibrator = None
    return estimator, scaler, calibrator


def counterfactuals_for(model_id: str, raw_row, true_label: int | None = None,
                        top_k: int = TOP_K) -> dict:
    """Single-feature flips for one patient row (pandas Series or 1-row frame)."""
    import numpy as np
    import pandas as pd
    if isinstance(raw_row, pd.DataFrame):
        raw_row = raw_row.iloc[0]
    estimator, scaler, calibrator = _loaded(model_id)
    _, record = registry.load_model(model_id)
    target = record["target"]
    train = _train_predictors()
    values = candidate_values(train)

    base_raw = pd.DataFrame([raw_row[list(schemas.PREDICTOR_COLUMNS)]])
    columns_for_target(base_raw, target)
    base_enc = preprocessing.apply_scaler(
        preprocessing.encoded_frame(base_raw), scaler).to_numpy()
    base_raw_prob = float(estimator.predict_proba(base_enc)[0, 1])
    base_prob = float(calibration.apply_estimator(calibrator, [base_raw_prob])[0]
                      if calibrator is not None else base_raw_prob)
    base_side = base_raw_prob >= THRESHOLD

    edits, order = [], []
    for feature in schemas.PREDICTOR_COLUMNS:
        if len(values[feature]) < 2:
            continue  # constant in train: nothing to perturb
        current = raw_row[feature]
        for value in values[feature]:
            if _same(current, value):
                continue
            edited = base_raw.copy()
            edited[feature] = __import__("pandas").Series(
                [value], index=edited.index)
            edits.append((feature, value))
            order.append(edited)
    batch = preprocessing.apply_scaler(
        preprocessing.encoded_frame(__import__("pandas").concat(order, ignore_index=True)),
        scaler).to_numpy()
    raw_probs = estimator.predict_proba(batch)[:, 1]
    probs = np.asarray(calibration.apply_estimator(calibrator, raw_probs)
                       if calibrator is not None else raw_probs, dtype=float)

    base_cols = preprocessing.encoded_frame(base_raw).to_numpy()[0]
    results = []
    for (feature, value), prob in zip(edits, probs):
        if (prob >= THRESHOLD) == base_side:
            continue  # no flip
        candidate = base_raw.copy()
        candidate[feature] = __import__("pandas").Series(
            [value], index=candidate.index)
        new_cols = preprocessing.encoded_frame(candidate).to_numpy()[0]
        mask = _feature_mask(feature)
        distance = float(np.abs(new_cols[mask] - base_cols[mask]).sum())
        corrective = (true_label is not None and
                      ((prob >= THRESHOLD) == bool(true_label)))
        results.append({
            "feature": feature,
            "from": _jsonable(raw_row[feature]),
            "to": _jsonable(value),
            "prob_before": base_prob,
            "prob_after": float(prob),
            "corrective": bool(corrective),
            "actionable": feature not in NON_ACTIONABLE,
            "std_distance": distance,
        })
    results.sort(key=lambda r: (not r["corrective"], r["std_distance"]))
    seen, diverse = set(), []
    for row in results:
        if row["feature"] in seen:
            continue  # one representative edit per feature: varied panels
        seen.add(row["feature"])
        diverse.append(row)
    return {"model_id": model_id, "target": target,
            "prob_before": base_prob, "true_label": true_label,
            "counterfactuals": diverse[:top_k]}


def _feature_mask(feature: str):
    import numpy as np
    names = preprocessing.feature_names()
    return np.array([n == feature or n.startswith(feature + "=") for n in names])


def _same(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _jsonable(value):
    import math
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


if __name__ == "__main__":
    import pandas as pd
    frames = evaluate._load_split_frames()
    sample = frames["test"].iloc[[0]]
    label = int(targets.read_labels(sample, "cad").iloc[0])
    print(json.dumps(counterfactuals_for("cad-v1", sample, label), indent=1))
