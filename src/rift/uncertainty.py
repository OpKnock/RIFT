from math import log

def normalized_entropy(values: list[float]) -> float:
    if not values:
        return 0.0
    total=sum(max(v,0.0) for v in values)
    if total <= 0.0:
        return 0.0
    probs=[max(v,0.0)/total for v in values]
    return -sum(p*log(p) for p in probs if p>0.0)

def normalized_risk_entropy(scores: list[float]) -> float:
    if not scores:
        return 0.0
    lo,hi=min(scores),max(scores)
    span=hi-lo
    if span == 0:
        return 0.0
    weights=[(s-lo)/span for s in scores]
    return normalized_entropy(weights)