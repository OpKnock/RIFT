from dataclasses import dataclass
from itertools import product
from .models import Policy, Scenario

@dataclass(frozen=True)
class FutureNode:
    id: str
    parent_id: str | None
    depth: int
    policy: Policy
    state: dict[str,float]
    score: float
    valid: bool
    label: str

@dataclass(frozen=True)
class FutureTree:
    nodes: tuple[FutureNode,...]
    max_depth: int

def branch_futures(scenario: Scenario, depth: int = 3) -> FutureTree:
    if depth < 1 or depth > 6:
        raise ValueError("depth must be between 1 and 6")
    nodes=[]
    frontier=[(None,dict(scenario.initial_state),{})]
    for level in range(depth):
        next_frontier=[]
        keys=list(scenario.interventions)
        values=[scenario.interventions[k] for k in keys]
        for parent_id,state,history in frontier:
            for bits in product(*values):
                policy=dict(zip(keys,bits))
                merged={**history,**policy}
                new_state=scenario.transition(dict(state),policy)
                valid=all(c.check(new_state) for c in scenario.constraints)
                node_id=f"f{level+1}-{len(nodes)+1}"
                node=FutureNode(node_id,parent_id,level+1,merged,new_state,scenario.objective(new_state),valid,f"t+{level+1}")
                nodes.append(node)
                next_frontier.append((node_id,new_state,merged))
        frontier=next_frontier
    return FutureTree(tuple(nodes),depth)
