from rift.optimizer import QUBO, exact_minimize
from rift.qaoa import simulate_qaoa

def test_qaoa_returns_valid_assignment():
    q=QUBO(("a","b"),{"a":-2,"b":-1},{("a","b"):3})
    exact=exact_minimize(q)
    result=simulate_qaoa(q,p=1,grid_steps=5,iterations=3)
    assert set(result.assignment)=={"a","b"}
    assert result.expected_energy >= exact.energy
    assert 0.0 <= result.probability <= 1.0
