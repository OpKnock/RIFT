"""Canonical clinical observation model (v1 data platform).

Every measurement entering the twin — whether from FHIR, CSV, JSON, or a
future wearable API — becomes one of these first. Validation, unit
normalization, and provenance are attached here, never downstream.

A CanonicalObservation is deliberately small: patient, timestamp,
source, metric, value, unit, quality, provenance. Day-level
WearableObservation rows are derived from these, so multi-observation
days work without changing the twin core.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import WearableObservation

# Canonical metric names and their expected units. Values arriving in other
# units are converted; unknown units are rejected, never guessed.
METRICS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")
EXPECTED_UNITS = {
    "resting_hr": "bpm",
    "hrv_rmssd": "ms",
    "sleep_hours": "h",
    "activity_load": "index",
}

# Accepted unit aliases per metric: alias -> multiplier to canonical unit.
UNIT_ALIASES = {
    "resting_hr": {"bpm": 1.0, "beats_per_minute": 1.0, "bpm_": 1.0},
    "hrv_rmssd": {"ms": 1.0, "millisecond": 1.0, "s": 1000.0},
    "sleep_hours": {"h": 1.0, "hour": 1.0, "hours": 1.0, "min": 1.0 / 60.0, "s": 1.0 / 3600.0},
    "activity_load": {"index": 1.0, "points": 1.0, "steps": 0.01},
}


@dataclass(frozen=True)
class CanonicalObservation:
    patient_id: str
    timestamp: str  # ISO-8601, e.g. 2026-01-04T08:04:00
    source: str     # e.g. fhir, csv, json, wearable-api
    metric: str
    value: float
    unit: str
    quality: float = 1.0  # 0..1 as asserted by the source adapter
    provenance: str = ""  # free text: file/device/endpoint identity

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "quality": self.quality,
            "provenance": self.provenance,
        }


def validate_observation(raw: dict) -> tuple[CanonicalObservation | None, list[str]]:
    """Validate + normalize one raw observation dict. Never raises.

    Returns (observation, issues). Unknown metrics, bad timestamps, unknown
    units, and non-numeric values are rejected with reasons; quality is
    clamped to 0..1.
    """
    issues: list[str] = []
    if not isinstance(raw, dict):
        return None, ["observation must be an object"]
    metric = raw.get("metric")
    if metric not in METRICS:
        return None, [f"unknown metric {metric!r}; expected one of {list(METRICS)}"]
    timestamp = raw.get("timestamp")
    if not isinstance(timestamp, str) or len(timestamp) < 10 or "T" not in timestamp:
        return None, [f"bad timestamp {timestamp!r}; expected ISO-8601"]
    try:
        value = float(raw.get("value"))
    except (TypeError, ValueError):
        return None, [f"non-numeric value for {metric!r}"]
    aliases = UNIT_ALIASES[metric]
    unit = raw.get("unit")
    if unit not in aliases:
        return None, [f"unknown unit {unit!r} for {metric!r}; expected one of {sorted(aliases)}"]
    try:
        quality = float(raw.get("quality", 1.0))
    except (TypeError, ValueError):
        issues.append("non-numeric quality clamped to 0.0")
        quality = 0.0
    quality = max(0.0, min(1.0, quality))
    patient_id = raw.get("patient_id")
    if not isinstance(patient_id, str) or not patient_id.strip():
        return None, ["missing patient_id"]
    return CanonicalObservation(
        patient_id=patient_id.strip(),
        timestamp=timestamp,
        source=str(raw.get("source") or "unknown"),
        metric=metric,
        value=value * aliases[unit],
        unit=EXPECTED_UNITS[metric],
        quality=quality,
        provenance=str(raw.get("provenance") or ""),
    ), issues


def normalize_batch(raw_items: list[dict]) -> tuple[list[CanonicalObservation], list[str]]:
    """Validate a batch; returns (accepted, issues). Rejects never abort the batch."""
    accepted: list[CanonicalObservation] = []
    issues: list[str] = []
    if not isinstance(raw_items, list):
        return [], ["batch must be a list"]
    for index, raw in enumerate(raw_items):
        obs, problems = validate_observation(raw)
        if obs is not None:
            accepted.append(obs)
        issues.extend(f"[{index}] {p}" for p in problems)
    return accepted, issues
