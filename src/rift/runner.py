"""Server-side experiment execution: stored spec → reproducible run record.

This closes the product loop CREATE → RUN → PERSIST → INSPECT → REPRODUCE.
The runner is pure engine code (no DB, no network): given an
:class:`rift.experiments.ExperimentSpec` it rebuilds the scenario from the
registry, executes the optimizer/backend named in the spec, verifies the
winner with Guardian, and returns a JSON-safe record containing everything
needed to compare and reproduce the result.

Determinism: current backends (exact enumeration, statevector QAOA grid
search) are fully deterministic; ``seed`` is recorded for future stochastic
backends and echoed back so rows stay comparable.
"""
from __future__ import annotations

import time
from typing import Any

from . import __version__ as ENGINE_VERSION
from .experiments import ExperimentSpec
from .multivariable import (
    build_robust_qubo_projection,
    evaluate_policy,
    exact_multivariable_robust_minimize,
    optimize_policy_space,
)
from .optimizer import QuantumOptimizer
from .scenarios import emergency_building
from .verifier import verify_under_perturbations

DEFAULT_POLICY_VARIABLES = ("route_a", "route_c", "stairwell_b")


def build_scenario(spec: ExperimentSpec):
    """Rebuild the domain scenario from a stored spec.

    Only registry scenarios are supported; ``initial_state`` overrides are
    restricted to known numeric fields so a stored row can never inject
    arbitrary state. Raises ValueError on unknown scenario/field.
    """
    if spec.scenario_name != "smart-building-emergency":
        raise ValueError(f"unsupported scenario_name: {spec.scenario_name!r}")
    scenario = emergency_building()
    known = set(scenario.initial_state)
    for key, value in spec.initial_state.items():
        if key not in known:
            raise ValueError(f"unknown scenario field: {key!r}")
        if not isinstance(value, (int, float)):
            raise ValueError(f"scenario field {key!r} must be numeric")
        scenario.initial_state[key] = float(value)
    return scenario


def run_spec(spec: ExperimentSpec) -> dict[str, Any]:
    """Execute a validated spec; return a JSON-safe run record."""
    if not isinstance(spec, ExperimentSpec):
        raise ValueError("run_spec requires an ExperimentSpec")
    started = time.perf_counter()
    scenario = build_scenario(spec)
    perturbations = [dict(p) for p in spec.perturbations]
    variables = tuple(spec.policy_variables) or DEFAULT_POLICY_VARIABLES

    ranked = optimize_policy_space(scenario, variables, perturbations)
    if spec.optimizer == "exact":
        best = exact_multivariable_robust_minimize(scenario, variables, perturbations)
        method = best.method
        projection_error: dict[str, Any] | None = None
    elif spec.optimizer in ("qaoa-expectation", "qaoa-cvar"):
        objective = "expectation" if spec.optimizer == "qaoa-expectation" else "cvar"
        projection = build_robust_qubo_projection(scenario, variables, perturbations)
        solved = QuantumOptimizer().solve(projection, objective=objective, alpha=0.25)
        gaps = [
            abs(projection.energy(policy.assignment) - policy.robust_cost)
            for policy in ranked
        ]
        projection_error = {
            "max_absolute_gap": max(gaps, default=0.0),
            "mean_absolute_gap": sum(gaps) / len(gaps) if gaps else 0.0,
            "approximation": True,
        }
        method = solved.method
        best = solved
    else:  # pragma: no cover — validate_spec_payload rejects these first
        raise ValueError(f"unsupported optimizer: {spec.optimizer!r}")

    guardian = verify_under_perturbations(
        dict(scenario.initial_state),
        best.assignment,
        scenario.transition,
        list(scenario.constraints),
        perturbations,
    )
    duration_ms = (time.perf_counter() - started) * 1000.0
    evaluation = evaluate_policy(scenario, best.assignment, perturbations)
    return {
        "engine_version": ENGINE_VERSION,
        "backend": "statevector-simulator" if spec.backend != "none" else "none",
        "optimizer": spec.optimizer,
        "method": method,
        "assignment": best.assignment,
        "nominal_cost": evaluation.nominal_cost,
        "robust_cost": evaluation.robust_cost,
        "feasible": evaluation.feasible,
        "worst_perturbation": evaluation.worst_perturbation,
        "constraint_violations": sum(1 for check in guardian if not check.passed),
        "guardian": {
            "passed": all(check.passed for check in guardian),
            "checks": [
                {"passed": check.passed, "violations": list(check.violations)}
                for check in guardian
            ],
            "scope": "nominal + every declared perturbation",
        },
        "projection_error": projection_error,
        "policies_evaluated": len(ranked),
        "effective_policy_variables": list(variables),
        "effective_perturbations": perturbations,
        "seed": spec.seed,
        "duration_ms": duration_ms,
        "spec_fingerprint": spec.fingerprint(),
    }
