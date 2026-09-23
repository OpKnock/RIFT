# Changelog

All notable changes to RIFT. Versions follow SemVer; `0.x` signals a lab system, not a certified product.

## [Unreleased]
### Fixed
- `/api/demo` no longer crashes on tuple-keyed QUBO JSON (quadratic terms serialize as `"a,b"` strings).
- Oversized request bodies are consumed-and-discarded before the 413 response, keeping HTTP/1.1 keep-alive connections in sync (previously aborted sockets on some platforms).
- `experiment_runs.user_id` column added (migration 005); the API already wrote it, which would have failed live inserts.
### Added
- Server-side execution: `rift.runner.run_spec` + `POST /api/experiments/{id}/execute` closes the CREATE → RUN → PERSIST → REPRODUCE loop with fingerprint-matched run records.
- `RIFT_REQUIRE_USER_ID=true` enforcement for persistence POSTs (previously documented but unenforced).
- Schema/code consistency tests fail the suite when API payload keys drift from migrations.
- Guardian feasibility flags in CHAOS UI (`REJECTED UNDER PERTURBATION`); regression tests for Guardian rejection and blocked-exit penalty semantics.

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
