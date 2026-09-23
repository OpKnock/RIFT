from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from .models import Policy, Scenario
from .robust_qubo import robust_policy_cost
from .optimizer import OptimizationResult, QUBO, exact_minimize

@dataclass(frozen=True)
class PolicyEvaluation:
    assignment: Policy
    nominal_cost: float
    robust_cost: float
    feasible: bool
    worst_perturbation: dict[str, float]

def enumerate_policies(variables: tuple[str, ...]):
    if not variables:
        raise ValueError("at least one policy variable is required")
    if len(variables) > 16:
        raise ValueError("exact policy enumeration is limited to 16 binary variables")
    for bits in product((0, 1), repeat=len(variables)):
        yield dict(zip(variables, bits))

def evaluate_policy(scenario: Scenario, policy: Policy, perturbations: list[dict[str, float]], penalty: float = 1000.0) -> PolicyEvaluation:
    nominal_state=scenario.transition(dict(scenario.initial_state), policy)
    nominal=scenario.objective(nominal_state)
    scenarios=[{}]+perturbations
    scored=[]
    for perturbation in scenarios:
        state=dict(scenario.initial_state)
        for key,delta in perturbation.items():
            if key in state:
                state[key]+=delta
        state=scenario.transition(state, policy)
        cost=scenario.objective(state)
        valid=all(c.check(state) for c in scenario.constraints)
        scored.append((cost + (0.0 if valid else penalty), perturbation, valid))
    worst=max(scored,key=lambda x:x[0])
    return PolicyEvaluation(policy,nominal,worst[0],all(x[2] for x in scored),worst[1])

def optimize_policy_space(scenario: Scenario, variables: tuple[str, ...], perturbations: list[dict[str, float]], penalty: float = 1000.0) -> list[PolicyEvaluation]:
    results=[evaluate_policy(scenario,p,perturbations,penalty) for p in enumerate_policies(variables)]
    return sorted(results,key=lambda x:(not x.feasible,x.robust_cost,x.nominal_cost))

def exact_multivariable_robust_minimize(scenario: Scenario, variables: tuple[str, ...], perturbations: list[dict[str, float]], penalty: float = 1000.0) -> OptimizationResult:
    ranked=optimize_policy_space(scenario,variables,perturbations,penalty)
    best=ranked[0]
    return OptimizationResult(best.assignment,best.robust_cost,"exact-multivariable-robust-enumeration")

def quadratic_projection(values: dict[tuple[int,...],float], variables: tuple[str,...]) -> QUBO:
    """Project a Boolean objective onto all linear/quadratic terms.

    This is a transparent approximation for >2 variables. It is NOT an exact
    representation of a higher-order objective and is labeled as such by RIFT.
    """
    zero=(0,)*len(variables)
    offset=values[zero]
    linear={}
    for i,name in enumerate(variables):
        bits=list(zero); bits[i]=1
        linear[name]=values[tuple(bits)]-offset
    quadratic={}
    for i in range(len(variables)):
        for j in range(i+1,len(variables)):
            bits=[0]*len(variables); bits[i]=1; bits[j]=1
            a=tuple(bits)
            bits_j=[0]*len(variables); bits_j[j]=1
            bits_i=[0]*len(variables); bits_i[i]=1
            quadratic[(variables[i],variables[j])]=values[a]-values[tuple(bits_i)]-values[tuple(bits_j)]+offset
    return QUBO(variables,linear,quadratic,offset)

def build_robust_qubo_projection(scenario: Scenario, variables: tuple[str,...], perturbations: list[dict[str,float]], penalty: float=1000.0) -> QUBO:
    values={bits:robust_policy_cost(scenario,dict(zip(variables,bits)),perturbations,penalty) for bits in product((0,1),repeat=len(variables))}
    return quadratic_projection(values,variables)
