from dataclasses import dataclass
from .adversarial import AdversarialFuture, search_failure_states
from .counterfactual import Future
from .models import Scenario

@dataclass(frozen=True)
class RobustAssessment:
    candidate: Future
    worst_case: AdversarialFuture | None
    mean_adversarial_score: float
    robustness_gap: float
    feasible_under_all: bool

def assess_candidate(scenario: Scenario, candidate: Future, perturbations: list[dict[str, float]]) -> RobustAssessment:
    failures = search_failure_states(scenario, candidate, perturbations)
    if not failures:
        return RobustAssessment(candidate, None, candidate.score, 0.0, True)
    worst = failures[0]
    mean = sum(x.adversarial_score for x in failures) / len(failures)
    feasible = all(x.valid for x in failures)
    return RobustAssessment(candidate, worst, mean, worst.adversarial_score - candidate.score, feasible)

def rank_robust_candidates(scenario: Scenario, candidates: list[Future], perturbations: list[dict[str, float]]) -> list[RobustAssessment]:
    assessments=[assess_candidate(scenario,c,perturbations) for c in candidates if c.valid]
    return sorted(assessments,key=lambda x:(not x.feasible_under_all,x.worst_case.adversarial_score if x.worst_case else x.candidate.score,x.mean_adversarial_score))
