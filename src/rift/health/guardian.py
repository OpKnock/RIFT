"""Healthcare Guardian: is this result safe to DISPLAY as decision support?

Guardian never diagnoses, never treats, never overrides a clinician. It
verifies display-safety: impossible physiology and invalid transitions
REJECT (result must not be shown as trustworthy); missing/stale/uncertain
inputs FLAG (result shown with explicit warnings).
"""
from __future__ import annotations

import json as _json

from .models import PHYSIOLOGICAL_BOUNDS, PatientState
from .risk import STRAIN_THRESHOLD

MAX_PLAUSIBLE_DAILY_HR_SHIFT = 30.0  # bpm/day beyond which a transition is rejected
STALE_FLAG_DAYS = 3
UNCERTAINTY_FLAG = 0.35
ALLOWED_OUTPUT_KEYS = {
    "target", "horizon", "risk", "event_predicted", "threshold",
    "contributions", "input_quality", "measurement_jitter", "uncertainty",
    "interval", "model", "calibration",
}

IMPOSSIBLE_MESSAGES = {
    "resting_hr": "resting HR outside plausible human range",
    "hrv_rmssd": "HRV outside plausible human range",
    "sleep_hours": "sleep hours outside 0-24 h",
    "activity_load": "activity load outside demo index range",
    "age": "age outside plausible human range",
}


def check_state(state: PatientState, previous: PatientState | None = None) -> dict:
    """Display-safety verdict for one synchronized twin state."""
    rejections: list[str] = []
    flags: list[str] = []
    for field, message in IMPOSSIBLE_MESSAGES.items():
        if field == "age":
            continue
        value = getattr(state, field, None)
        if value is None:
            continue
        lo, hi = PHYSIOLOGICAL_BOUNDS[field]
        if not (lo <= value <= hi):
            rejections.append(f"{message}: {value}")
    missing = [f for f in ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")
               if getattr(state, f) is None]
    if missing:
        flags.append(f"missing wearable fields: {', '.join(missing)} (baseline-imputed downstream)")
    if state.stale_days >= STALE_FLAG_DAYS:
        flags.append(f"wearable data stale by {state.stale_days} days: treat trend as uncertain")
    if previous is not None and state.resting_hr is not None and previous.resting_hr is not None:
        shift = abs(state.resting_hr - previous.resting_hr)
        if shift > MAX_PLAUSIBLE_DAILY_HR_SHIFT:
            rejections.append(f"resting HR shifted {shift:.1f} bpm in one day: implausible transition")
    return {"rejections": rejections, "flags": flags}


def check_prediction(risk_record: dict) -> dict:
    """Display-safety verdict for one risk prediction."""
    rejections: list[str] = []
    flags: list[str] = []
    unexpected = set(risk_record) - ALLOWED_OUTPUT_KEYS
    if unexpected:
        rejections.append(f"prediction carries unsupported output fields: {sorted(unexpected)}")
    if "prescription" in json_text(risk_record).lower() or "dosage" in json_text(risk_record).lower():
        rejections.append("prediction output must never contain treatment instructions")
    uncertainty = risk_record.get("uncertainty", 0.0) or 0.0
    if uncertainty > UNCERTAINTY_FLAG:
        flags.append(f"uncertainty {uncertainty:.2f} exceeds display threshold: show interval, not a point estimate")
    if risk_record.get("input_quality", 1.0) < 0.5:
        flags.append("input quality below 0.5: prediction is indicative only")
    return {"rejections": rejections, "flags": flags}


def json_text(record: dict) -> str:
    try:
        return _json.dumps(record, sort_keys=True)
    except (TypeError, ValueError):
        return ""


def check_population(ehr) -> dict:
    """Out-of-distribution scope check. The demo weights assume adults."""
    flags: list[str] = []
    age = getattr(ehr, "age", None) if ehr is not None else None
    if age is not None and (age < 18 or age > 90):
        flags.append(f"age {age:.0f} is outside the adult demo scope (18-90): treat output as out-of-distribution")
    return {"rejections": [], "flags": flags}


def verdict(state: PatientState, risk_record: dict, previous: PatientState | None = None, ehr=None) -> dict:
    """Combined verdict. display_allowed is False when any rejection exists."""
    state_check = check_state(state, previous)
    pred_check = check_prediction(risk_record)
    pop_check = check_population(ehr)
    rejections = state_check["rejections"] + pred_check["rejections"] + pop_check["rejections"]
    flags = state_check["flags"] + pred_check["flags"] + pop_check["flags"]
    return {
        "display_allowed": not rejections,
        "rejections": rejections,
        "flags": flags,
        "scope": "display-safety for decision support; not a clinical authority",
    }
