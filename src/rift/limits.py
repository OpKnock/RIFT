"""Central computational and request limits.

RIFT enumerates counterfactuals combinatorially. These bounds keep the
demo honest: exceeding a limit returns a clear error instead of silently
truncating a scientific experiment. Every value is overridable via
``RIFT_MAX_*`` environment variables for operators who know their budget.
"""
from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (ValueError, AttributeError):
        return default
    return value if value > 0 else default


MAX_POLICY_VARIABLES = _int_env("RIFT_MAX_POLICY_VARIABLES", 16)
MAX_PERTURBATIONS = _int_env("RIFT_MAX_PERTURBATIONS", 32)
MAX_FUTURES = _int_env("RIFT_MAX_FUTURES", 256)
MAX_TREE_DEPTH = _int_env("RIFT_MAX_TREE_DEPTH", 6)
MAX_PAYLOAD_BYTES = _int_env("RIFT_MAX_PAYLOAD_BYTES", 1_000_000)
MAX_NAME_LENGTH = _int_env("RIFT_MAX_NAME_LENGTH", 200)
MAX_QUBO_VARIABLES = 12  # hard simulator bound in rift.qaoa

# Scenario input bounds for the smart-building lab (units documented in
# docs/experiments.md). Out-of-range values are rejected, not clamped.
SCENARIO_BOUNDS = {
    "crowd": (0.0, 5000.0),
    "smoke": (0.0, 20.0),
    "corridor_capacity": (1.0, 10000.0),
    "blocked_b_penalty": (0.0, 1000.0),
    "smoke_growth": (-20.0, 20.0),
}


def check_policy_variables(variables: tuple[str, ...] | list[str]) -> None:
    if not variables:
        raise ValueError("at least one policy variable is required")
    if len(variables) != len(set(variables)):
        raise ValueError("policy variables must be unique")
    if len(variables) > MAX_POLICY_VARIABLES:
        raise ValueError(
            f"too many policy variables ({len(variables)} > {MAX_POLICY_VARIABLES}); "
            "exact enumeration would explode combinatorially"
        )
    for name in variables:
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise ValueError(f"invalid policy variable name: {name!r}")


def check_perturbations(perturbations: list[dict]) -> None:
    if len(perturbations) > MAX_PERTURBATIONS:
        raise ValueError(
            f"too many perturbations ({len(perturbations)} > {MAX_PERTURBATIONS})"
        )
    for delta in perturbations:
        if not isinstance(delta, dict):
            raise ValueError("each perturbation must be an object")
        for key, amount in delta.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"invalid perturbation key: {key!r}")
            if not isinstance(amount, (int, float)) or not abs(float(amount)) < 1e12:
                raise ValueError(f"invalid perturbation amount for {key!r}")


def check_scenario_state(state: dict) -> None:
    if not isinstance(state, dict):
        raise ValueError("scenario state must be an object")
    for key, value in state.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"scenario field {key!r} must be numeric")
        bounds = SCENARIO_BOUNDS.get(key)
        if bounds is not None:
            lo, hi = bounds
            if not (lo <= float(value) <= hi):
                raise ValueError(
                    f"scenario field {key!r}={value} out of range [{lo}, {hi}]"
                )


def check_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"name exceeds {MAX_NAME_LENGTH} characters")


def describe_limits() -> dict:
    return {
        "max_policy_variables": MAX_POLICY_VARIABLES,
        "max_perturbations": MAX_PERTURBATIONS,
        "max_futures": MAX_FUTURES,
        "max_tree_depth": MAX_TREE_DEPTH,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "max_name_length": MAX_NAME_LENGTH,
        "max_qubo_variables": MAX_QUBO_VARIABLES,
        "scenario_bounds": SCENARIO_BOUNDS,
    }
