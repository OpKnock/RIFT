# Real Hardware Run Record (executed 2026-09-26, Phase 11 DONE)

## Execution

- Backend: `ibm_kingston`, 156-qubit Heron, via IBM Quantum Open Plan (free tier).
- Instance: 2-variable reference QUBO (`a:-2, b:-1, ab:+3`), QAOA p=1, 1,000 shots.
- Path: `rift.qpu.solve_on_ibm` — angles optimized locally (Aer statevector + COBYLA), final circuit transpiled for Kingston, sampled with SamplerV2.

## Result

| Measure | Value |
|---|---|
| Hardware energy | -2.0 |
| Hardware assignment | {a: 1, b: 0} |
| Exact optimum | -2.0 |
| Optimality gap | 0.0 |
| Wall time | 17.6 s |

## What this proves and what it does not

- Proves: the full hardware path works end-to-end against a live QPU (auth → backend → transpile → sample → decode), with zero gap on the reference instance.
- Does NOT prove: quantum advantage. A 2-variable instance is trivially solvable exactly; per `docs/benchmark-methodology.md` §4–5, an advantage claim needs same-instance comparisons against the full classical battery with statistical + practical significance. Default conclusion stands: "no quantum advantage demonstrated."
- Credential hygiene: the API token was supplied by the operator, held in process memory only (env var), never written to disk or the repo, and cleared after the run. The operator was advised to rotate the key since it transited chat/shell history.
