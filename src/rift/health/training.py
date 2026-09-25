"""ML experiment framework: manifests, splits, seeds, artifacts, benchmarks.

Covers the REPRODUCIBILITY machinery of model training without performing
weight fitting: on synthetic demo data, fitting weights would be metric
gaming dressed as training, so `fit` is deliberately absent — the module
documents exactly where a future fitting step plugs in once governed data
exists. Everything around fitting (dataset identity, patient-level and
temporal split protection, seeds, experiment IDs, artifact hashes,
benchmark comparison, failure reporting) is real, tested code.
"""
from __future__ import annotations

import hashlib
import json

EXPERIMENT_VERSION = "ml-experiment-v1"


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def dataset_manifest(*, dataset_id: str, source: str, observations: list,
                     day_ranges: dict[str, list[int]]) -> dict:
    """Fingerprint a dataset: content hash plus named day ranges.

    day_ranges maps split names to [start_day, end_day] (inclusive) over
    day_index values, e.g. {"calibration": [0, 29], "test": [30, 59]}.
    """
    content = [
        {"day_index": o.day_index, "resting_hr": o.resting_hr, "hrv_rmssd": o.hrv_rmssd,
         "sleep_hours": o.sleep_hours, "activity_load": o.activity_load}
        for o in observations
    ]
    # Note: day-level rows carry no patient attribution; patient scoping
    # lives in patient_split(), which keeps unattributed rows out of held-out.
    return {
        "dataset_id": dataset_id,
        "source": source,
        "n_observations": len(observations),
        "day_ranges": day_ranges,
        "dataset_hash": _sha256_hex({"dataset_id": dataset_id, "rows": content}),
        "manifest_version": EXPERIMENT_VERSION,
    }


def temporal_split(observations: list, cutoff_day: int) -> tuple[list, list]:
    """Split by time: everything < cutoff_day is past, rest is future.

    Temporal order is never shuffled: random splits on time series leak the
    future into training. Raises on empty sides so silent degenerate splits
    are impossible.
    """
    past = [o for o in observations if o.day_index < cutoff_day]
    future = [o for o in observations if o.day_index >= cutoff_day]
    if not past or not future:
        raise ValueError(f"temporal split at day {cutoff_day} leaves an empty side")
    return past, future


def patient_split(observations: list, held_out_patients: list[str]) -> tuple[list, list]:
    """Split by patient identity for multi-patient datasets.

    Observations without a patient_id attribute stay in the development
    side and are reported — never silently assigned to held-out.
    """
    held_out = [o for o in observations
                if getattr(o, "patient_id", None) in held_out_patients]
    development = [o for o in observations if o not in held_out]
    unattributed = [o for o in development if not getattr(o, "patient_id", None)]
    if not development or not held_out:
        raise ValueError("patient split leaves an empty side")
    return development, {"held_out": held_out, "unattributed_kept_in_development": len(unattributed)}


def run_experiment(*, experiment_id: str, dataset: dict, config: dict,
                   metrics_fn=None) -> dict:
    """Execute one versioned experiment; never raises on metric failure.

    config must carry: seed, feature_schema, windows, threshold, and a
    human-readable purpose. metrics_fn(config, dataset) produces the
    metrics dict; exceptions become status=failed with the error recorded.
    Returns the full experiment record including artifact hashes.
    """
    required = ("seed", "feature_schema", "threshold", "purpose")
    missing = [k for k in required if k not in config]
    record: dict = {
        "experiment_id": experiment_id,
        "experiment_version": EXPERIMENT_VERSION,
        "dataset": {"dataset_id": dataset.get("dataset_id"),
                    "dataset_hash": dataset.get("dataset_hash")},
        "config": config,
        "status": "failed",
        "metrics": {},
        "error": None,
    }
    if missing:
        record["error"] = f"missing config keys: {missing}"
        record["artifact_hash"] = _sha256_hex(record)
        return record
    try:
        record["metrics"] = dict(metrics_fn(config, dataset)) if metrics_fn else {}
        record["status"] = "succeeded"
    except Exception as exc:  # failure is data, not a crash
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["artifact_hash"] = _sha256_hex(record)
    return record


def compare_to_baseline(candidate_metrics: dict, baseline_metrics: dict,
                        higher_is_better: tuple[str, ...] = ("event_agreement",),
                        tolerance: float = 1e-9) -> dict:
    """Compare candidate vs baseline metric dicts without inventing winners.

    Returns per-metric deltas and a verdict of better/worse/tied per metric
    plus an overall summary. No single score, no auto-promotion — promotion
    decisions belong to model_registry.promote with evidence.
    """
    details: dict = {}
    for key in sorted(set(candidate_metrics) | set(baseline_metrics)):
        if key not in candidate_metrics or key not in baseline_metrics:
            details[key] = {"verdict": "incomparable", "delta": None}
            continue
        delta = candidate_metrics[key] - baseline_metrics[key]
        if abs(delta) <= tolerance:
            verdict = "tied"
        elif (delta > 0) == (key in higher_is_better):
            verdict = "better"
        else:
            verdict = "worse"
        details[key] = {"verdict": verdict, "delta": delta}
    verdicts = [d["verdict"] for d in details.values()]
    return {"metrics": details,
            "summary": "better" if verdicts and all(v == "better" for v in verdicts)
                       else "worse" if "worse" in verdicts else "mixed-or-tied"}
