from rift.robust_qubo import build_robust_qubo, robust_policy_cost
from rift.optimizer import exact_minimize
from rift.scenarios import emergency_building

def test_robust_qubo_matches_policy_costs():
    scenario = emergency_building()
    perturbations = [{"smoke": 2.0}, {"crowd": 80.0}]
    qubo = build_robust_qubo(scenario, ("route_a", "route_c"), perturbations)
    for route_a in (0, 1):
        for route_c in (0, 1):
            policy = {"route_a": route_a, "route_c": route_c}
            assert abs(
                qubo.energy(policy)
                - robust_policy_cost(scenario, policy, perturbations)
            ) < 1e-9

def test_robust_qubo_has_exact_classical_solution():
    scenario = emergency_building()
    qubo = build_robust_qubo(
        scenario, ("route_a", "route_c"), [{"smoke": 2.0}, {"crowd": 80.0}]
    )
    result = exact_minimize(qubo)
    assert tuple(result.assignment.keys()) == qubo.variables
