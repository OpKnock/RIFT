"""FORESIGHT: future trajectories as an internal RIFT capability.

Reuses the generic engine directly:
- counterfactual futures via rift.counterfactual.generate_futures
- adversarial search via rift.adversarial.search_failure_states
- robust ranking via rift.robust.rank_robust_candidates
- independent checks via rift.verifier.verify_under_perturbations

Patient vitals are adapted to the generic Scenario (dict states, binary
intervention policies). Multi-day trajectory rollout steps the same
transition; it is presentation of the model, not a second engine.
"""
from __future__ import annotations

from ..adversarial import search_failure_states
from ..causal import CausalEdge, CausalGraph
from ..counterfactual import Future, generate_futures
from ..models import Constraint, Scenario
from ..robust import rank_robust_candidates
from ..verifier import verify_under_perturbations
from .ehr import EHRRecord
from .models import PHYSIOLOGICAL_BOUNDS, PatientState, PersonalBaseline
from .risk import drivers, susceptibility
from .transition import INTERVENTIONS, apply_policy, transition

HEALTH_PERTURBATIONS = [
    {"resting_hr": 5.0},
    {"hrv_rmssd": -8.0},
    {"sleep_hours": -1.5},
    {"activity_load": 25.0},
    {"resting_hr": 5.0, "activity_load": 25.0},
]

# Cold-start anchors used ONLY when neither current state nor personal
# baseline has a value (e.g. day 0, before any history exists). Synthetic
# constants, always reported in imputed_fields — never silent.
COLD_START_ANCHORS = {
    "resting_hr": 70.0,
    "hrv_rmssd": 45.0,
    "sleep_hours": 7.0,
    "activity_load": 40.0,
}


def _vitals_dict(state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord | None = None) -> tuple[dict, list[str]]:
    """Fill missing vitals: personal baseline → EHR clinic value → cold-start anchor.

    Every fallback is reported in imputed_fields so downstream consumers
    (Guardian, explainability, UI) can see what was measured vs filled.
    """
    out, imputed = {}, []
    for field in ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load"):
        value = getattr(state, field)
        if value is None:
            value = getattr(baseline, field)
            if value is not None:
                imputed.append(field)
        if value is None and ehr is not None and field == "resting_hr":
            value = ehr.resting_hr_clinic
            if value is not None:
                imputed.append(field + ":ehr-clinic")
        if value is None:
            value = COLD_START_ANCHORS[field]
            imputed.append(field + ":anchor")
        out[field] = value
    return out, imputed


def _risk_cost(vitals: dict, ehr: EHRRecord, baseline: PersonalBaseline) -> float:
    proxy = PatientState(
        resting_hr=vitals.get("resting_hr"),
        hrv_rmssd=vitals.get("hrv_rmssd"),
        sleep_hours=vitals.get("sleep_hours"),
        activity_load=vitals.get("activity_load"),
    )
    base, _ = susceptibility(ehr)
    drive, _ = drivers(proxy, baseline)
    return max(0.0, min(1.0, base + drive))


def patient_scenario(
    state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord
) -> tuple[Scenario, list[str]]:
    """Adapt (PatientState, baseline, EHR) to a generic RIFT Scenario."""
    vitals, imputed = _vitals_dict(state, baseline, ehr)

    def _transition(world: dict, policy: dict) -> dict:
        stepped = transition(apply_policy(world, policy), ehr, policy)
        return {k: (v if v is not None else world.get(k, 0.0)) for k, v in stepped.items()}

    constraints = tuple(
        Constraint(
            f"{field}_plausible",
            (lambda f: (lambda s: PHYSIOLOGICAL_BOUNDS[f][0] <= s.get(f, 0.0) <= PHYSIOLOGICAL_BOUNDS[f][1]))(field),
            f"{field} left the plausible physiological envelope",
        )
        for field in ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")
    )

    scenario = Scenario(
        name="patient-cardiac-strain",
        initial_state=dict(vitals),
        interventions={name: (0, 1) for name in INTERVENTIONS},
        transition=_transition,
        constraints=constraints,
        objective=lambda s: _risk_cost(s, ehr, baseline),
    )
    return scenario, imputed


def counterfactual_futures(state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord) -> dict:
    """One-step what-if futures for every intervention policy (4 policies)."""
    scenario, imputed = patient_scenario(state, baseline, ehr)
    futures = generate_futures(scenario)
    ranked = rank_robust_candidates(scenario, futures, HEALTH_PERTURBATIONS)
    guardian = verify_under_perturbations(
        dict(scenario.initial_state), ranked[0].candidate.policy if ranked else {},
        scenario.transition, list(scenario.constraints), HEALTH_PERTURBATIONS,
    ) if ranked else ()
    return {
        "policies": [
            {
                "policy": f.policy,
                "risk": f.score,
                "valid": f.valid,
            }
            for f in futures
        ],
        "robust_ranking": [
            {
                "policy": a.candidate.policy,
                "nominal_risk": a.candidate.score,
                "worst_case_risk": a.worst_case.adversarial_score if a.worst_case else a.candidate.score,
                "feasible_under_all": a.feasible_under_all,
            }
            for a in ranked
        ],
        "imputed_fields": imputed,
        "guardian": {
            "passed": all(g.passed for g in guardian),
            "checks": [{"passed": g.passed, "violations": list(g.violations)} for g in guardian],
        },
    }


def trajectories(
    state: PatientState, baseline: PersonalBaseline, ehr: EHRRecord, horizon_days: int = 3
) -> list[dict]:
    """Multi-day rollout per intervention policy using the same transition."""
    scenario, imputed = patient_scenario(state, baseline, ehr)
    vitals = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")
    paths = []
    for policy in ({n: b for n, b in zip(INTERVENTIONS, bits)} for bits in [(0, 0), (1, 0), (0, 1), (1, 1)]):
        world = dict(scenario.initial_state)
        path = [{"day": 0, **{k: world[k] for k in vitals}, "risk": scenario.objective(world)}]
        for day in range(1, horizon_days + 1):
            world = scenario.transition(world, policy)
            path.append({
                "day": day,
                "resting_hr": world["resting_hr"],
                "hrv_rmssd": world["hrv_rmssd"],
                "sleep_hours": world["sleep_hours"],
                "activity_load": world["activity_load"],
                "risk": scenario.objective(world),
            })
        paths.append({"policy": policy, "path": path, "imputed_fields": imputed})
    return paths


def health_causal_graph() -> CausalGraph:
    """Demo-assumption causal graph. Strengths are illustrative, not evidence."""
    edges = (
        CausalEdge("poor_sleep", "elevated_resting_hr", 0.7),
        CausalEdge("low_hrv", "cardiac_strain", 0.6),
        CausalEdge("high_exertion", "cardiac_strain", 0.5),
        CausalEdge("hypertension", "susceptibility", 0.6),
        CausalEdge("aging", "susceptibility", 0.4),
        CausalEdge("beta_blocker", "blunted_hr_response", -0.5),
    )
    nodes = tuple(dict.fromkeys([x for e in edges for x in (e.cause, e.effect)]))
    return CausalGraph(nodes, edges)
