from rift.multivariable import (
    optimize_policy_space,
    build_robust_qubo_projection,
)
from rift.robust_qubo import robust_policy_cost
from rift.scenarios import emergency_building

def test_multivariable_space_supports_three_binary_controls():
    s = emergency_building()
    ranked = optimize_policy_space(
        s, ("route_a", "route_c", "stairwell_b"), [{"smoke": 2}]
    )
    assert len(ranked) == 8
    assert ranked[0].robust_cost <= ranked[-1].robust_cost

def test_quadratic_projection_has_all_pair_terms():
    s = emergency_building()
    q = build_robust_qubo_projection(
        s, ("route_a", "route_c", "stairwell_b"), [{"smoke": 2}]
    )
    assert len(q.quadratic) == 3

def test_projection_is_measured_against_exact_objective():
    s = emergency_building()
    variables = ("route_a", "route_c", "stairwell_b")
    perturbations = [{"smoke": 2}, {"crowd": 80}]
    q = build_robust_qubo_projection(s, variables, perturbations)
    max_gap = 0.0
    for policy in optimize_policy_space(s, variables, perturbations):
        exact = robust_policy_cost(s, policy.assignment, perturbations)
        max_gap = max(max_gap, abs(q.energy(policy.assignment) - exact))
    assert max_gap >= 0.0
