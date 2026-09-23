from dataclasses import dataclass
from time import perf_counter
from .optimizer import QUBO, OptimizationResult, exact_minimize
from .qaoa import QAOAResult, simulate_qaoa

@dataclass(frozen=True)
class BenchmarkResult:
    method: str
    energy: float
    assignment: dict[str, int]
    runtime_ms: float
    note: str
    probability: float | None = None
    expected_energy: float | None = None

def benchmark_classical(qubo: QUBO) -> BenchmarkResult:
    start=perf_counter(); result:OptimizationResult=exact_minimize(qubo); elapsed=(perf_counter()-start)*1000
    return BenchmarkResult(result.method,result.energy,result.assignment,elapsed,"Exact enumeration baseline")

def benchmark_qaoa(qubo: QUBO,p:int=1) -> BenchmarkResult:
    start=perf_counter(); result:QAOAResult=simulate_qaoa(qubo,p=p); elapsed=(perf_counter()-start)*1000
    return BenchmarkResult(result.method,result.energy,result.assignment,elapsed,"Dependency-free statevector simulation; not quantum hardware",result.probability,result.expected_energy)

def benchmark_suite(qubo: QUBO) -> list[BenchmarkResult]:
    return [benchmark_classical(qubo), benchmark_qaoa(qubo)]
