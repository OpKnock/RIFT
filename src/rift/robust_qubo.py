from itertools import product
from .models import Scenario, Policy
from .optimizer import QUBO

def _scenario_cost(scenario: Scenario, policy: Policy, perturbation: dict[str,float], penalty: float) -> float:
    state=dict(scenario.initial_state)
    for key,delta in perturbation.items():
        if key in state:
            state[key]+=delta
    state=scenario.transition(state,policy)
    objective=scenario.objective(state)
    if not all(c.check(state) for c in scenario.constraints):
        objective += penalty
    return objective

def robust_policy_cost(scenario: Scenario, policy: Policy, perturbations: list[dict[str,float]], penalty: float=1000.0) -> float:
    scenarios=[{}]+perturbations
    return max(_scenario_cost(scenario,policy,p,penalty) for p in scenarios)

def build_robust_qubo(scenario: Scenario, variables: tuple[str,...], perturbations: list[dict[str,float]], penalty: float=1000.0) -> QUBO:
    """Fit the exact robust Boolean objective into a QUBO for <=2 binary variables."""
    if len(variables)>2:
        raise ValueError("Exact robust QUBO fitting currently supports at most 2 binary variables.")
    values={}
    for bits in product((0,1),repeat=len(variables)):
        policy=dict(zip(variables,bits))
        values[bits]=robust_policy_cost(scenario,policy,perturbations,penalty)
    offset=values[(0,)*len(variables)]
    linear={}
    quadratic={}
    for i,name in enumerate(variables):
        bits=[0]*len(variables); bits[i]=1
        linear[name]=values[tuple(bits)]-offset
    if len(variables)==2:
        a,b=variables
        quadratic[(a,b)]=values[(1,1)]-values[(1,0)]-values[(0,1)]+offset
    return QUBO(variables,linear,quadratic,offset)