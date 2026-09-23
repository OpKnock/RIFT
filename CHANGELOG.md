# Changelog

All notable changes to RIFT. Versions follow SemVer; `0.x` signals a lab system, not a certified product.

## [Unreleased]
### Added
- Frontend SAVE & EXECUTE panel: persists the current scenario spec and runs it server-side with fingerprinted results; honestly disabled until Supabase is configured.
### Fixed
- `/api/demo` no longer crashes on tuple-keyed QUBO JSON (quadratic terms serialize as `"a,b"` strings).
- Oversized request bodies are consumed-and-discarded before the 413 response, keeping HTTP/1.1 keep-alive connections in sync (previously aborted sockets on some platforms).
- `experiment_runs.user_id` column added (migration 005); the API already wrote it, which would have failed live inserts.
### Added
- Server-side execution: `rift.runner.run_spec` + `POST /api/experiments/{id}/execute` closes the CREATE → RUN → PERSIST → REPRODUCE loop with fingerprint-matched run records.
- `RIFT_REQUIRE_USER_ID=true` enforcement for persistence POSTs (previously documented but unenforced).
- Schema/code consistency tests fail the suite when API payload keys drift from migrations.
- Guardian feasibility flags in CHAOS UI (`REJECTED UNDER PERTURBATION`); regression tests for Guardian rejection and blocked-exit penalty semantics.
- Missing persistence rows now return `404 not_found` (was `502`); engine execution failures return `500 execution_error` with the experiment marked `failed`; `variant_id` must be a string.
- Removed dead `idx` computation in the QAOA simulator.
- Cross-user experiment/run reads verified denied-and-allowed via fake-store tests; entropy helpers documented as nats (rescaled inputs, undivided output).

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
