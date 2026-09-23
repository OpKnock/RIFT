from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

State = dict[str, float]
Policy = dict[str, int]
Transition = Callable[[State, Policy], State]

@dataclass(frozen=True)
class Constraint:
    name: str
    check: Callable[[State], bool]
    message: str

@dataclass(frozen=True)
class Scenario:
    name: str
    initial_state: State
    interventions: Mapping[str, Sequence[int]]
    transition: Transition
    constraints: Sequence[Constraint] = field(default_factory=tuple)
    objective: Callable[[State], float] = lambda state: 0.0
