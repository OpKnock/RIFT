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

import math
from dataclasses import dataclass
from datetime import datetime, timezone

# Canonical metric names and their expected units. Values arriving in other
# units are converted; unknown units are rejected, never guessed.
#
# resting_hr means RESTING heart rate specifically. Generic heart-rate
# readings use heart_rate; R-R interval SD uses rr_sd. The twin's risk
# path consumes resting_hr/hrv_rmssd only — generic readings are preserved
# at observation level but never silently relabeled (see adapters.py).
METRICS = (
    "resting_hr", "hrv_rmssd", "sleep_hours", "activity_load",
    "heart_rate", "rr_sd",
    "eda", "skin_temp",  # wearable exam stress dataset
    "spo2", "temperature", "sbp", "map", "dbp", "resp_rate",
    "icu_los_hours", "sepsis_label",  # PhysioNet Sepsis Challenge 2019
)
EXPECTED_UNITS = {
    "resting_hr": "bpm",
    "hrv_rmssd": "ms",
    "sleep_hours": "h",
    "activity_load": "index",
    "heart_rate": "bpm",
    "rr_sd": "ms",
    "eda": "µS",
    "skin_temp": "°C",
    "spo2": "%",
    "temperature": "C",
    "sbp": "mmHg",
    "map": "mmHg",
    "dbp": "mmHg",
    "resp_rate": "breaths/min",
    "icu_los_hours": "hours",
    "sepsis_label": "binary",
}

# Accepted unit aliases per metric: alias -> multiplier to canonical unit.
UNIT_ALIASES = {
    "resting_hr": {"bpm": 1.0, "beats_per_minute": 1.0},
    "hrv_rmssd": {"ms": 1.0, "millisecond": 1.0, "s": 1000.0},
    "sleep_hours": {"h": 1.0, "hour": 1.0, "hours": 1.0, "min": 1.0 / 60.0, "s": 1.0 / 3600.0},
    "activity_load": {"index": 1.0, "points": 1.0, "steps": 0.01},
    "heart_rate": {"bpm": 1.0, "beats_per_minute": 1.0, "/min": 1.0, "beats/min": 1.0},
    "rr_sd": {"ms": 1.0, "millisecond": 1.0, "s": 1000.0},
    "eda": {"µS": 1.0, "uS": 1.0, "microsiemens": 1.0},
    "skin_temp": {"°C": 1.0, "C": 1.0, "celsius": 1.0, "K": 1.0},
    "spo2": {"%": 1.0, "percent": 1.0},
    "temperature": {"C": 1.0, "celsius": 1.0, "K": 1.0},
    "sbp": {"mmHg": 1.0},
    "map": {"mmHg": 1.0},
    "dbp": {"mmHg": 1.0},
    "resp_rate": {"breaths/min": 1.0, "bpm": 1.0},
    "icu_los_hours": {"hours": 1.0, "h": 1.0},
    "sepsis_label": {"binary": 1.0},
}


@dataclass(frozen=True)
class CanonicalObservation:
    patient_id: str
    timestamp: str  # normalized UTC ISO-8601, e.g. 2026-01-04T08:04:00+00:00
    source: str     # e.g. fhir, csv, json, wearable-api (required)
    metric: str
    value: float    # finite, in EXPECTED_UNITS[metric]
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


def normalize_timestamp(raw: object) -> str:
    """Parse ISO-8601 strictly and normalize to UTC.

    Naive timestamps are assumed UTC (documented, not guessed per-source).
    Date-only strings are accepted as midnight UTC. Raises ValueError on
    anything unparseable — including FHIR Period/Timing objects, which this
    pipeline does not accept as instants.
    """
    if not isinstance(raw, str):
        raise ValueError(f"timestamp must be a string, got {type(raw).__name__}")
    text = raw.strip()
    try:
        # datetime.fromisoformat always returns datetime (date-only input
        # becomes midnight); 'Z' suffix handled for pre-3.11-style strings.
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"unparseable timestamp {raw!r}; expected ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def validate_observation(raw: dict) -> tuple[CanonicalObservation | None, list[str]]:
    """Validate + normalize one raw observation dict. Never raises.

    Returns (observation, issues). Rejected with reasons: unknown metrics,
    unparseable timestamps, non-finite values, unknown units, out-of-range
    or non-numeric quality, missing patient_id, missing source. Nothing is
    clamped or defaulted except documented UTC assumption for naive times.
    """
    issues: list[str] = []
    if not isinstance(raw, dict):
        return None, ["observation must be an object"]
    metric = raw.get("metric")
    if metric not in METRICS:
        return None, [f"unknown metric {metric!r}; expected one of {list(METRICS)}"]
    try:
        timestamp = normalize_timestamp(raw.get("timestamp"))
    except ValueError as exc:
        return None, [str(exc)]
    try:
        value = float(raw.get("value"))
    except (TypeError, ValueError):
        return None, [f"non-numeric value for {metric!r}"]
    if not math.isfinite(value):
        return None, [f"non-finite value for {metric!r}: rejected, not normalized"]
    aliases = UNIT_ALIASES[metric]
    unit = raw.get("unit")
    if unit not in aliases:
        return None, [f"unknown unit {unit!r} for {metric!r}; expected one of {sorted(aliases)}"]
    try:
        quality = float(raw.get("quality", 1.0))
    except (TypeError, ValueError):
        return None, [f"non-numeric quality for {metric!r}: rejected, not defaulted"]
    if not math.isfinite(quality) or not 0.0 <= quality <= 1.0:
        return None, [f"quality {raw.get('quality')!r} out of range [0, 1]: rejected, not clamped"]
    patient_id = raw.get("patient_id")
    if not isinstance(patient_id, str) or not patient_id.strip():
        return None, ["missing patient_id"]
    source = raw.get("source")
    if not isinstance(source, str) or not source.strip():
        return None, ["missing source: provenance-first ingestion requires a named source"]
    return CanonicalObservation(
        patient_id=patient_id.strip(),
        timestamp=timestamp,
        source=source.strip(),
        metric=metric,
        value=value * aliases[unit],
        unit=EXPECTED_UNITS[metric],
        quality=quality,
        provenance=str(raw.get("provenance") or ""),
    ), issues


