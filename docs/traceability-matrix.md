# Requirements Traceability Matrix (initial)

Requirement → design → verification. Status: **unverified-by-test** rows need
a test or a documented external gate; a requirement with neither is void.

| Req | Requirement | Design | Verification | Status |
|---|---|---|---|---|
| R-001 | Predictions carry patient/time provenance | `health/twin.py`, `observations.py` | 223-test suite (provenance subset) | verified |
| R-002 | No prediction on inadequate evidence | 100/100 adequacy gate, WITHHOLD | adequacy tests | verified |
| R-003 | Guardian cannot be bypassed by optimizer | stage ordering, tests incl. adversarial | guardian tests | verified |
| R-004 | Evidence bundles are tamper-evident | HMAC-signed, versioned schema | evidence tests | verified |
| R-005 | Model versions are gated and auditable | `model_registry.py` promotion/rollback/approval | registry tests | verified |
| R-006 | Solver comparisons follow pre-registered methodology | `docs/benchmark-methodology.md`, `benchmark.py` | `test_benchmark_heuristics.py` | verified |
| R-007 | Benchmark notes surface limitations | `BenchmarkResult.note` required | methodology §6 (UI wiring pending) | partial |
| R-008 | Clinician review actions are audited | `health/reviews.py` ledger + `POST /api/twin/reviews` + dashboard panel | `test_reviews.py`, `test_review_api.py` | verified (durable persistence external) |
| R-009 | Optimizer outage degrades safely | `service_levels.py` targets + `minimize_with_fallback` | `test_service_levels.py` | verified (operated RTO/RPO external) |
| R-010 | Each Guardian rule has clinical owner/version | `guardian.RULE_METADATA` + `rule_metadata()` | `test_guardian_metadata.py` | verified (owner assignment external) |
| R-011 | Silent prospective uses immutable locks | `health/prospective.py` | prospective tests | partial (deployment external) |
| R-016 | Ledgers survive restarts | `durable.JsonlStore`, env-wired ledgers | `test_durable.py` | verified (backup ops external) |
| R-017 | Quantum path is real SDK code, hardware-executed | `qpu.solve_on_aer` / `solve_on_ibm` | `test_qpu_aer.py` + `docs/real-hardware-run.md` (ibm_kingston, gap 0.0) | verified |
| R-018 | Abstention harm is measured, not assumed | `health/abstention.py` | `test_abstention.py` | verified (harm study external) |
| R-012 | Weights are fitted, never hard-coded | training manifests; fitting absent | — | external (data + fitting) |
| R-013 | Validation precedes any clinical claim | study protocol template | — | external (hospital/IRB) |
| R-014 | QPU claims require hardware evidence | gated `qpu.py`; methodology §4-5 | — | external (hardware) |
| R-015 | Protected data stays protected | auth, RLS migrations, HMAC webhooks, SSRF guard | auth/api tests | partial (live verification external) |

Rule: adding a feature without adding its row here violates change control.
