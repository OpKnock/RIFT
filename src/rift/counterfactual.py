from dataclasses import dataclass
from itertools import product
from .models import Policy, Scenario

@dataclass(frozen=True)
class Future:
    policy: Policy
    state: dict[str, float]
    score: float
    valid: bool

def enumerate_policies(scenario: Scenario) -> list[Policy]:
    keys = list(scenario.interventions)
    values = [scenario.interventions[k] for k in keys]
    return [dict(zip(keys, bits)) for bits in product(*values)]

def simulate_policy(scenario: Scenario, policy: Policy) -> Future:
    state = scenario.transition(dict(scenario.initial_state), policy)
    valid = all(c.check(state) for c in scenario.constraints)
    return Future(policy, state, scenario.objective(state), valid)

def generate_futures(scenario: Scenario) -> list[Future]:
    return [simulate_policy(scenario, p) for p in enumerate_policies(scenario)]
