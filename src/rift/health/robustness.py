"""Healthcare robustness: sensor/parameter perturbations + spread uncertainty.

Reuses rift.robust / rift.adversarial on the FORESIGHT scenario. Adds
healthcare-relevant data degradations (dropout, staleness, noise) whose
effect is to widen uncertainty, never to silently substitute values.
"""
from __future__ import annotations

import random

from ..robust import rank_robust_candidates
from .foresight import HEALTH_PERTURBATIONS, patient_scenario
from .models import PatientState, PersonalBaseline
from .ehr import EHRRecord
from .wearable import FIELDS


def degrade_missing(state: PatientState, field: str) -> PatientState:
    """Simulate sensor dropout for one field."""
    return PatientState(**{**state.to_dict(), field: None})


def degrade_stale(state: PatientState, extra_days: int = 3) -> PatientState:
    """Simulate stale wearable data."""
    d = state.to_dict()
    d["stale_days"] = d["stale_days"] + extra_days
    d["data_quality"] = max(0.0, d["data_quality"] - 0.2 * extra_days)
    return PatientState(**d)


def degrade_noisy(state: PatientState, seed: int = 7, magnitude: float = 0.05) -> PatientState:
    """Deterministic sensor noise (seeded; reproducible by construction)."""
    rng = random.Random(seed)  # nosec B311 -- reproducible test/demo noise, never a security boundary
    d = state.to_dict()
    for field in ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load"):
        value = d[field]
        if value is not None:
            d[field] = value * (1.0 + magnitude * (rng.random() * 2 - 1))
    return PatientState(**d)


def robustness_report(state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord) -> dict:
    """Rank intervention policies under health perturbations; spread widens uncertainty."""
    from ..counterfactual import generate_futures

    scenario, imputed = patient_scenario(state, baseline, ehr)
    futures = generate_futures(scenario)
    ranked = rank_robust_candidates(scenario, futures, HEALTH_PERTURBATIONS)
    worst_cases = [
        a.worst_case.adversarial_score for a in ranked if a.worst_case is not None
    ]
    spread = (max(worst_cases) - min(worst_cases)) / 2 if len(worst_cases) > 1 else 0.0
    return {
        "perturbations": HEALTH_PERTURBATIONS,
        "ranking": [
            {
                "policy": a.candidate.policy,
                "nominal_risk": a.candidate.score,
                "worst_case_risk": a.worst_case.adversarial_score if a.worst_case else a.candidate.score,
                "robustness_gap": a.robustness_gap,
                "feasible_under_all": a.feasible_under_all,
            }
            for a in ranked
        ],
        "worst_case_spread": spread,
        "imputed_fields": imputed,
    }


def combine_uncertainty(base_uncertainty: float, spread: float) -> float:
    """Total uncertainty: base (quality-driven) plus robustness spread."""
    return max(0.0, min(0.45, base_uncertainty + spread / 2))
