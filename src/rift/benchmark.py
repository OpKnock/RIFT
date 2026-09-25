from dataclasses import dataclass
from random import Random
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

def _neighbors(qubo: QUBO, assignment: dict[str, int]) -> list[dict[str, int]]:
    out = []
    for i, name in enumerate(qubo.variables):
        flip = dict(assignment)
        flip[name] = 1 - flip[name]
        out.append(flip)
    return out

def simulated_annealing(qubo: QUBO, *, seed: int = 7, steps: int = 200,
                        start_temp: float = 2.0, end_temp: float = 0.01) -> BenchmarkResult:
    """Seeded single-bit-flip simulated annealing (classical heuristic baseline).

    Deterministic for a fixed seed. Never claims optimality: report the
    optimality gap against exact_minimize on small instances.
    """
    import math
    start = perf_counter()
    rng = Random(seed)  # nosec B311 -- seeded benchmark heuristic, not cryptographic use
    current = {name: rng.randint(0, 1) for name in qubo.variables}
    current_energy = qubo.energy(current)
    best, best_energy = dict(current), current_energy
    for step in range(max(1, steps)):
        temp = start_temp + (end_temp - start_temp) * step / max(1, steps - 1)
        candidate = dict(current)
        flip = rng.choice(qubo.variables) if qubo.variables else None
        if flip is None:
            break
        candidate[flip] = 1 - candidate[flip]
        energy = qubo.energy(candidate)
        if energy < current_energy or (temp > 0 and rng.random() < math.exp(-(energy - current_energy) / temp)):
            current, current_energy = candidate, energy
            if energy < best_energy:
                best, best_energy = dict(candidate), energy
    elapsed = (perf_counter() - start) * 1000
    return BenchmarkResult("simulated-annealing", best_energy, best, elapsed,
                           f"Seeded SA baseline (seed={seed}, steps={steps}); heuristic, gap vs exact reported")

def tabu_search(qubo: QUBO, *, seed: int = 7, steps: int = 200, tenure: int = 5) -> BenchmarkResult:
    """Seeded tabu search over single-bit-flip neighborhood (classical baseline).

    Deterministic for a fixed seed. Aspiration: a tabu move that improves the
    best-known energy is always accepted. Heuristic: report the optimality gap.
    """
    start = perf_counter()
    rng = Random(seed)  # nosec B311 -- seeded benchmark heuristic, not cryptographic use
    current = {name: rng.randint(0, 1) for name in qubo.variables}
    current_energy = qubo.energy(current)
    best, best_energy = dict(current), current_energy
    tabu: dict[str, int] = {}
    for step in range(max(1, steps)):
        options = []
        for neighbor in _neighbors(qubo, current):
            flipped = next(n for n in qubo.variables if neighbor[n] != current[n])
            energy = qubo.energy(neighbor)
            options.append((energy, flipped, neighbor))
        options.sort(key=lambda item: item[0])
        chosen = None
        for energy, flipped, neighbor in options:
            if energy < best_energy or tabu.get(flipped, -1) < step:
                chosen = (energy, flipped, neighbor)
                break
        if chosen is None:
            energy, flipped, neighbor = options[0]
            chosen = (energy, flipped, neighbor)
        energy, flipped, neighbor = chosen
        tabu[flipped] = step + max(1, tenure)
        current, current_energy = neighbor, energy
        if energy < best_energy:
            best, best_energy = dict(neighbor), energy
    elapsed = (perf_counter() - start) * 1000
    return BenchmarkResult("tabu-search", best_energy, best, elapsed,
                           f"Seeded tabu baseline (seed={seed}, steps={steps}, tenure={tenure}); heuristic, gap vs exact reported")

def benchmark_suite(qubo: QUBO) -> list[BenchmarkResult]:
    return [benchmark_classical(qubo), benchmark_qaoa(qubo),
            simulated_annealing(qubo), tabu_search(qubo)]
