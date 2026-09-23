from rift.multivariable import optimize_policy_space, build_robust_qubo_projection
from rift.scenarios import emergency_building

def test_multivariable_space_supports_three_binary_controls():
    s=emergency_building()
    ranked=optimize_policy_space(s,("route_a","route_c","stairwell_b"),[{"smoke":2}])
    assert len(ranked)==8
    assert ranked[0].robust_cost <= ranked[-1].robust_cost

def test_quadratic_projection_has_all_pair_terms():
    s=emergency_building()
    q=build_robust_qubo_projection(s,("route_a","route_c","stairwell_b"),[{"smoke":2}])
    assert len(q.quadratic)==3
