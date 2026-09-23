"""Bounded, interpretable patient-state transition model.

SYNTHETIC DEMO WEIGHTS — not physiology, not clinically validated. Every
coefficient lives in TRANSITION_WEIGHTS below so assumptions are explicit
and testable. The model maps (current vitals, EHR modifiers, intervention
deltas) to next-day vitals, clamped to PHYSIOLOGICAL_BOUNDS.

Interventions (binary, counterfactual-compatible):
- sleep_plus: +1.5 h sleep tonight
- exertion_cut: -35 activity-load points tomorrow
"""
from __future__ import annotations

from .ehr import EHRRecord
from .models import PHYSIOLOGICAL_BOUNDS

TRANSITION_WEIGHTS = {
    "hr_per_sleep_debt_hour": 0.8,     # bpm added per hour under 7 h sleep
    "hr_per_excess_activity": 0.03,    # bpm per activity point above 60
    "hr_beta_blocker_blunt": -2.0,     # bpm offset when on a beta blocker
    "hrv_per_sleep_debt_hour": -0.6,   # ms lost per hour under 7 h sleep
    "hrv_per_excess_activity": -0.02,  # ms lost per activity point above 60
    "hrv_recovery_rate": 0.05,         # pull toward HRV_SETPOINT per day
    "hrv_setpoint": 45.0,              # ms, synthetic population anchor
    "sleep_intervention_gain": 1.5,    # extra hours when sleep_plus=1
    "activity_intervention_cut": 35.0, # load removed when exertion_cut=1
    "activity_floor": 10.0,
    "sleep_reference": 7.0,            # hours; debt measured below this
    "activity_reference": 60.0,        # load; excess measured above this
}

INTERVENTIONS = ("sleep_plus", "exertion_cut")


def _clamp(field: str, value: float) -> float:
    lo, hi = PHYSIOLOGICAL_BOUNDS[field]
    return max(lo, min(hi, value))


def apply_policy(vitals: dict, policy: dict[str, int]) -> dict:
    """Apply a binary intervention policy to today's vitals pre-transition."""
    out = dict(vitals)
    if policy.get("sleep_plus"):
        out["sleep_hours"] = (out.get("sleep_hours") or 0.0) + TRANSITION_WEIGHTS["sleep_intervention_gain"]
    if policy.get("exertion_cut"):
        out["activity_load"] = max(
            TRANSITION_WEIGHTS["activity_floor"],
            (out.get("activity_load") or 0.0) - TRANSITION_WEIGHTS["activity_intervention_cut"],
        )
    return out


def transition(vitals: dict, ehr: EHRRecord, policy: dict[str, int] | None = None) -> dict:
    """Next-day vitals from today's vitals. Missing inputs propagate as None.

    Only resting_hr and hrv_rmssd evolve; sleep/activity persist (plus any
    policy deltas). All outputs are clamped to PHYSIOLOGICAL_BOUNDS.
    """
    w = TRANSITION_WEIGHTS
    current = apply_policy(vitals, policy or {})
    hr = current.get("resting_hr")
    hrv = current.get("hrv_rmssd")
    sleep = current.get("sleep_hours")
    activity = current.get("activity_load")

    on_beta_blocker = "beta_blocker" in (ehr.medications or ())
    sleep_debt = max(0.0, w["sleep_reference"] - sleep) if sleep is not None else 0.0
    excess_activity = max(0.0, activity - w["activity_reference"]) if activity is not None else 0.0

    if hr is None:
        next_hr = None
    else:
        next_hr = hr + w["hr_per_sleep_debt_hour"] * sleep_debt + w["hr_per_excess_activity"] * excess_activity
        if on_beta_blocker:
            next_hr += w["hr_beta_blocker_blunt"]
        next_hr = _clamp("resting_hr", next_hr)

    if hrv is None:
        next_hrv = None
    else:
        next_hrv = (
            hrv
            + w["hrv_per_sleep_debt_hour"] * sleep_debt
            + w["hrv_per_excess_activity"] * excess_activity
            + w["hrv_recovery_rate"] * (w["hrv_setpoint"] - hrv)
        )
        next_hrv = _clamp("hrv_rmssd", next_hrv)

    return {
        "resting_hr": next_hr,
        "hrv_rmssd": next_hrv,
        "sleep_hours": sleep,
        "activity_load": current.get("activity_load"),
    }
