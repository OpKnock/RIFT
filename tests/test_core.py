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
