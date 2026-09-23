from math import log

def normalized_entropy(values: list[float]) -> float:
    """Shannon entropy (nats) of non-negative values treated as weights.

    "Normalized" here means the inputs are rescaled to sum to 1, not that
    the output is divided by log(n): uniform inputs yield log(n), not 1.0.
    """
    if not values:
        return 0.0
    total=sum(max(v,0.0) for v in values)
    if total <= 0.0:
        return 0.0
    probs=[max(v,0.0)/total for v in values]
    return -sum(p*log(p) for p in probs if p>0.0)

def normalized_risk_entropy(scores: list[float]) -> float:
    """Entropy (nats) of min-max rescaled scores; 0.0 when all scores tie."""
    if not scores:
        return 0.0
    lo,hi=min(scores),max(scores)
    span=hi-lo
    if span == 0:
        return 0.0
    weights=[(s-lo)/span for s in scores]
    return normalized_entropy(weights)