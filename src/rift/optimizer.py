from dataclasses import dataclass
from itertools import product
from .models import Policy

@dataclass(frozen=True)
class QUBO:
    variables: tuple[str, ...]
    linear: dict[str, float]
    quadratic: dict[tuple[str, str], float] | None = None
    offset: float = 0.0
    def energy(self, assignment: Policy) -> float:
        value=self.offset
        for name,coefficient in self.linear.items(): value += coefficient*assignment.get(name,0)
        for (left,right),coefficient in (self.quadratic or {}).items(): value += coefficient*assignment.get(left,0)*assignment.get(right,0)
        return value

@dataclass(frozen=True)
class OptimizationResult:
    assignment: Policy
    energy: float
    method: str

def exact_minimize(qubo:QUBO, accelerator: str = "off")->OptimizationResult:
    if (accelerator or "off").strip().lower() not in ("off", "none", "false", "0"):
        from .accelerate import resolve_accelerator, torch_exact_minimize
        resolved = resolve_accelerator(accelerator)
        if resolved["use_torch"]:
            return torch_exact_minimize(qubo, device=resolved["device"])
    best=None
    for bits in product((0,1),repeat=len(qubo.variables)):
        assignment=dict(zip(qubo.variables,bits)); result=OptimizationResult(assignment,qubo.energy(assignment),"exact-enumeration")
        if best is None or result.energy<best.energy: best=result
    if best is None:  # product() over repeat=0 still yields one case; guard anyway
        raise ValueError("QUBO has no assignments to minimize")
    return best

class QuantumOptimizer:
    """Quantum optimization adapter.

    The default backend is a dependency-free QAOA statevector simulator. A future
    hardware backend can implement the same solve contract.
    """
    def __init__(self, backend="statevector", p=1, accelerator="off"):
        self.backend=backend; self.p=p; self.accelerator=accelerator
    def solve(self, qubo:QUBO, objective="expectation", alpha=0.25)->OptimizationResult:
        if self.backend!="statevector":
            raise NotImplementedError(f"Quantum backend '{self.backend}' is not connected.")
        from .qaoa import qaoa_minimize
        return qaoa_minimize(qubo,p=self.p,objective=objective,alpha=alpha,
                             accelerator=self.accelerator)
