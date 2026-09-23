from rift.cvar import cvar, cvar_from_distribution

def test_cvar_focuses_on_best_cost_tail():
    assert cvar([10, 20, 30, 40], 0.5) == 15

def test_distribution_cvar():
    # alpha=0.5 consumes 0.2 mass at cost 1 and 0.3 at cost 2.
    assert abs(cvar_from_distribution([1, 2, 10], [0.2, 0.5, 0.3], 0.5) - 1.6) < 1e-9
