# Clinical Roadmap (living document)

Master specification adapted to RIFT's actual state. Status per phase:
**DONE** (code-complete, tested) · **PARTIAL** (scaffolding done, needs data/world) · **EXTERNAL** (cannot be done in this repo). Evidence basis: `docs/clinical-audit-phase0.md`. Update this file — never the phase-matrix — when gates move.

Mission: help clinicians make safer, better-informed decisions under uncertainty. Quantum is a plug-in solver, never a dependency. No clinical-validity, medical-device, or quantum-advantage claim without evidence.

## Phase status

| # | Phase | Status | Done | Missing |
|---|---|---|---|---|
| 0 | Audit the repo | DONE | `docs/clinical-audit-phase0.md`, 223 tests, SAST clean | — |
| 1 | Narrow use case | DONE | 24h cardiac-strain risk, hospitalized adults, decision-support-only; prediction≠recommendation≠action | Formal intended-use statement for regulators (see 17) |
| 2 | Real clinical data | PARTIAL | FHIR R4 subset, validation, units, provenance, fail-closed ingestion | HL7; live source; notes/devices at scale |
| 3 | Dataset program | PARTIAL | Splits, subgroups, adequacy gates, leakage tests | Governed TRAIN→PROSPECTIVE cohorts (hospital/IRB/DUA) |
| 4 | Validated models | PARTIAL | Registry, versions, promotion/rollback/approval | Fitted weights; calibration on real data; approved status |
| 5 | Twin properly | PARTIAL | State/history/uncertainty/provenance | Transition model evaluated on real trajectories |
| 6 | Defensible CHAOS | PARTIAL | Declared sets, measured degradation | Clinically-justified failure-mode taxonomy |
| 7 | Optimization layer | DONE | Objective/constraints exposed, sensitivity analysis | — |
| 8 | Legitimate QUBO | DONE | Exact fitting + equivalence tests, reported gaps | — |
| 9 | No fake advantage | PARTIAL | Zero claims; exact-vs-sim benchmarks | Full classical battery (MILP/CP-SAT/SA/tabu) → **in progress below** |
| 10 | Define advantage | DONE | Policy: "no advantage demonstrated" by default | — |
| 11 | Real hardware | EXTERNAL | Gated `qpu.py` boundary | Credentials, hardware, full-benchmark runs |
| 12 | Formal Guardian | PARTIAL | 16 rules, stages, tested, unbypassable | Per-rule clinical owner + hazard mapping → **in progress below** |
| 13 | Uncertainty/abstention | PARTIAL | Decomposition, calibration repair, WITHHOLD | Abstention-harm study (needs clinical data) |
| 14 | Clinician UI + audit | PARTIAL | Full-explanation dashboard | ACCEPT/REJECT/OVERRIDE/REQUEST REVIEW + audit → **in progress below** |
| 15 | Silent prospective | PARTIAL | Immutable locks, reconcile API | Durable ledger, deployment, silent comparison |
| 16 | Clinical validation | EXTERNAL | Study-protocol template (below) | Hospital, endpoints, SAP, sample, review |
| 17 | Regulatory | EXTERNAL | Strategy notes (below) | Qualified professionals, jurisdiction assessment |
| 18 | QMS | PARTIAL | QMS skeleton (below) | Operated QMS, audits, CAPA history |
| 19 | Prod security | PARTIAL | Auth/HMAC/SSRF/RLS/scanning/rate-limit | Pen test, threat model, MFA, rotation, immutable logs, backup/DR, incident response |
| 20 | Reliability | PARTIAL | Fail-closed semantics, probes/HPA/PDB | RTO/RPO/SLOs, tested optimizer-outage fallback → **in progress below** |
| 21 | Observability | PARTIAL | Metric contract, rules, dashboards | Live alert delivery; override/acceptance tracking (needs 14) |
| 22 | Continuous monitoring | PARTIAL | Drift code, monitoring skeleton | Deployed loop, operated releases |
| 23 | Change control | PARTIAL | Registry + audit log substrate | Formal operated process |
| 24 | Reproducibility | DONE | Seeds, fingerprints, manifests, `constraints.txt`, deterministic IDs | — |
| 25 | Publication | EXTERNAL | `evidence-sheet.md` artifact pattern | Papers, peer review |

## Completed in the web-gathering cycle (code-addressable + executed)

- Real PhysioNet ingestion executed: CHFDB `chf01` 250 Hz bytes → 333 reference beats → HR 66.5 bpm / HRV 39.6 ms through the repo's own adapter (`docs/real-data-ingestion.md`). **Additional 32 records from 7 more open datasets ingested (NSRDB, FANTASIA, EDB, LTAFDB, QTDB, total 1.1M+ beats) — `docs/proxy-fit-open-data.md`**. Phase 2 → PARTIAL (credentialed MIMIC still external).
- Qiskit Aer QAOA backend: real SDK execution with shot sampling, matches exact on the reference instance; IBM hardware path implemented and fail-closed with verified setup steps (`src/rift/qpu.py`, `tests/test_qpu_aer.py`). **First hardware run EXECUTED 2026-09-26: `ibm_kingston`, gap 0.0 (see `docs/real-hardware-run.md`). Phase 11 → DONE (execution); advantage comparison per methodology still open.**
- Crash-safe ledgers: `JsonlStore` (fsync append, strict replay) backs prospective + review ledgers via `RIFT_PROSPECTIVE_LEDGER` / `RIFT_REVIEWS_LEDGER` (`tests/test_durable.py`). Phases 14/15 → PARTIAL (deployment + backup ops external).
- Abstention-harm analysis module (`health/abstention.py`, `tests/test_abstention.py`). Phase 13 → PARTIAL (harm study external).
- Threat model, incident runbook with backup/restore (`docs/threat-model.md`, `docs/incident-runbook.md`). Phases 19/20 → PARTIAL (pen test, drills, operated RTO external).
- External gates doc with live-verified links: IBM Open Plan terms, PhysioNet credentialing, FDA Q-Sub/software guidance (`docs/external-gates.md`). Phase 17 → PARTIAL (professionals + submission external).

## Completed in the previous cycle (code-addressable)

- Benchmark battery: simulated annealing + tabu search vs QAOA sim + pre-registered methodology doc (`docs/benchmark-methodology.md`, `tests/test_benchmark_heuristics.py`). Phase 9 → PARTIAL (MILP/CP-SAT + hardware external).
- Clinician review actions with audit trail: append-only hash-chained ledger, `GET/POST /api/twin/reviews`, dashboard CLINICIAN REVIEW panel, review counts in `/metrics` (`rift_clinician_reviews_total`). Phase 14 → PARTIAL (durable persistence + live tracking external).
- SLO/RTO/RPO targets + optimizer-outage fallback (`src/rift/service_levels.py`, `tests/test_service_levels.py`). Phase 20 → PARTIAL (operated infra external).
- Guardian rule registry: owner/version/evidence per rule G-001…G-016 (`RULE_METADATA`, `tests/test_guardian_metadata.py`). Phase 12 → PARTIAL (owner sign-off external).
- Study-protocol template, QMS skeleton, traceability matrix. Phases 16/18/23 → PARTIAL (operated processes external).

## Definitions (binding)

- **Production-ready**: technical + clinical + safety + security + human-factors + interoperability + prospective + regulatory + QMS + deployment + monitoring validation. Never tests-alone, demo-alone, AUROC-alone, install-alone, or hardware-alone.
- **Quantum advantage**: statistically + practically meaningful win vs strongest classical baseline, same instances, predeclared methodology. Otherwise: "quantum optimization experiment."
