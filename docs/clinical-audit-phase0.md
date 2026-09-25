# Phase-0 Audit: What RIFT Actually Is (v1.0.0, commit-pinned)

Source-level audit of all 66 Python modules, 15 API endpoints, 7 migrations,
29 test files, CI workflows, containers, and datasets. Classification scale:

- **production-capable** — correct, tested, deployable as software
- **research-grade** — correct methodology, synthetic/unvalidated data
- **demonstration-only** — works for the demo, not a real claim
- **placeholder** — interface exists, implementation intentionally absent
- **unimplemented** — does not exist
- **unsafe for clinical use** — must never touch patients as-is

## Engine core — production-capable (as software)

| Component | Files | Class | Evidence |
|---|---|---|---|
| Counterfactual futures | `counterfactual.py`, `futures.py`, `engine.py` | production-capable | deterministic, tested |
| CHAOS adversarial search | `adversarial.py`, `health/robustness.py` | research-grade | declared sets, measured spread; failure taxonomy synthetic |
| Exact QUBO + robust objective | `robust_qubo.py`, `optimizer.py` | production-capable | exact ≤2-var fitting + equivalence tests |
| Multivariable projection | `multivariable.py` | research-grade | approximate, gap reported, never hidden |
| CVaR (lowest-cost tail) | `cvar.py` | production-capable | documented non-standard definition |
| QAOA statevector simulator | `qaoa.py` | demonstration-only | correct math, simulator only |
| QPU adapter | `qpu.py` | placeholder | raises `NotImplementedError` by design |
| Verifier / limits / runner / experiments | `verifier.py`, `limits.py`, `runner.py`, `experiments.py` | production-capable | bounds fail loudly, fingerprinted specs |
| Benchmark suite | `benchmark.py` | research-grade | exact vs sim only; no MILP/CP-SAT/SA/tabu yet |

## Patient twin pipeline — research-grade with demonstration-only model

| Component | Files | Class | Evidence |
|---|---|---|---|
| Canonical observations | `health/observations.py` | production-capable | strict validation, offsets, fail-closed, tested |
| Adapters (FHIR/CSV/JSON) | `health/adapters.py`, `fhir_clinical.py` | production-capable (boundary) | tested vs fixture; **no live source** |
| Terminology (LOINC 2.83) | `health/terminology.py` | research-grade | narrow subset; SNOMED/RxNorm absent |
| Timeline (hour/day/week) | `health/timeline.py` | production-capable | patient-scoped buckets, coverage report |
| Estimators / drift | `health/estimation.py`, `health/drift.py` | research-grade | explicit thresholds, synthetic data |
| Baselines (no leakage) | `health/baseline.py` | production-capable | `day_index < t` enforced, tested |
| **Risk weights** | `health/risk.py` | demonstration-only / **unsafe for clinical use** | hard-coded additive constants, unfitted |
| **Transition model** | `health/transition.py` | demonstration-only / **unsafe for clinical use** | file header says SYNTHETIC DEMO WEIGHTS |
| FORESIGHT trajectories | `health/foresight.py` | research-grade | reuses generic engine; simulated scenarios |
| Twin loop + provenance | `health/twin.py` | production-capable | deterministic IDs, telemetry wired |
| Decision tables + sensitivity | `health/decision.py` | research-grade | honest comparison machinery |
| Evaluation (backtest/calibration/external) | `health/evaluate.py` | research-grade | independent outcome rule; **all synthetic** |
| Evidence bundles | `health/evidence.py` | production-capable | versioned, HMAC-signed, adequacy-gated |
| Model registry | `health/model_registry.py` | production-capable | versions, promotion/rollback/audit, closed gate |
| Training framework | `health/training.py` | research-grade | manifests/splits/hashes; **weight fitting deliberately absent** |
| Cohort / subgroups | `health/cohort.py`, `health/subgroups.py` | research-grade | synthetic patients, deterministic seeds |
| Prospective locks | `health/prospective.py` | demonstration-only | immutable locks; **in-memory only** |
| **Outcome rule** | `evaluate.OUTCOME_RULE` | demonstration-only / **unsafe for clinical use** | synthetic HR/sleep/HRV thresholds, not a clinical endpoint |

## Guardian 2.0 — production-capable (as software boundary)

16 rules (G-001…G-016), 6 stages, WITHHOLD/WARN/ALLOW, optimizer cannot override. Tested including adversarial cases. **Not** a certification, not clinical review, no per-rule clinical owner yet.

## Platform — production-capable (as software)

| Component | Class | Evidence |
|---|---|---|
| HTTP API (15 endpoints) | production-capable | boundaries, 4xx/5xx discipline, request IDs |
| Auth (open/token/JWT) + ownership | production-capable | fail-closed 401s, 403 mismatch, spoof-proof JWT |
| Rate limiting | production-capable | fixed-window, 429+Retry-After, tested |
| Billing webhooks | production-capable | HMAC, DB-unique idempotency, resume-on-retry, 502-retry |
| Supabase migrations 001→007 | production-capable | additive/idempotent, RLS, matches store; **no live project** |
| Monitoring (`/metrics` contract) | production-capable | single vocabulary, contract-tested; delivery absent by design |
| Docker production image | production-capable | builds in CI + smoke test; root image is legacy demo |
| K8s manifests | research-grade | complete templates, JWT required in prod; **no live cluster** |
| CI (test/validate/security/build) | production-capable | 223 green, Bandit/Semgrep 0, constraints-pinned |
| Accessibility configs | placeholder | pa11y/axe/Lighthouse configs exist; manual, non-blocking |

## Data — the honest boundary

| Dataset | Class |
|---|---|
| Synthetic demo/cohort series | demonstration-only (pipeline validation only) |
| BIDSleep / exam-stress / sepsis / CHFDB seams | research-grade ingestion; real bytes, **not** model validation |
| Committed `.LEGACY.csv` | retired artifact, must not be used |
| Governed clinical cohort | **unimplemented** (external: hospital, IRB, DUA) |

## Hard-coded clinical assumptions (complete list)

`risk.RISK_WEIGHTS` · `transition.TRANSITION_WEIGHTS` · `STRAIN_THRESHOLD = 0.6` · `evaluate.OUTCOME_RULE` · `PHYSIOLOGICAL_BOUNDS` · `100/100` adequacy bar. All explicit constants, all synthetic, all **unsafe for clinical use** until replaced by fitted, validated values.

## Synthetic-data shortcuts (complete list)

Demo EHR/wearables · seeded spell schedules · synthetic outcome rule · synthetic external series · unfitted weights · in-memory prospective ledger · fixture-tested FHIR · unexecuted WFDB full-cohort CI.

## README-vs-reality check

The README claims: research prototype, synthetic demo, no clinical validation, no production deployment, simulator ≠ hardware, 223 tests, SAST clean. **All verified accurate** against this audit. No component is preserved merely for impressiveness; placeholders (`qpu.py`, prospective persistence, live integrations) are labeled as such in code and docs.
