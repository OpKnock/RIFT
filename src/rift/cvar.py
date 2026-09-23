from __future__ import annotations

def cvar(values: list[float], alpha: float = 0.25) -> float:
    """Average of the best alpha fraction of sampled costs (minimization)."""
    if not values:
        raise ValueError("values must not be empty")
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    ordered=sorted(values)
    count=max(1,int(len(ordered)*alpha))
    return sum(ordered[:count])/count

def cvar_from_distribution(costs: list[float], probabilities: list[float], alpha: float = 0.25) -> float:
    if len(costs)!=len(probabilities) or not costs:
        raise ValueError("costs and probabilities must be non-empty and equal length")
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    pairs=sorted(zip(costs,probabilities),key=lambda x:x[0])
    remaining=alpha
    total=0.0
    mass=0.0
    for cost,prob in pairs:
        take=min(max(prob,0.0),remaining)
        total += cost*take
        mass += take
        remaining -= take
        if remaining <= 1e-12:
            break
    return total/mass if mass else min(costs)