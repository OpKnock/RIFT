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
    "hr_slope_per_bpm_per_day": 0.015,  # velocity: rising HR adds risk
    "sleep_worsening_per_hour": 0.03,   # velocity: shrinking sleep adds risk
    "trend_cap": 0.15,                  # total velocity contribution cap
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


def drivers(
    state: PatientState,
    baseline: PersonalBaseline,
    trend: dict[str, float | None] | None = None,
) -> tuple[float, list[dict]]:
    """Dynamic wearable-derived drivers + per-factor contributions.

    trend (from wearable.trend_terms) adds a bounded velocity term: only
    deterioration counts (rising HR, shrinking sleep); recoveries add
    nothing. Callers without history pass None and get level-only drivers
    (used by multi-day trajectory rollout — documented in foresight).
    """
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
    trend = trend or {}
    trend_total = 0.0
    hr_slope = trend.get("hr_slope")
    if hr_slope is not None and hr_slope > 0:
        trend_total += w["hr_slope_per_bpm_per_day"] * hr_slope
    sleep_delta = trend.get("sleep_delta")
    if sleep_delta is not None and sleep_delta < 0:
        trend_total += w["sleep_worsening_per_hour"] * abs(sleep_delta)
    trend_total = min(w["trend_cap"], trend_total)
    if trend_total > 0:
        total += trend_total
        parts.append({"factor": "deteriorating 24h trend (HR rising / sleep shrinking)", "value": trend_total})
    return total, parts


def input_quality(state: PatientState) -> float:
    """0..1 from the state itself: field completeness discounted by staleness.

    Derived from present fields rather than any stored score, so degraded
    or tampered states always score honestly.
    """
    present = sum(1 for f in ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")
                  if getattr(state, f) is not None)
    freshness = 1.0 / (1.0 + max(0, state.stale_days))
    return max(0.0, min(1.0, (present / 4.0) * freshness))


JITTER_WEIGHT = 0.15  # synthetic: uncertainty added per unit of measured jitter


def predict(
    state: PatientState,
    baseline: PersonalBaseline,
    ehr: EHRRecord,
    measurement_jitter: float = 0.0,
    trend: dict[str, float | None] | None = None,
) -> dict:
    """Risk record with horizon, contributions, quality, and uncertainty.

    measurement_jitter (0..1, from wearable.jitter_score) widens the
    interval: fast day-over-day fluctuation — whether sensor noise or a
    genuine shock — means the point estimate is less trustworthy.
    trend (from wearable.trend_terms) adds a bounded velocity term so
    deterioration in progress scores higher than a static snapshot.
    """
    base, base_parts = susceptibility(ehr)
    drive, drive_parts = drivers(state, baseline, trend)
    risk = _clamp01(base + drive)
    quality = input_quality(state)
    jitter = max(0.0, min(1.0, measurement_jitter))
    # Uncertainty widens as inputs degrade; spread from robustness is added
    # later by the twin (see robustness.spread_uncertainty).
    uncertainty = max(0.0, min(0.45, 0.05 + 0.30 * (1.0 - quality) + JITTER_WEIGHT * jitter))
    return {
        "target": "high cardiac-strain day",
        "horizon": HORIZON_LABEL,
        "risk": risk,
        "event_predicted": risk >= STRAIN_THRESHOLD,
        "threshold": STRAIN_THRESHOLD,
        "contributions": base_parts + drive_parts,
        "input_quality": quality,
        "measurement_jitter": jitter,
        "trend_terms": {k: v for k, v in (trend or {}).items()},
        "uncertainty": uncertainty,
        "interval": [max(0.0, risk - uncertainty), min(1.0, risk + uncertainty)],
        "calibration": "demo / not calibrated",
        "model": "transparent additive demo weights (synthetic, not validated)",
    }
