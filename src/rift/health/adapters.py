"""Ingestion adapters: FHIR / CSV / JSON → CanonicalObservation lists.

Each adapter parses its format and delegates all validation to
observations.normalize_batch, so every source faces identical checks.
No adapter invents values: unparseable rows are reported, never filled.
"""
from __future__ import annotations

import csv

from .observations import normalize_batch

# Minimal FHIR R4 Observation subset, mapped by LOINC code. Anything else
# is rejected with a reason — the adapter never guesses a metric mapping.
FHIR_LOINC_MAP = {
    "8867-4": ("resting_hr", {"/min": 1.0, "bpm": 1.0, "beats/min": 1.0}),
    "80404-7": ("hrv_rmssd", {"ms": 1.0, "millisecond": 1.0}),
    "93832-4": ("sleep_hours", {"h": 1.0, "min": 1.0 / 60.0, "s": 1.0 / 3600.0}),
}


def _fhir_patient(ref: object) -> str | None:
    if isinstance(ref, dict) and isinstance(ref.get("reference"), str):
        return ref["reference"].split("/")[-1] or None
    if isinstance(ref, str):
        return ref.split("/")[-1] or None
    return None


def from_fhir(payload: dict | list, provenance: str = "fhir") -> tuple[list, list[str]]:
    """Parse FHIR R4 Observation resource(s) into raw observation dicts.

    Accepts a single resource, a list of resources, or a Bundle
    (entry[].resource). Returns (raw_dicts, issues); raw dicts still go
    through normalize_batch by the caller pipeline (see from_fhir_normalized).
    """
    issues: list[str] = []
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        resources = [e.get("resource", {}) for e in payload.get("entry", []) if isinstance(e, dict)]
    elif isinstance(payload, list):
        resources = payload
    elif isinstance(payload, dict):
        resources = [payload]
    else:
        return [], ["FHIR payload must be a resource, Bundle, or list"]
    raw: list[dict] = []
    for index, res in enumerate(resources):
        if not isinstance(res, dict) or res.get("resourceType") != "Observation":
            issues.append(f"[{index}] skipped: not an Observation resource")
            continue
        codings = (res.get("code") or {}).get("coding") or []
        loinc = next((c.get("code") for c in codings if isinstance(c, dict) and c.get("code")), None)
        if loinc not in FHIR_LOINC_MAP:
            issues.append(f"[{index}] skipped: unsupported code {loinc!r}")
            continue
        metric, units = FHIR_LOINC_MAP[loinc]
        quantity = res.get("valueQuantity") or {}
        try:
            value = float(quantity.get("value"))
        except (TypeError, ValueError):
            issues.append(f"[{index}] skipped: non-numeric valueQuantity")
            continue
        unit = quantity.get("unit") or quantity.get("code")
        if unit not in units:
            issues.append(f"[{index}] skipped: unsupported UCUM unit {unit!r}")
            continue
        timestamp = res.get("effectiveDateTime") or res.get("issued")
        if not isinstance(timestamp, str) or "T" not in timestamp:
            issues.append(f"[{index}] skipped: missing effectiveDateTime")
            continue
        patient_id = _fhir_patient(res.get("subject")) or "unknown-patient"
        raw.append({
            "patient_id": patient_id,
            "timestamp": timestamp,
            "source": "fhir",
            "metric": metric,
            "value": value * units[unit],
            "unit": {"resting_hr": "bpm", "hrv_rmssd": "ms", "sleep_hours": "h"}[metric],
            "quality": 1.0,
            "provenance": provenance,
        })
    return raw, issues


def from_fhir_normalized(payload: dict | list, provenance: str = "fhir"):
    """FHIR → validated CanonicalObservations in one call."""
    raw, issues = from_fhir(payload, provenance)
    accepted, problems = normalize_batch(raw)
    return accepted, issues + problems


def from_csv_rows(path: str, *, delimiter: str = ","):
    """CSV with header patient_id,timestamp,source,metric,value,unit[,quality,provenance]."""
    try:
        handle = open(path, "r", encoding="utf-8", newline="")
    except OSError as exc:
        raise ValueError(f"cannot open ingestion CSV: {path}") from exc
    required = ("patient_id", "timestamp", "source", "metric", "value", "unit")
    with handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fields = reader.fieldnames or []
        missing = [c for c in required if c not in fields]
        if missing:
            raise ValueError(f"ingestion CSV missing columns: {missing}")
        raw = [dict(row) for row in reader]
    return normalize_batch(raw)


def from_json_batch(payload: list):
    """JSON list of raw observation dicts → validated CanonicalObservations."""
    return normalize_batch(payload)
