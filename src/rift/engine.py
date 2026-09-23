from dataclasses import dataclass
from .counterfactual import Future, generate_futures
from .models import Scenario
from .optimizer import OptimizationResult, QUBO, exact_minimize
from .robust import rank_robust_candidates
from .verifier import VerificationResult, verify

@dataclass(frozen=True)
class ExperimentResult:
    candidates: tuple[Future, ...]
    best_policy: OptimizationResult
    verification: VerificationResult
    robust_candidates: tuple = ()

def run_experiment(scenario: Scenario, qubo: QUBO, perturbations: list[dict[str,float]] | None = None) -> ExperimentResult:
    candidates = tuple(generate_futures(scenario))
    perturbations = perturbations or []
    ranked = tuple(rank_robust_candidates(scenario,list(candidates),perturbations)) if perturbations else ()
    if ranked:
        selected = ranked[0].candidate.policy
        energy = qubo.energy(selected)
        best = OptimizationResult(selected,energy,"robust-classical")
    else:
        best = exact_minimize(qubo)
    state = scenario.transition(dict(scenario.initial_state), best.assignment)
    return ExperimentResult(candidates, best, verify(state, list(scenario.constraints)), ranked)
