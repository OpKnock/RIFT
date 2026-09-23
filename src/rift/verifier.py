from dataclasses import dataclass
from .models import Constraint, State

@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    violations: tuple[str, ...]

def verify(state: State, constraints: list[Constraint] | tuple[Constraint, ...]) -> VerificationResult:
    violations = tuple(c.message for c in constraints if not c.check(state))
    return VerificationResult(not violations, violations)
