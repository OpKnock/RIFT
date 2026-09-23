from rift.robust_qubo import build_robust_qubo, robust_policy_cost
from rift.optimizer import exact_minimize
from rift.scenarios import emergency_building

def test_robust_qubo_matches_policy_costs():
    s=emergency_building()
    perturbations=[{"smoke":2.0},{"crowd":80.0}]
    q=build_robust_qubo(s,("route_a","route_c"),perturbations)
    for a in (0,1):
        for c in (0,1):
            p={"route_a":a,"route_c":c}
            assert abs(q.energy(p)-robust_policy_cost(s,p,perturbations)) < 1e-9

def test_robust_qubo_has_exact_classical_solution():
    s=emergency_building()
    q=build_robust_qubo(s,("route_a","route_c"),[{"smoke":2.0},{"crowd":80.0}])
    result=exact_minimize(q)
    assert result.assignment.keys()==q.variables