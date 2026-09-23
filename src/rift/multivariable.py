from __future__ import annotations
from dataclasses import dataclass
from itertools import product

from .models import Policy, Scenario
from .robust_qubo import robust_policy_cost
from .optimizer import OptimizationResult, QUBO


@dataclass(frozen=True)
class PolicyEvaluation:
    assignment: Policy
    nominal_cost: float
    robust_cost: float
    feasible: bool
    worst_perturbation: dict[str, float]


def enumerate_policies(variables: tuple[str, ...]):
    if not variables:
        raise ValueError("at least one policy variable is required")
    if len(variables) > 16:
        raise ValueError("exact policy enumeration is limited to 16 binary variables")
    for bits in product((0, 1), repeat=len(variables)):
        yield dict(zip(variables, bits))


def evaluate_policy(
    scenario: Scenario,
    policy: Policy,
    perturbations: list[dict[str, float]],
    penalty: float = 1000.0,
) -> PolicyEvaluation:
    nominal_state = scenario.transition(dict(scenario.initial_state), policy)
    nominal = scenario.objective(nominal_state)
    scenarios = [{}] + perturbations
    scored = []
    for perturbation in scenarios:
        state = dict(scenario.initial_state)
        for key, delta in perturbation.items():
            if key in state:
                state[key] += delta
        state = scenario.transition(state, policy)
        cost = scenario.objective(state)
        valid = all(c.check(state) for c in scenario.constraints)
        scored.append((cost + (0.0 if valid else penalty), perturbation, valid))
    worst = max(scored, key=lambda x: x[0])
    return PolicyEvaluation(
        policy,
        nominal,
        worst[0],
        all(x[2] for x in scored),
        worst[1],
    )


def optimize_policy_space(
    scenario: Scenario,
    variables: tuple[str, ...],
    perturbations: list[dict[str, float]],
    penalty: float = 1000.0,
) -> list[PolicyEvaluation]:
    results = [
        evaluate_policy(scenario, policy, perturbations, penalty)
        for policy in enumerate_policies(variables)
    ]
    return sorted(
        results,
        key=lambda x: (not x.feasible, x.robust_cost, x.nominal_cost),
    )


def exact_multivariable_robust_minimize(
    scenario: Scenario,
    variables: tuple[str, ...],
    perturbations: list[dict[str, float]],
    penalty: float = 1000.0,
) -> OptimizationResult:
    ranked = optimize_policy_space(scenario, variables, perturbations, penalty)
    best = ranked[0]
    return OptimizationResult(
        best.assignment,
        best.robust_cost,
        "exact-multivariable-robust-enumeration",
    )


def quadratic_projection(
    values: dict[tuple[int, ...], float],
    variables: tuple[str, ...],
) -> QUBO:
    """Least-squares project a Boolean objective onto degree <=2 terms.

    The projection uses the orthogonal Walsh basis z_i in {-1, +1} under the
    uniform distribution over the supplied Boolean policy space. Keeping the
    constant, singleton, and pair terms is the uniform least-squares
    degree-2 approximation. For objectives with higher-order interactions this
    is intentionally approximate; the omitted higher-order energy is measured
    by the caller.
    """
    n = len(variables)
    expected_points = 2**n
    if len(values) != expected_points:
        raise ValueError(
            f"expected {expected_points} Boolean objective values, got {len(values)}"
        )

    all_bits = list(product((0, 1), repeat=n))
    offset = 0.0
    singleton = [0.0] * n
    pair = {}

    # z_i = 1 - 2*x_i is an orthogonal {-1,+1} basis. The coefficient of
    # each basis function is its uniform mean against that basis function.
    for bits in all_bits:
        value = float(values[bits])
        z = [1.0 - 2.0 * bit for bit in bits]
        offset += value
        for i in range(n):
            singleton[i] += value * z[i]
        for i in range(n):
            for j in range(i + 1, n):
                pair[(i, j)] = pair.get((i, j), 0.0) + value * z[i] * z[j]

    scale = 1.0 / expected_points
    offset *= scale
    singleton = [coefficient * scale for coefficient in singleton]
    pair = {key: coefficient * scale for key, coefficient in pair.items()}

    # Convert the z-basis projection back to the standard 0/1 QUBO basis:
    # z_i = 1 - 2*x_i and z_i*z_j = 1 - 2*x_i - 2*x_j + 4*x_i*x_j.
    linear = [-2.0 * coefficient for coefficient in singleton]
    for (i, j), coefficient in pair.items():
        linear[i] -= 2.0 * coefficient
        linear[j] -= 2.0 * coefficient

    quadratic = {
        (variables[i], variables[j]): 4.0 * coefficient
        for (i, j), coefficient in pair.items()
    }

    offset += sum(singleton) + sum(pair.values())
    return QUBO(
        variables,
        {variables[i]: linear[i] for i in range(n)},
        quadratic,
        offset,
    )


def build_robust_qubo_projection(
    scenario: Scenario,
    variables: tuple[str, ...],
    perturbations: list[dict[str, float]],
    penalty: float = 1000.0,
) -> QUBO:
    values = {
        bits: robust_policy_cost(
            scenario,
            dict(zip(variables, bits)),
            perturbations,
            penalty,
        )
        for bits in product((0, 1), repeat=len(variables))
    }
    return quadratic_projection(values, variables)
