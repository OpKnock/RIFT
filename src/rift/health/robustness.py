"""Healthcare robustness: sensor/parameter perturbations + spread uncertainty.

Reuses rift.robust / rift.adversarial on the FORESIGHT scenario. Adds
healthcare-relevant data degradations (dropout, staleness, noise, bias,
temporal shift, correlated dropout) whose effect is to widen uncertainty,
never to silently substitute values.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from ..robust import rank_robust_candidates
from .foresight import HEALTH_PERTURBATIONS, patient_scenario
from .models import PatientState, PersonalBaseline
from .ehr import EHRRecord
from .wearable import FIELDS


# ---- Core degradations (deterministic, seeded) ----

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


def degrade_biased(state: PatientState, seed: int = 7, bias: dict[str, float] | None = None) -> PatientState:
    """Simulate systematic sensor bias (e.g., wrist HR reads +5 bpm high)."""
    rng = random.Random(seed)
    d = state.to_dict()
    bias = bias or {"resting_hr": 5.0, "hrv_rmssd": -5.0, "sleep_hours": 0.5, "activity_load": 0.2}
    for field, b in bias.items():
        value = d.get(field)
        if value is not None:
            d[field] = value + b * (1.0 + 0.1 * (rng.random() * 2 - 1))
    return PatientState(**d)


def degrade_temporal_shift(state: PatientState, seed: int = 7, hours: int = 2) -> PatientState:
    """Simulate circadian phase shift (e.g., night shift worker data)."""
    rng = random.Random(seed)
    d = state.to_dict()
    # Sleep phase shift: HR typically lower at night, HRV higher
    if d.get("sleep_hours") is not None:
        shift_factor = 1.0 + 0.02 * hours * (rng.random() * 2 - 1)
        d["resting_hr"] = d.get("resting_hr", 70.0) * shift_factor
        d["hrv_rmssd"] = d.get("hrv_rmssd", 50.0) / shift_factor
    d["activity_load"] = max(0.0, d.get("activity_load", 0.0) * (1.0 - 0.1 * hours / 12.0))
    return PatientState(**d)


def degrade_correlated_dropout(state: PatientState, seed: int = 7, p: float = 0.3) -> PatientState:
    """Simulate correlated sensor failure (e.g., wrist device off → HR + HRV + sleep all missing)."""
    rng = random.Random(seed)
    d = state.to_dict()
    if rng.random() < p:
        for field in ("resting_hr", "hrv_rmssd", "sleep_hours"):
            d[field] = None
        d["activity_load"] = d.get("activity_load", 0.0)  # step count often survives
        d["data_quality"] = max(0.0, d.get("data_quality", 1.0) - 0.5)
    return PatientState(**d)


# ---- Combinatorial degradation suites ----

@dataclass(frozen=True)
class DegradationSuite:
    """Named set of degradations for systematic robustness testing."""
    name: str
    degradations: list[Callable[[PatientState], PatientState]]

# Pre-defined suites matching clinical failure modes
DEGRADATION_SUITES = {
    "sensor_dropout": DegradationSuite("sensor_dropout", [
        lambda s: degrade_missing(s, "resting_hr"),
        lambda s: degrade_missing(s, "hrv_rmssd"),
        lambda s: degrade_missing(s, "sleep_hours"),
        lambda s: degrade_missing(s, "activity_load"),
    ]),
    "stale_data": DegradationSuite("stale_data", [
        lambda s: degrade_stale(s, 3),
        lambda s: degrade_stale(s, 7),
        lambda s: degrade_stale(s, 14),
    ]),
    "sensor_noise": DegradationSuite("sensor_noise", [
        lambda s: degrade_noisy(s, magnitude=0.02),
        lambda s: degrade_noisy(s, magnitude=0.05),
        lambda s: degrade_noisy(s, magnitude=0.10),
    ]),
    "systematic_bias": DegradationSuite("systematic_bias", [
        lambda s: degrade_biased(s, bias={"resting_hr": 5.0}),
        lambda s: degrade_biased(s, bias={"hrv_rmssd": -10.0}),
        lambda s: degrade_biased(s, bias={"sleep_hours": 1.5}),
    ]),
    "temporal_shift": DegradationSuite("temporal_shift", [
        lambda s: degrade_temporal_shift(s, hours=2),
        lambda s: degrade_temporal_shift(s, hours=6),
        lambda s: degrade_temporal_shift(s, hours=12),
    ]),
    "correlated_dropout": DegradationSuite("correlated_dropout", [
        lambda s: degrade_correlated_dropout(s, p=0.2),
        lambda s: degrade_correlated_dropout(s, p=0.5),
        lambda s: degrade_correlated_dropout(s, p=0.8),
    ]),
    "combined_realistic": DegradationSuite("combined_realistic", [
        lambda s: degrade_noisy(s, magnitude=0.03),
        lambda s: degrade_stale(s, extra_days=2),
        lambda s: degrade_biased(s, bias={"resting_hr": 3.0}),
    ]),
}


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


def run_suite(state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord,
              suite_name: str) -> dict:
    """Run a degradation suite and return aggregated robustness metrics."""
    if suite_name not in DEGRADATION_SUITES:
        raise KeyError(f"unknown suite {suite_name!r}")
    suite = DEGRADATION_SUITES[suite_name]
    results = []
    for degrade in suite.degradations:
        degraded = degrade(state)
        report = robustness_report(degraded, baseline, ehr)
        results.append({
            "degradation": degrade.__name__ if hasattr(degrade, "__name__") else "lambda",
            "worst_case_spread": report["worst_case_spread"],
            "ranking": report["ranking"],
        })
    max_spread = max(r["worst_case_spread"] for r in results) if results else 0.0
    return {
        "suite": suite_name,
        "n_degradations": len(results),
        "max_spread": max_spread,
        "details": results,
    }


def run_all_suites(state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord) -> dict:
    """Run all predefined degradation suites."""
    return {name: run_suite(state, baseline, ehr, name) for name in DEGRADATION_SUITES}


def combine_uncertainty(base_uncertainty: float, spread: float) -> float:
    """Total uncertainty: base (quality-driven) plus robustness spread."""
    return max(0.0, min(0.45, base_uncertainty + spread / 2))
