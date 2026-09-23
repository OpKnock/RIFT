import argparse
from .models import Constraint, Scenario
from .optimizer import QUBO
from .engine import run_experiment

def demo() -> None:
    def transition(state, policy):
        return {"risk": max(0.0, state["risk"] - 8 * policy["route_a"] - 5 * policy["route_b"]), "capacity": state["capacity"] + 10 * policy["route_a"] + 6 * policy["route_b"]}
    scenario = Scenario("emergency-routing", {"risk": 40.0, "capacity": 20.0}, {"route_a": (0,1), "route_b": (0,1)}, transition, (Constraint("capacity", lambda s: s["capacity"] >= 30, "Capacity must remain >= 30"),), lambda s: s["risk"] - 0.1*s["capacity"])
    result = run_experiment(scenario, QUBO(("route_a","route_b"), {"route_a": -8.0, "route_b": -5.0}))
    print("RIFT demo")
    print("Best policy:", result.best_policy.assignment)
    print("Energy:", result.best_policy.energy)
    print("Guardian:", "PASS" if result.verification.passed else "FAIL")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["demo"])
    if parser.parse_args().command == "demo": demo()

if __name__ == "__main__": main()
