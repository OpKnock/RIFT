from dataclasses import dataclass

@dataclass(frozen=True)
class CausalEdge:
    cause: str
    effect: str
    strength: float = 1.0

@dataclass(frozen=True)
class CausalGraph:
    nodes: tuple[str, ...]
    edges: tuple[CausalEdge, ...]

    def downstream(self, node: str) -> tuple[str, ...]:
        return tuple(e.effect for e in self.edges if e.cause == node)

    def upstream(self, node: str) -> tuple[str, ...]:
        return tuple(e.cause for e in self.edges if e.effect == node)

def emergency_causal_graph() -> CausalGraph:
    edges=(
        CausalEdge("smoke","visibility",0.9),
        CausalEdge("visibility","movement_speed",-0.8),
        CausalEdge("movement_speed","evacuation_time",-0.7),
        CausalEdge("crowd","congestion",0.8),
        CausalEdge("corridor_capacity","congestion",-0.9),
        CausalEdge("congestion","evacuation_time",0.8),
        CausalEdge("blocked_exit","crowd_redistribution",0.9),
        CausalEdge("crowd_redistribution","congestion",0.7),
    )
    nodes=tuple(dict.fromkeys([x for e in edges for x in (e.cause,e.effect)]))
    return CausalGraph(nodes,edges)
