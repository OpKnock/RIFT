"""Explainability: every prediction ships human-readable reasons."""
from __future__ import annotations

from .baseline import PersonalBaseline
from .ehr import EHRRecord
from .models import Deviation, PatientState


def build_reasons(
    state: PatientState,
    baseline: PersonalBaseline,
    deviations: list[Deviation],
    ehr: EHRRecord,
    risk_record: dict,
    guardian_verdict: dict,
    trajectory_note: str = "",
) -> list[str]:
    """Ordered reasons a clinician can scan: trajectory, baseline, EHR,
    wearables, causal contributors, quality/uncertainty, Guardian."""
    reasons: list[str] = []
    contributions = sorted(risk_record.get("contributions", []), key=lambda c: -abs(c.get("value", 0.0)))
    top = [c for c in contributions if abs(c.get("value", 0.0)) >= 0.01][:3]
    if top:
        reasons.append(
            "Top risk contributors: " + "; ".join(f"{c['factor']} (+{c['value']:.2f})" for c in top) + "."
        )
    for dev in deviations:
        if dev.direction == "unknown" or dev.delta is None:
            reasons.append(f"{dev.field.replace('_', ' ')} has no usable baseline comparison (missing data).")
        elif dev.field == "resting_hr" and dev.direction == "above":
            reasons.append(f"Resting HR {dev.current:.0f} bpm sits {dev.delta:.1f} above your personal baseline ({dev.baseline:.0f}).")
        elif dev.field == "hrv_rmssd" and dev.direction == "below":
            reasons.append(f"HRV {dev.current:.0f} ms sits {abs(dev.delta):.1f} below your personal baseline ({dev.baseline:.0f}).")
        elif dev.field == "sleep_hours" and dev.direction == "below":
            reasons.append(f"Sleep {dev.current:.1f} h is {abs(dev.delta):.1f} h under your usual {dev.baseline:.1f} h.")
    if ehr.conditions:
        reasons.append(f"EHR susceptibility factors: {', '.join(ehr.conditions)}.")
    if trajectory_note:
        reasons.append(trajectory_note)
    quality = risk_record.get("input_quality", 1.0)
    uncertainty = risk_record.get("uncertainty", 0.0)
    reasons.append(f"Input quality {quality:.2f}; uncertainty ±{uncertainty:.2f} (interval shown, not certainty).")
    for flag in guardian_verdict.get("flags", []):
        reasons.append(f"Guardian note: {flag}")
    for rejection in guardian_verdict.get("rejections", []):
        reasons.append(f"Guardian REJECTION: {rejection}")
    return reasons
