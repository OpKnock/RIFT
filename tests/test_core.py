from rift.models import Constraint, Scenario
from rift.counterfactual import generate_futures
from rift.optimizer import QUBO, exact_minimize
from rift.verifier import verify

def test_policy_enumeration_and_verification():
    s = Scenario("test", {"capacity":0}, {"a":(0,1),"b":(0,1)}, lambda st,p: {"capacity":10*p["a"]+5*p["b"]}, (Constraint("capacity", lambda x:x["capacity"]>=10, "capacity too low"),))
    futures = generate_futures(s)
    assert len(futures) == 4 and sum(f.valid for f in futures) == 2

def test_exact_qubo():
    q = QUBO(("a","b"), {"a":-2,"b":-1}, {("a","b"):3})
    r = exact_minimize(q)
    assert r.assignment == {"a":1,"b":0} and r.energy == -2

def test_guardian():
    c = Constraint("capacity", lambda s:s["capacity"]>=10, "capacity too low")
    r = verify({"capacity":4}, [c])
    assert not r.passed and r.violations == ("capacity too low",)


def test_robust_engine_runs_quantum_and_classical_paths():
    from rift.engine import run_experiment
    from rift.scenarios import emergency_building
    s=emergency_building()
    q=QUBO(("route_a","route_c"),{"route_a":1.0,"route_c":1.0},{("route_a","route_c"):-0.5})
    result=run_experiment(s,q,[{"smoke":2.0},{"crowd":80.0}])
    assert result.robust_qubo is not None
    assert result.quantum_policy is not None
    assert set(result.best_policy.assignment)=={"route_a","route_c"}
