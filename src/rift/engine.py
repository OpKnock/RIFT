from dataclasses import dataclass
from .counterfactual import Future, generate_futures
from .models import Scenario
from .optimizer import OptimizationResult, QUBO, exact_minimize, QuantumOptimizer
from .robust import rank_robust_candidates
from .robust_qubo import build_robust_qubo
from .verifier import VerificationResult, verify

@dataclass(frozen=True)
class ExperimentResult:
    candidates: tuple[Future, ...]
    best_policy: OptimizationResult
    verification: VerificationResult
    robust_candidates: tuple = ()
    robust_qubo: QUBO | None = None
    quantum_policy: OptimizationResult | None = None

def run_experiment(scenario: Scenario, qubo: QUBO, perturbations: list[dict[str,float]] | None = None) -> ExperimentResult:
    candidates=tuple(generate_futures(scenario))
    perturbations=perturbations or []
    ranked=tuple(rank_robust_candidates(scenario,list(candidates),perturbations)) if perturbations else ()
    robust_qubo=build_robust_qubo(scenario,qubo.variables,perturbations) if perturbations else None
    if robust_qubo:
        best=exact_minimize(robust_qubo)
        quantum=QuantumOptimizer().solve(robust_qubo)
    else:
        best=exact_minimize(qubo)
        quantum=QuantumOptimizer().solve(qubo)
    state=scenario.transition(dict(scenario.initial_state),best.assignment)
    return ExperimentResult(candidates,best,verify(state,list(scenario.constraints)),ranked,robust_qubo,quantum)
