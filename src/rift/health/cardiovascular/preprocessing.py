"""Deterministic preprocessing (Phase 2/14): encode + scale, fit on train only.

- Binary Y/N -> 1/0, Sex Male -> 1, fixed one-hots for BBB/VHD.
- Numerics standardized with train mean/std (stored in the scaler record).
- Zero-variance columns dropped per schemas.DROPPED_COLUMNS (documented).
- Unknown categories at transform time -> all-zero one-hot (never crash).
- The leakage firewall runs on every input frame.
"""
from __future__ import annotations

import math

from . import schemas
from .leakage import assert_no_leakage


def _coerce_binary(value) -> float:
    if value == 1 or value == "Y":
        return 1.0
    if value == 0 or value == "N":
        return 0.0
    raise ValueError("non-binary value in Y/N column: %r" % (value,))


def encoded_frame(df):
    """Raw predictor frame -> numeric frame (no scaling yet)."""
    assert_no_leakage(df)
    import pandas as pd
    out = pd.DataFrame(index=df.index)
    for column in schemas.PREDICTOR_COLUMNS:
        if column in schemas.DROPPED_COLUMNS:
            continue
        series = df[column]
        if column in schemas.BINARY_YN:
            out[column] = [float(_coerce_binary(v)) for v in series.tolist()]
        elif column == "Sex":
            out[column] = [1.0 if v == "Male" else 0.0 for v in series.tolist()]
        elif column in schemas.CATEGORICAL_LEVELS:
            for level in schemas.CATEGORICAL_LEVELS[column]:
                out["%s=%s" % (column, level)] = [
                    1.0 if v == level else 0.0 for v in series.tolist()]
        else:
            out[column] = [float(v) for v in series.tolist()]
    return out


def feature_names() -> list:
    """Final model feature order (stable across runs)."""
    names = []
    for column in schemas.PREDICTOR_COLUMNS:
        if column in schemas.DROPPED_COLUMNS:
            continue
        if column in schemas.BINARY_YN or column == "Sex":
            names.append(column)
        elif column in schemas.CATEGORICAL_LEVELS:
            names.extend("%s=%s" % (column, level)
                         for level in schemas.CATEGORICAL_LEVELS[column])
        else:
            names.append(column)
    return names


def fit_scaler(train_numeric):
    """Per-column mean/std from the TRAIN frame only."""
    import pandas as pd
    means, stds = {}, {}
    for column in train_numeric.columns:
        values = [float(v) for v in train_numeric[column].tolist()]
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(var) if var > 0 else 1.0
        means[column], stds[column] = mean, std
    return {"means": means, "stds": stds, "features": list(train_numeric.columns)}


def apply_scaler(numeric, scaler: dict):
    """Standardize with stored train params (unknown columns ignored)."""
    import pandas as pd
    out = pd.DataFrame(index=numeric.index)
    for column in scaler["features"]:
        mean, std = scaler["means"][column], scaler["stds"][column]
        out[column] = [(float(v) - mean) / std for v in numeric[column].tolist()]
    return out


def prepare_matrices(raw_frame, scaler: dict | None = None):
    """Raw predictor frame -> (X scaled DataFrame, scaler used)."""
    numeric = encoded_frame(raw_frame)
    if scaler is None:
        scaler = fit_scaler(numeric)
    return apply_scaler(numeric, scaler), scaler
