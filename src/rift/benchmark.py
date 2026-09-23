from dataclasses import dataclass
from time import perf_counter
from .optimizer import QUBO, OptimizationResult, exact_minimize

@dataclass(frozen=True)
class BenchmarkResult:
    method: str
    energy: float
    assignment: dict[str, int]
    runtime_ms: float
    note: str

def benchmark_classical(qubo: QUBO) -> BenchmarkResult:
    start = perf_counter()
    result: OptimizationResult = exact_minimize(qubo)
    elapsed = (perf_counter() - start) * 1000
    return BenchmarkResult(result.method, result.energy, result.assignment, elapsed, "Exact enumeration baseline")

def benchmark_suite(qubo: QUBO) -> list[BenchmarkResult]:
    return [benchmark_classical(qubo)]
