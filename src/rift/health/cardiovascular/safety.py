"""Track-A safety layer (Phase 18): gate every prediction before display.

Three independent checks, evaluated in order:

1. CALIBRATION PRESENT — a registered model without a recorded, hash-
   verified calibrator is refused outright (``safe_to_show=False``).
   Uncalibrated probabilities must never reach a screen.
2. WEAK-MODEL FLAGS — RCA predictions carry a NOT-decision-grade warning;
   negative LCX predictions carry a does-not-rule-out warning. Shown, but
   labeled.
3. OUT-OF-DISTRIBUTION INPUT — each predictor is compared against values
   observed in TRAIN (numeric range, categorical levels). Off-range fields
   are listed; the prediction still shows, flagged.

Blocks (refusals) happen only for check 1 and for non-finite/
out-of-bounds probabilities. Everything else warns. The module never
touches the network and never changes the model.
"""
from __future__ import annotations

import math

from . import registry, schemas

DISCLAIMER = ("Research prototype output; not a medical device. "
              "See /api/cardio/model-cards for limitations.")

_bounds_cache: dict | None = None


def train_bounds() -> dict:
    """Observed train values per feature: (min, max) or level set."""
    global _bounds_cache
    if _bounds_cache is not None:
        return _bounds_cache
    from . import evaluate
    frames = evaluate._load_split_frames()
    train = frames["train"][list(schemas.PREDICTOR_COLUMNS)]
    bounds = {}
    for column in train.columns:
        if train[column].dtype == object:
            bounds[column] = {"levels": sorted(str(v) for v in train[column].dropna().unique())}
        else:
            bounds[column] = {"min": float(train[column].min()),
                              "max": float(train[column].max())}
    _bounds_cache = bounds
    return bounds


def out_of_distribution_fields(predictors: dict) -> list:
    """Predictor names whose value was never observed in train."""
    bounds = train_bounds()
    flagged = []
    for column in schemas.PREDICTOR_COLUMNS:
        value = predictors.get(column)
        spec = bounds[column]
        if "levels" in spec:
            if str(value) not in spec["levels"]:
                flagged.append(column)
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                flagged.append(column)
                continue
            if isinstance(number, float) and math.isnan(number):
                flagged.append(column)
            elif number < spec["min"] or number > spec["max"]:
                flagged.append(column)
    return flagged


def assess_prediction(model_id: str, predictors: dict, probability: float) -> dict:
    """Safety verdict for one prediction. Never raises on model content."""
    warnings: list = []
    _, record = registry.load_model(model_id)
    target = record["target"]

    calibration = record.get("calibration") or {}
    if not calibration.get("method"):
        return {"safe_to_show": False,
                "warnings": ["model %r has no recorded calibration: refusing" % model_id],
                "out_of_distribution_fields": [],
                "disclaimer": DISCLAIMER}

    if not isinstance(probability, float) or math.isnan(probability):
        return {"safe_to_show": False,
                "warnings": ["non-finite probability: refusing"],
                "out_of_distribution_fields": [],
                "disclaimer": DISCLAIMER}
    if probability < 0.0 or probability > 1.0:
        return {"safe_to_show": False,
                "warnings": ["probability out of bounds: refusing"],
                "out_of_distribution_fields": [],
                "disclaimer": DISCLAIMER}

    if target == "rca":
        warnings.append("RCA predictions are NOT decision-grade "
                        "(near-chance test AUC; see model card); shown for completeness only.")
    if target == "lcx" and probability < 0.5:
        warnings.append("A negative LCX prediction does NOT rule out LCX disease "
                        "(low recall; see model card).")

    ood = out_of_distribution_fields(predictors)
    if ood:
        warnings.append("Out-of-distribution input: %d field(s) outside train-observed "
                        "values (%s)." % (len(ood), ", ".join(sorted(ood)[:5])))

    return {"safe_to_show": True,
            "warnings": warnings,
            "out_of_distribution_fields": ood,
            "disclaimer": DISCLAIMER}
