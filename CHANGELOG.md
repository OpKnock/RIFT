# Changelog

All notable changes to RIFT. Versions follow SemVer; `0.x` signals a lab system, not a certified product.

## [Unreleased]
### Added
- v1 data platform (`rift.health.observations/adapters/timeline`): canonical Observation with validation + unit normalization, FHIR R4 Observation import subset, CSV/JSON adapters, multi-observation-day timeline with median estimation and reproducible day indices.
- Model registry + provenance (`rift.health.model_registry`): versioned `cardiac-strain-v1` pin, live weights-drift detection, deterministic prediction IDs stamped on snapshots, evidence-served deployment gate (clinical-use closed).
- Decision table (`rift.health.decision`): policy comparison joined from robust ranking + trajectories, in snapshots.
- Migration `006_model_registry.sql`: registry + prediction-audit tables (service-role only; unapplied, no live project).
- Patient Digital Twin healthcare demo (`src/rift/health/`, `GET /api/twin/demo`, doctor dashboard): synthetic EHR + replayable 14-day wearable stream → personal baselines → bounded transition model → 24h cardiac-strain risk → FORESIGHT trajectories/counterfactuals via the generic engine → robustness spread → display-safety Guardian → reasons. Decision support only; synthetic, not validated.
- Phase-3 validation (`rift.health.evaluate` + backtest metrics: 1-day MAE, event agreement, Brier, interval coverage, counterfactual sanity); baseline uses strictly prior observations (no leakage); `WearableSource` replay/live seam; risk intervals labeled demo/not-calibrated.
- Phase-4 evidence: independent outcome labels (observed-criteria rule, breaking the self-agreement circularity), 60-day series with calibration/holdout split, rolling backtest with onset lead/lag, sensor-noise stress sweep, `PublicDatasetSource` CSV adapter, `GET /api/twin/evidence` + dashboard evidence panel.
- Phase-5 evidence hardening: measurement-jitter path (day-over-day excess over MAD widens uncertainty; stress uncertainty now rises 0.085→0.11 with noise), threshold tradeoff table proving misses are structural not threshold artifacts, overclaim-language regression guard, dashboard stress table with explicit response note.
- Phase-7 external validation: `evaluate.external_validation` replays an independent synthetic series (seed/spells disjoint from development) with model, threshold, and Platt params frozen; reports ECE/Brier, WLS slope/intercept, Wilson CIs, coverage, and small-sample warnings; `GET /api/twin/evidence` gains a no-refit `external_validation` block plus dashboard section. Synthetic-to-synthetic only — real-dataset execution stays pending.
- Sample-adequacy verdict: external samples are scored against the ~100-event/100-non-event bar (current 5/54 → `limited`, dashboard-visible); good point estimates cannot upgrade the calibration claim.
- Sensitivity mechanism (not threshold gaming): bounded velocity term (rising HR / shrinking sleep, capped, deterioration-only) lifts spell onsets; held-out sensitivity 0.33 with specificity 0.93 intact; empirical reliability analysis (ECE 0.22 — probabilities explicitly NOT calibrated).
- Calibration repair: Platt scaling fit on calibration days only (order-preserving by construction), test-set ECE 0.198→0.058 with Brier flat; operating threshold and weights untouched; fit chose a near-constant map, reported as a small-sample finding.
- Bandit SAST gate in CI (`security` job, zero-findings baseline); supply-chain audit of the declared dependency closure clean.
- Verified JWT identity (`rift.auth_jwt`, HS256 via `RIFT_SUPABASE_JWT_SECRET`): gated endpoints authenticate `Bearer` tokens and derive `user_id` from `sub`; spoofed `user_id` values are ignored; `none`/foreign algorithms, bad signatures, and expired tokens fail closed with 401.
- In-process rate limiting (`rift.ratelimit`, `RIFT_RATE_LIMIT_ENABLED=true`): fixed-window budgets with a stricter `.../execute` scope, `429 + Retry-After`; static assets uncounted.
- Frontend access-token field (SETTINGS) auto-attached to save/execute calls.
- Frontend SAVE & EXECUTE panel: persists the current scenario spec and runs it server-side with fingerprinted results; honestly disabled until Supabase is configured.
- Server-side execution: `rift.runner.run_spec` + `POST /api/experiments/{id}/execute` closes the CREATE → RUN → PERSIST → REPRODUCE loop with fingerprint-matched run records.
- `RIFT_REQUIRE_USER_ID=true` enforcement for persistence POSTs (previously documented but unenforced).
- Schema/code consistency tests fail the suite when API payload keys drift from migrations.
- Guardian feasibility flags in CHAOS UI (`REJECTED UNDER PERTURBATION`); regression tests for Guardian rejection and blocked-exit penalty semantics.
- Missing persistence rows now return `404 not_found` (was `502`); engine execution failures return `500 execution_error` with the experiment marked `failed`; `variant_id` must be a string.
- Removed dead `idx` computation in the QAOA simulator.
- Cross-user experiment/run reads verified denied-and-allowed via fake-store tests; entropy helpers documented as nats (rescaled inputs, undivided output).
### Fixed
- Bandit triage: billing checkout URL pinned to an allowlist; best-effort `except: pass` paths now emit diagnostics (three justified `nosec` cases documented); optimizer `assert` replaced with an explicit raise.
- `/api/demo` no longer crashes on tuple-keyed QUBO JSON (quadratic terms serialize as `"a,b"` strings).
- Oversized request bodies are consumed-and-discarded before the 413 response, keeping HTTP/1.1 keep-alive connections in sync (previously aborted sockets on some platforms).
- `experiment_runs.user_id` column added (migration 005); the API already wrote it, which would have failed live inserts.

## [0.6.0] — Counterfactual Laboratory release candidate
### Engine and science
- Exact robust enumeration baseline with QAOA statevector comparison (expectation + lowest-cost-tail CVaR, α=0.25).
- Least-squares quadratic projection for multi-variable QAOA with reported max/mean objective gap.
- Independent Guardian verification over nominal + every declared perturbation.
- Bounded scenario inputs, policy/perturbation limits, and explicit simulator caps (12 qubits, 16 policy vars).

### Product boundaries
- Serializable experiment specs with fingerprints (`src/rift/experiments.py`).
- Unified Supabase adapter with lifecycle/status endpoints (migrations 001→004).
- Optional service-token gate + server-side ownership checks.
- Lemon Squeezy checkout/webhook boundary with HMAC verification, idempotent processing, subscription lifecycle mapping, and server-derived entitlements.
- Hardened HTTP layer: request IDs, structured logs, security headers, bounded payloads, sanitized errors.

### Frontend, CI, docs
- Lab UI with system status, local history, settings/capabilities, reproducibility metadata, and honest error states.
- CI runs pytest plus migration/secret/version validation gates.
- Docs: setup, API, experiments, billing, security (with residual risks), deployment (+Dockerfile), review policy, release checklist.
