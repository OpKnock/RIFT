from dataclasses import dataclass
from .counterfactual import Future
from .models import Scenario

@dataclass(frozen=True)
class AdversarialFuture:
    policy: dict[str, int]
    state: dict[str, float]
    base_score: float
    adversarial_score: float
    perturbation: dict[str, float]

def search_failure_states(scenario: Scenario, candidate: Future, perturbations: list[dict[str, float]]) -> list[AdversarialFuture]:
    results = []
    for delta in perturbations:
        perturbed = dict(scenario.initial_state)
        for key, amount in delta.items():
            perturbed[key] = perturbed.get(key, 0.0) + amount
        state = scenario.transition(perturbed, candidate.policy)
        results.append(AdversarialFuture(candidate.policy, state, candidate.score, scenario.objective(state), delta))
    return sorted(results, key=lambda x: x.adversarial_score, reverse=True)
