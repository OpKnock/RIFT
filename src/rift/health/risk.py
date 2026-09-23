"""Short-horizon adverse-event predictor: next-24h cardiac-strain risk.

TARGET (narrow, demoable): will tomorrow be a high-strain day
(risk >= STRAIN_THRESHOLD)? Transparent additive score, never a diagnosis.
Contributions, horizon, input quality, and uncertainty ship with every
prediction for the explainability layer.
"""
from __future__ import annotations

from .baseline import PersonalBaseline
from .ehr import EHRRecord
from .models import PatientState

HORIZON_LABEL = "24h"
STRAIN_THRESHOLD = 0.6

RISK_WEIGHTS = {
    "base": 0.10,
    "age_per_year_over_40": 0.004,
    "hypertension": 0.08,
    "type_2_diabetes": 0.05,
    "beta_blocker_relief": -0.06,
    "hr_per_bpm_over_baseline": 0.012,
    "hrv_per_ms_under_40": 0.006,
    "sleep_per_hour_debt": 0.05,
    "activity_per_point_over_60": 0.002,
    "hrv_low_reference": 40.0,
}


def _clamp01(value: float) -> float:
    return max(0.01, min(0.99, value))


def susceptibility(ehr: EHRRecord) -> tuple[float, list[dict]]:
    """Static EHR-derived susceptibility + per-factor contributions."""
    w = RISK_WEIGHTS
    total = w["base"]
    parts = [{"factor": "base susceptibility", "value": w["base"]}]
    if ehr.age is not None and ehr.age > 40:
        term = w["age_per_year_over_40"] * (ehr.age - 40)
        total += term
        parts.append({"factor": f"age {ehr.age:.0f}", "value": term})
    if "hypertension" in ehr.conditions:
        total += w["hypertension"]
        parts.append({"factor": "hypertension history", "value": w["hypertension"]})
    if "type_2_diabetes" in ehr.conditions:
        total += w["type_2_diabetes"]
        parts.append({"factor": "type 2 diabetes history", "value": w["type_2_diabetes"]})
    if "beta_blocker" in ehr.medications:
        total += w["beta_blocker_relief"]
        parts.append({"factor": "beta blocker (blunts HR response)", "value": w["beta_blocker_relief"]})
    return total, parts


def drivers(state: PatientState, baseline: PersonalBaseline) -> tuple[float, list[dict]]:
    """Dynamic wearable-derived drivers + per-factor contributions."""
    w = RISK_WEIGHTS
    total = 0.0
    parts: list[dict] = []
    ref_hr = baseline.resting_hr if baseline.resting_hr is not None else 70.0
    if state.resting_hr is not None:
        over = max(0.0, state.resting_hr - ref_hr)
        term = w["hr_per_bpm_over_baseline"] * over
        total += term
        parts.append({"factor": f"resting HR {state.resting_hr:.0f} vs baseline {ref_hr:.0f}", "value": term})
    if state.hrv_rmssd is not None:
        under = max(0.0, w["hrv_low_reference"] - state.hrv_rmssd)
        term = w["hrv_per_ms_under_40"] * under
        total += term
        parts.append({"factor": f"HRV {state.hrv_rmssd:.0f} ms vs {w['hrv_low_reference']:.0f} ms reference", "value": term})
    if state.sleep_hours is not None:
        debt = max(0.0, 7.0 - state.sleep_hours)
        term = w["sleep_per_hour_debt"] * debt
        total += term
        parts.append({"factor": f"sleep debt {debt:.1f} h", "value": term})
    if state.activity_load is not None:
        excess = max(0.0, state.activity_load - 60.0)
        term = w["activity_per_point_over_60"] * excess
        total += term
        parts.append({"factor": f"exertion {excess:.0f} pts over reference", "value": term})
    return total, parts


def input_quality(state: PatientState) -> float:
    """0..1: field completeness discounted by staleness."""
    freshness = 1.0 / (1.0 + max(0, state.stale_days))
    return max(0.0, min(1.0, state.data_quality * freshness))


def predict(state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord) -> dict:
    """Risk record with horizon, contributions, quality, and uncertainty."""
    base, base_parts = susceptibility(ehr)
    drive, drive_parts = drivers(state, baseline)
    risk = _clamp01(base + drive)
    quality = input_quality(state)
    # Uncertainty widens as inputs degrade; spread from robustness is added
    # later by the twin (see robustness.spread_uncertainty).
    uncertainty = max(0.0, min(0.45, 0.05 + 0.30 * (1.0 - quality)))
    return {
        "target": "high cardiac-strain day",
        "horizon": HORIZON_LABEL,
        "risk": risk,
        "event_predicted": risk >= STRAIN_THRESHOLD,
        "threshold": STRAIN_THRESHOLD,
        "contributions": base_parts + drive_parts,
        "input_quality": quality,
        "uncertainty": uncertainty,
        "interval": [max(0.0, risk - uncertainty), min(1.0, risk + uncertainty)],
        "model": "transparent additive demo weights (synthetic, not validated)",
    }
