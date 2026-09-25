"""Ingestion adapters: FHIR / CSV / JSON → CanonicalObservation lists.

Each adapter parses its format and delegates all validation to
observations.normalize_batch, so every source faces identical checks.
No adapter invents values: unparseable rows are reported, never filled.
"""
from __future__ import annotations

import csv
import json
import math

from .observations import EXPECTED_UNITS, normalize_batch
from .terminology import (
    LOINC_MAP,
    RESTING_CONTEXT_CODES,
    TERMINOLOGY_VERSION as FHIR_TERMINOLOGY_VERSION,
)

# Back-compat alias: (metric, units) view of the versioned registry.
# New code should use terminology.mapping_status() directly.
FHIR_LOINC_MAP = {code: (metric, units) for code, (metric, units, *_rest) in LOINC_MAP.items()}


def _fhir_patient(ref: object) -> str | None:
    if isinstance(ref, dict) and isinstance(ref.get("reference"), str):
        return ref["reference"].split("/")[-1] or None
    if isinstance(ref, str):
        return ref.split("/")[-1] or None
    return None


def _resting_context(res: dict) -> bool:
    """True when the resource explicitly asserts a resting measurement context."""
    haystacks: list[str] = []
    body_position = res.get("bodyPosition")
    if isinstance(body_position, dict):
        for coding in (body_position.get("coding") or []):
            if isinstance(coding, dict):
                haystacks.extend(str(coding.get(k, "")) for k in ("code", "display"))
    for interp in res.get("interpretation") or []:
        if isinstance(interp, dict):
            for coding in (interp.get("coding") or []):
                if isinstance(coding, dict):
                    haystacks.extend(str(coding.get(k, "")) for k in ("code", "display"))
    text = " ".join(haystacks).lower().replace("_", "-")
    return any(code.lower() in text for code in RESTING_CONTEXT_CODES)


def _structured_provenance(res: dict, loinc: str | None, raw_unit: object, raw_value: object,
                           ingested_via: str = "fhir") -> str:
    """Preserve auditable FHIR context as JSON instead of one opaque string."""
    return json.dumps({
        "adapter": "fhir",
        "ingested_via": ingested_via,
        "terminology": FHIR_TERMINOLOGY_VERSION,
        "resource_id": res.get("id"),
        "loinc": loinc,
        "original_unit": raw_unit,
        "original_value": raw_value,
        "effective": res.get("effectiveDateTime") or res.get("issued"),
        "patient_reference": (res.get("subject") or {}).get("reference")
        if isinstance(res.get("subject"), dict) else res.get("subject"),
    }, sort_keys=True)


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
        raw_value = quantity.get("value")
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            issues.append(f"[{index}] skipped: non-numeric valueQuantity")
            continue
        if not math.isfinite(value):
            issues.append(f"[{index}] skipped: non-finite valueQuantity")
            continue
        unit = quantity.get("unit") or quantity.get("code")
        if unit not in units:
            issues.append(f"[{index}] skipped: unsupported UCUM unit {unit!r}")
            continue
        timestamp = res.get("effectiveDateTime") or res.get("effectiveInstant")
        if isinstance(timestamp, dict):
            issues.append(f"[{index}] skipped: Period/Timing effective not supported, need a single instant")
            continue
        if not isinstance(timestamp, str) or "T" not in timestamp:
            # issued is resource availability time, NOT observation time —
            # substituting it would mislabel clinical timing, so reject.
            issues.append(f"[{index}] skipped: missing effectiveDateTime/effectiveInstant (issued is not a substitute)")
            continue
        patient_id = _fhir_patient(res.get("subject"))
        if not patient_id:
            issues.append(f"[{index}] skipped: missing subject reference")
            continue
        # 8867-4 is generic heart rate: only an explicit resting context on
        # the resource justifies recording it as resting_hr.
        if loinc == "8867-4" and _resting_context(res):
            metric = "resting_hr"
        raw.append({
            "patient_id": patient_id,
            "timestamp": timestamp,
            "source": "fhir",
            "metric": metric,
            "value": value * units[unit],
            "unit": EXPECTED_UNITS[metric],
            "quality": 1.0,
            "provenance": _structured_provenance(res, loinc, unit, raw_value, provenance),
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
