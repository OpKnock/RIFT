from dataclasses import dataclass
from .counterfactual import Future, generate_futures
from .models import Scenario
from .optimizer import OptimizationResult, QUBO, exact_minimize
from .verifier import VerificationResult, verify

@dataclass(frozen=True)
class ExperimentResult:
    candidates: tuple[Future, ...]
    best_policy: OptimizationResult
    verification: VerificationResult

def run_experiment(scenario: Scenario, qubo: QUBO) -> ExperimentResult:
    candidates = tuple(generate_futures(scenario))
    best = exact_minimize(qubo)
    state = scenario.transition(dict(scenario.initial_state), best.assignment)
    return ExperimentResult(candidates, best, verify(state, list(scenario.constraints)))
