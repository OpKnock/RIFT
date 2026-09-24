"""Versioned clinical terminology registry (LOINC subset).

Mappings from external codes to canonical metrics live here — versioned,
reviewable, and testable — instead of hiding inside adapter code. Each
entry records its status: supported mappings are enforced by tests;
anything else must be added deliberately, never guessed.
"""
from __future__ import annotations

TERMINOLOGY_VERSION = "LOINC 2.83 (2026-08-19)"

# LOINC code -> (canonical metric, {unit: multiplier}, status, note).
# Statuses: "supported" (pinned by regression tests) or "withheld"
# (known code, deliberately unmapped until semantics are verified).
LOINC_MAP: dict[str, tuple[str, dict[str, float], str, str]] = {
    "8867-4": (
        "heart_rate",
        {"/min": 1.0, "bpm": 1.0, "beats/min": 1.0},
        "supported",
        "generic Heart rate; never resting_hr without explicit resting context",
    ),
    "80404-7": (
        "rr_sd",
        {"ms": 1.0, "millisecond": 1.0, "s": 1000.0},
        "supported",
        "R-R interval standard deviation; not RMSSD",
    ),
    "93832-4": (
        "sleep_hours",
        {"h": 1.0, "min": 1.0 / 60.0, "s": 1.0 / 3600.0},
        "supported",
        "Sleep duration",
    ),
}

# FHIR codings asserting a resting measurement context, allowing 8867-4
# to be recorded as resting_hr instead of generic heart_rate.
RESTING_CONTEXT_CODES = frozenset({
    "supine", "lying", "recumbent", "resting", "at-rest", "LAEQ",
})


def mapping_status(loinc: str | None) -> dict:
    """Reviewable status for one code: mapped metric or explicit rejection reason."""
    entry = LOINC_MAP.get(loinc or "")
    if entry is None:
        return {"loinc": loinc, "status": "unmapped",
                "reason": "no verified mapping; rejected, never guessed",
                "terminology": TERMINOLOGY_VERSION}
    metric, units, status, note = entry
    return {"loinc": loinc, "metric": metric, "units": sorted(units),
            "status": status, "note": note,
            "terminology": TERMINOLOGY_VERSION}
