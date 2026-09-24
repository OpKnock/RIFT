"""Baseline estimator comparison (Phase 5, experimental).

The twin's production baseline stays the median layer (never silently
replaced). This module lets reviewers compare valid alternative
estimators on the same history and see exactly where they disagree:
median vs quality-weighted mean vs exponential-weighted mean (EWM).
Estimators are pure functions over value lists — no hidden state, no
fitted parameters beyond the documented alpha.
"""
from __future__ import annotations

from statistics import median

EWM_ALPHA = 0.3  # documented smoothing factor, not tuned per dataset


def median_estimate(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return float(median(clean)) if clean else None


def weighted_mean_estimate(values: list[float], weights: list[float] | None = None) -> float | None:
    pairs = [(v, w) for v, w in zip(values, weights if weights else [1.0] * len(values))
             if v is not None]
    total_weight = sum(w for _, w in pairs)
    if not pairs or total_weight <= 0:
        return median_estimate(values)
    return float(sum(v * w for v, w in pairs) / total_weight)


def ewm_estimate(values: list[float], alpha: float = EWM_ALPHA) -> float | None:
    """Exponential-weighted mean: recent observations count more."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    level = clean[0]
    for value in clean[1:]:
        level = alpha * value + (1 - alpha) * level
    return float(level)


def compare_estimators(field_values: dict[str, list[float]],
                       weights: dict[str, list[float]] | None = None) -> dict:
    """Run all estimators per field; report estimates and max disagreement.

    Returns {"estimates": {estimator: {field: value}}, "max_disagreement":
    {field: range}, "estimators": [...]}. Large disagreement means the
    baseline choice matters for that field — flagged, not hidden.
    """
    weights = weights or {}
    estimates: dict[str, dict[str, float | None]] = {
        "median": {}, "weighted_mean": {}, "ewm": {},
    }
    for field, values in field_values.items():
        estimates["median"][field] = median_estimate(values)
        estimates["weighted_mean"][field] = weighted_mean_estimate(values, weights.get(field))
        estimates["ewm"][field] = ewm_estimate(values)
    disagreement: dict[str, float | None] = {}
    for field in field_values:
        vals = [e[field] for e in estimates.values() if e[field] is not None]
        disagreement[field] = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
    return {"estimates": estimates, "max_disagreement": disagreement,
            "estimators": ["median", "weighted_mean", "ewm"],
            "production": "median"}
