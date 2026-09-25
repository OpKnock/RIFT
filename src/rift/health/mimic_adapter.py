"""MIMIC/PhysioNet → CanonicalObservation mapping (example, no real data bundled).

This adapter demonstrates how a governed public dataset plugs into
PublicDatasetSource without changing the twin pipeline. Replace the
example CSV with the real export and keep the same header — the twin,
Guardian, and evaluation layers work unchanged.
"""
from __future__ import annotations

import csv

from .observations import normalize_batch

# Example mapping for a MIMIC-IV-style vitals export. Columns are
# illustrative: adapt to the actual export header of your approved
# dataset. Every mapping is explicit — no silent metric inference.
# 
# IMPORTANT: MIMIC's heart_rate is generic recorded vital signs, NOT
# automatically resting heart rate. We map to 'heart_rate' to preserve
# semantic accuracy. A separate validated derivation would be needed
# to produce 'resting_hr'.
MIMIC_COLUMN_MAP = {
    "subject_id": "patient_id",
    "charttime": "timestamp",
    "heart_rate": "heart_rate",
    "hrv": "hrv_rmssd",
    "sleep_duration": "sleep_hours",
    "activity": "activity_load",
}


def load_mimic_example(path: str):
    """Load a MIMIC-style CSV via the canonical pipeline.

    Expected header (example): subject_id,charttime,heart_rate,hrv,sleep_duration,activity
    Returns (accepted, issues) exactly like PublicDatasetSource, so
    validation, unit handling, and provenance are identical.
    """
    try:
        handle = open(path, "r", encoding="utf-8", newline="")
    except OSError as exc:
        raise ValueError(f"cannot open MIMIC CSV: {path}") from exc
    with handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [c for c in ("subject_id", "charttime") if c not in fields]
        if missing:
            raise ValueError(f"MIMIC CSV missing columns: {missing}")
        raw = []
        for row in reader:
            for src_col, metric in MIMIC_COLUMN_MAP.items():
                if src_col in ("subject_id", "charttime"):
                    continue
                if row.get(src_col) in (None, ""):
                    continue
                raw.append({
                    "patient_id": row.get("subject_id") or "unknown",
                    "timestamp": row.get("charttime") or "",
                    "source": "mimic",
                    "metric": metric,
                    "value": row[src_col],
                    "unit": {"heart_rate": "bpm", "hrv_rmssd": "ms",
                             "sleep_hours": "h", "activity_load": "index"}[metric],
                    "quality": 1.0,
                    "provenance": path,
                })
    return normalize_batch(raw)
