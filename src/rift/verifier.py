from dataclasses import dataclass
from .models import Constraint, State

@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    violations: tuple[str, ...]

def verify(
    state: State,
    constraints: list[Constraint] | tuple[Constraint, ...],
) -> VerificationResult:
    violations = tuple(c.message for c in constraints if not c.check(state))
    return VerificationResult(not violations, violations)

def verify_under_perturbations(
    initial_state: State,
    policy: dict[str, int],
    transition,
    constraints: list[Constraint] | tuple[Constraint, ...],
    perturbations: list[dict[str, float]],
) -> tuple[VerificationResult, ...]:
    """Independently verify nominal + every adversarial perturbation."""
    results = [verify(transition(dict(initial_state), policy), constraints)]
    for delta in perturbations:
        state = dict(initial_state)
        for key, amount in delta.items():
            state[key] = state.get(key, 0.0) + amount
        results.append(verify(transition(state, policy), constraints))
    return tuple(results)
