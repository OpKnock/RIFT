# RIFT Architecture

## Pipeline

State → World Model → Counterfactual Futures → CHAOS → Candidate Policies → QUBO → Classical/Quantum Optimizer → GUARDIAN → Robust Decision.

## Boundaries
- rift.models: domain types
- rift.counterfactual: intervention enumeration and simulation
- rift.adversarial: failure-state search
- rift.optimizer: QUBO and optimizer adapters
- rift.multivariable: exact binary policy enumeration and transparent quadratic projection
- rift.supabase_store: optional persistence adapter
- rift.settings: server-side env configuration (no secret leakage)
- rift.billing: Lemon Squeezy provider boundary (checkout + webhook verify)
- rift.verifier: hard constraints
- rift.engine: orchestration
- rift.cli: local demo

## Principles
1. Deterministic experiments with explicit seeds.
2. Pure domain logic independent of HTTP/database.
3. Pluggable optimizers with explicit backend metadata.
4. Verification cannot be bypassed by an optimizer score.
5. Every recommendation exposes assumptions and evidence.
6. Quantum execution is experimental; no automatic advantage is claimed.

## Persistence
Supabase stores experiments and runs. The engine remains runnable without a network connection.
Server env: `RIFT_SUPABASE_URL` / `RIFT_SUPABASE_KEY` (legacy `SUPABASE_*` fallbacks).
Full setup: `docs/supabase-setup.md`.

## Billing boundary
`rift.billing` + `POST /api/billing/checkout` + `POST /api/billing/webhook`.
Disabled by default; configured via `RIFT_LEMON_SQUEEZY_*` server env.
Full setup: `docs/billing.md`.

## Planned API
POST /experiments
POST /experiments/{id}/run
GET /experiments/{id}
GET /runs/{id}
POST /benchmarks
GET /health
GET /api/persistence/status
POST /api/experiments
GET /api/experiments/{id}
POST /api/experiments/{id}/runs
GET /api/experiments/{id}/runs
GET /api/runs/{id}
GET /api/billing/status
POST /api/billing/checkout
POST /api/billing/webhook

## Multi-variable optimization boundary
For small policy spaces, exact robust enumeration is the reference implementation. When a robust Boolean objective contains higher-order interactions, RIFT may project it to linear/quadratic terms so QAOA can operate on a QUBO. The projection is explicitly approximate and is never presented as an exact reformulation.
