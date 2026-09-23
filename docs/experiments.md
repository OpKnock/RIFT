# RIFT experiment model

An experiment is a reproducible, fingerprintable spec — not a pile of callables.

## Spec fields (`src/rift/experiments.py`)
`name` · `scenario_name` (`smart-building-emergency`) · `initial_state` (bounded numerics) ·
`perturbations` (≤32 numeric deltas) · `policy_variables` (unique, ≤16) ·
`optimizer` (`exact` | `qaoa-expectation` | `qaoa-cvar`) · `backend`
(`statevector-simulator`) · `seed` · `engine_version` · `description` · `status`
(`created` → `configured` → `running` → `succeeded` | `failed`).

## Reproducibility
- `spec.fingerprint()` = SHA-256 over canonical JSON; stored in `experiments.fingerprint`.
- The demo payload echoes `reproducibility: {engine_version, backend, perturbations, policy_variables}`.
- Persisted rows carry `engine_version`, `seed`, `optimizer_config`, `backend`, `perturbations`, `policy_variables` (migration 004) so a stored experiment can be re-executed from its row.

## Why not serialize `Scenario` directly?
`rift.models.Scenario` holds Python callables (`transition`, `objective`, `check`) which are not JSON-safe. The spec layer references scenarios by name and validates numeric inputs, keeping the product boundary serializable while the engine stays pure.

## Lifecycle endpoints
Create (`POST /api/experiments`) → run records (`POST /api/experiments/{id}/runs`) → inspect (`GET ...`) → compare (fingerprints) → reproduce (re-POST the stored spec).

## Server-side execution
`POST /api/experiments/{id}/execute` loads the stored spec, runs it via
`rift.runner.run_spec` (optimizer/backend from the row), writes an
`experiment_runs` row with metrics + fingerprint, and marks the experiment
`succeeded` (or `failed` with error info on invalid specs). The returned
`result` echoes `effective_policy_variables`, `effective_perturbations`,
`spec_fingerprint`, `duration_ms`, and the full Guardian verdict, so any
stored run can be re-executed and compared byte-for-byte on policy, costs,
and fingerprint.

## Blocked-exit semantics
`stairwell_b` means "route via stairwell B"; `blocked_b_penalty` is a risk
penalty added when B is marked blocked. It does not reduce corridor
capacity — a penalty model, not a physical closure. Pinned by
`tests/test_scenario_semantics.py`.
