from rift.benchmark import benchmark_suite, simulated_annealing, tabu_search
from rift.optimizer import QUBO, exact_minimize

Q = QUBO(("a", "b"), {"a": -2, "b": -1}, {("a", "b"): 3})


def test_benchmark_suite_reports_four_methods():
    methods = [r.method for r in benchmark_suite(Q)]
    assert methods == ["exact-enumeration", "qaoa-statevector-simulator",
                       "simulated-annealing", "tabu-search"]


def test_heuristics_deterministic_for_fixed_seed():
    sa1, sa2 = simulated_annealing(Q), simulated_annealing(Q)
    tb1, tb2 = tabu_search(Q), tabu_search(Q)
    assert (sa1.assignment, sa1.energy) == (sa2.assignment, sa2.energy)
    assert (tb1.assignment, tb1.energy) == (tb2.assignment, tb2.energy)


def test_heuristics_valid_assignments_with_reported_gap():
    exact = exact_minimize(Q)
    for result in (simulated_annealing(Q), tabu_search(Q)):
        assert set(result.assignment) == {"a", "b"}
        assert all(v in (0, 1) for v in result.assignment.values())
        assert result.energy >= exact.energy  # gap never negative
        assert result.runtime_ms >= 0
