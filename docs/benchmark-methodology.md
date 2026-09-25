# Benchmark Methodology (pre-registered, v1)

Binding rules for any solver comparison in RIFT, including future QPU runs.
Violating any rule invalidates the comparison; such results must be labeled
"exploratory," never "advantage."

## Battery (all in `src/rift/benchmark.py`, stdlib-only, seeded)

| Method | Type | Optimality |
|---|---|---|
| `exact-enumeration` | exhaustive | optimal (small instances only) |
| `qaoa-statevector-simulator` | quantum-inspired classical simulation | approximate, gap reported |
| `simulated-annealing` | classical heuristic (seed 7, 200 steps) | approximate, gap reported |
| `tabu-search` | classical heuristic (seed 7, 200 steps, tenure 5) | approximate, gap reported |

MILP / CP-SAT are not vendored (no scipy/OR-Tools dependency). Adding them
later requires this doc to be versioned and the new baselines back-reported
on the same instance set.

## Rules

1. Same instance set for every method; instances fingerprinted (`benchmark_suite` inputs logged by callers).
2. Heuristic seeds fixed and published (`seed=7`); seed-sensitivity runs are exploratory unless pre-registered.
3. Report per method: best energy, optimality gap vs exact (where exact feasible), runtime_ms, assignment. Never report wins without gaps.
4. QAOA-sim-vs-heuristic is **not** a quantum result. A hardware claim additionally requires: real QPU execution, queue/transpile overhead included, same instances, statistical significance, practical significance.
5. Default conclusion when no comparison meets these rules: "no quantum advantage demonstrated."
6. `note` field on every `BenchmarkResult` states the method's limitation; UIs must surface it, never truncate it.

## Status

Battery implemented and tested (`tests/test_benchmark_heuristics.py`): 4 methods,
deterministic, gaps non-negative on the reference instance. Full classical
battery (MILP/CP-SAT) and hardware runs remain EXTERNAL (see `docs/clinical-roadmap.md`).
