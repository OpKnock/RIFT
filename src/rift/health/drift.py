"""Distribution-shift detection over observation windows (Phase 9/18-lite).

Compares a reference window against a current window per metric: mean
shift in units of reference spread, variance ratio, and missingness-rate
delta. Thresholds are explicit constants, not learned. Emits drift events
(field, kind, magnitude, threshold) consumed by monitoring/alerting — and
by Guardian's input-quality path in a future turn, not silently today.

Deterministic, stdlib-only, no fitted models.
"""
from __future__ import annotations

from statistics import mean, pstdev

from .models import WearableObservation
from .wearable import FIELDS

MEAN_SHIFT_THRESHOLD = 2.0   # |mean_current - mean_ref| in reference stds
VARIANCE_RATIO_THRESHOLD = 4.0  # var_current / var_ref (or inverse), either direction
MISSINGNESS_DELTA_THRESHOLD = 0.25  # absolute change in missing rate


def _values(observations: list[WearableObservation], field: str) -> list[float]:
    return [getattr(o, field) for o in observations if getattr(o, field) is not None]


def field_drift(reference: list[float], current: list[float]) -> dict:
    """One metric, two windows: shift diagnostics with explicit thresholds."""
    result: dict = {"n_ref": len(reference), "n_cur": len(current),
                    "mean_shift_std": None, "variance_ratio": None,
                    "drifted": False, "reasons": []}
    if len(reference) < 2 or len(current) < 1:
        result["reasons"].append("insufficient samples: cannot assess drift")
        return result
    ref_mean, ref_sd = mean(reference), pstdev(reference)
    cur_mean = mean(current)
    if ref_sd > 0:
        shift = abs(cur_mean - ref_mean) / ref_sd
        result["mean_shift_std"] = shift
        if shift >= MEAN_SHIFT_THRESHOLD:
            result["drifted"] = True
            result["reasons"].append(f"mean shift {shift:.2f} stds >= {MEAN_SHIFT_THRESHOLD}")
    elif cur_mean != ref_mean:
        # Zero-variance reference: any sustained deviation is significant,
        # not invisible. Report the raw gap so reviewers see why.
        result["mean_shift_std"] = float("inf")
        result["drifted"] = True
        result["reasons"].append(
            f"mean moved {abs(cur_mean - ref_mean):.2f} off a constant baseline")
    if len(current) >= 2:
        cur_sd = pstdev(current)
        if ref_sd > 0 and cur_sd == 0:
            # Variance collapse to a constant is extreme drift, not ratio 0.
            result["variance_ratio"] = 0.0
            result["drifted"] = True
            result["reasons"].append(
                f"variance collapsed to constant (ref sd {ref_sd:.2f} -> 0)")
        else:
            ratio = (cur_sd ** 2 / ref_sd ** 2) if ref_sd > 0 else (float("inf") if cur_sd > 0 else 1.0)
            result["variance_ratio"] = ratio
            if ratio >= VARIANCE_RATIO_THRESHOLD or (ratio > 0 and 1 / ratio >= VARIANCE_RATIO_THRESHOLD):
                result["drifted"] = True
                result["reasons"].append(f"variance ratio {ratio:.2f} breaches {VARIANCE_RATIO_THRESHOLD}")
    return result


def missingness_drift(reference: list[WearableObservation],
                      current: list[WearableObservation]) -> dict:
    """Compare per-field missing rates between windows."""
    result: dict = {"fields": {}, "drifted": False, "reasons": []}
    for field in FIELDS:
        ref_missing = sum(1 for o in reference if getattr(o, field) is None) / max(1, len(reference))
        cur_missing = sum(1 for o in current if getattr(o, field) is None) / max(1, len(current))
        delta = cur_missing - ref_missing
        result["fields"][field] = {"ref": ref_missing, "cur": cur_missing, "delta": delta}
        if abs(delta) >= MISSINGNESS_DELTA_THRESHOLD:
            result["drifted"] = True
            result["reasons"].append(f"missingness {field}: {ref_missing:.2f} -> {cur_missing:.2f}")
    return result


def detect_drift(reference: list[WearableObservation],
                 current: list[WearableObservation]) -> dict:
    """Full drift sweep: per-field distribution + missingness + source sets.

    Returns {"drifted": bool, "events": [...], "fields": {...},
    "missingness": {...}, "sources": {...}}. Empty windows can never report
    drift — they report inability instead.
    """
    events: list[dict] = []
    fields: dict = {}
    if not reference or not current:
        return {"drifted": False, "events": [{"kind": "insufficient-data",
                "magnitude": 0.0, "threshold": 0.0,
                "message": "empty reference or current window: drift unassessable"}],
                "fields": fields, "missingness": {}, "sources": {}}
    for field in FIELDS:
        outcome = field_drift(_values(reference, field), _values(current, field))
        fields[field] = outcome
        for reason in outcome["reasons"]:
            if reason.startswith("insufficient"):
                continue
            magnitude = outcome.get("mean_shift_std") or outcome.get("variance_ratio") or 0.0
            events.append({"field": field, "kind": "distribution",
                           "magnitude": magnitude, "threshold": MEAN_SHIFT_THRESHOLD,
                           "message": reason})
    missing = missingness_drift(reference, current)
    for reason in missing["reasons"]:
        events.append({"field": "missingness", "kind": "missingness",
                       "magnitude": MISSINGNESS_DELTA_THRESHOLD, "threshold": MISSINGNESS_DELTA_THRESHOLD,
                       "message": reason})
    ref_sources = {o.provenance for o in reference if o.provenance}
    cur_sources = {o.provenance for o in current if o.provenance}
    sources = {"reference": sorted(ref_sources), "current": sorted(cur_sources),
               "added": sorted(cur_sources - ref_sources), "removed": sorted(ref_sources - cur_sources)}
    if sources["added"] or sources["removed"]:
        events.append({"field": "source", "kind": "source-shift",
                       "magnitude": float(len(sources["added"]) + len(sources["removed"])),
                       "threshold": 1.0, "message": f"source set changed: +{sources['added']} -{sources['removed']}"})
    return {"drifted": bool(events), "events": events, "fields": fields,
            "missingness": missing["fields"], "sources": sources}