def normalize_batch(raw_items: list[dict]) -> tuple[list[CanonicalObservation], list[str]]:
    """Validate a batch; returns (accepted, issues). Rejects never abort the batch."""
    accepted, decisions = ingest_batch(raw_items, batch_id="", source_id="")
    issues = [f"[{i}] {reason}"
              for i, d in enumerate(decisions) if d["decision"] == "rejected"
              for reason in d["reasons"]]
    return accepted, issues


def ingest_batch(raw_items: list[dict], batch_id: str = "",
                 source_id: str = "") -> tuple[list[CanonicalObservation], list[dict]]:
    """Ingest with a complete per-item decision trail (Phase 1 auditability).

    Every input produces exactly one decision record:
    {batch_id, source, observation_id (or null), decision, reasons}.
    Duplicates (same observation_id twice in one batch) are rejected as
    duplicates — never silently double-counted.
    """
    accepted: list[CanonicalObservation] = []
    decisions: list[dict] = []
    if not isinstance(raw_items, list):
        return [], [{"batch_id": batch_id, "source": source_id,
                     "observation_id": None, "decision": "rejected",
                     "reasons": ["batch must be a list"]}]
    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        obs, problems = validate_observation(raw)
        if obs is None:
            decisions.append({
                "batch_id": batch_id,
                "source": source_id or (raw.get("source") if isinstance(raw, dict) else ""),
                "observation_id": None,
                "decision": "rejected",
                "reasons": problems,
            })
            continue
        oid = observation_id(obs)
        if oid in seen:
            decisions.append({
                "batch_id": batch_id, "source": source_id or obs.source,
                "observation_id": oid, "decision": "rejected",
                "reasons": [f"duplicate of item already accepted in batch {batch_id or index}"],
            })
            continue
        seen.add(oid)
        accepted.append(obs)
        decisions.append({
            "batch_id": batch_id, "source": source_id or obs.source,
            "observation_id": oid, "decision": "accepted", "reasons": [],
        })
    return accepted, decisions


def observation_id(obs: CanonicalObservation) -> str:
    """Deterministic immutable identity: SHA-256 over the canonical record."""
    import hashlib as _hashlib
    import json as _json

    canonical = _json.dumps(
        {"patient_id": obs.patient_id, "timestamp": obs.timestamp,
         "source": obs.source, "metric": obs.metric, "value": obs.value,
         "unit": obs.unit, "quality": obs.quality, "provenance": obs.provenance},
        sort_keys=True, separators=(",", ":"),
    )
    return _hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Revision:
    """A correction creates a new immutable record; nothing is mutated.

    revision_id is deterministic over (superseded id, new observation,
    reason). revised_at is wall-clock metadata, excluded from the id so
    identical corrections reproduce identical ids.
    """
    supersedes_id: str
    observation: CanonicalObservation
    reason: str
    revised_at: str = ""
    revision_id: str = ""

    def __post_init__(self):
        import hashlib as _hashlib
        import json as _json

        if not self.revision_id:
            canonical = _json.dumps(
                {"supersedes": self.supersedes_id,
                 "observation": self.observation.to_dict(),
                 "reason": self.reason},
                sort_keys=True, separators=(",", ":"),
            )
            object.__setattr__(
                self, "revision_id",
                _hashlib.sha256(canonical.encode("utf-8")).hexdigest())
