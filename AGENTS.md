# AGENTS.md — working map for RIFT

RIFT is a counterfactual decision lab: world state → futures → CHAOS → robust/QUBO optimization (exact vs QAOA simulator) → Guardian verification. Honest labels only: simulator ≠ hardware, projection ≈ approximate, CVaR = lowest-cost tail.

## Where things live
- Engine: `src/rift/` (`engine.py` orchestration, `scenarios.py`, `counterfactual.py`, `adversarial.py`, `robust*.py`, `optimizer.py`, `qaoa.py`, `cvar.py`, `multivariable.py`, `verifier.py`, `benchmark.py`, `causal.py`, `futures.py`, `uncertainty.py`)
- Product boundaries: `experiments.py` (specs/fingerprints), `limits.py` (bounds), `auth.py` (token gate + ownership), `auth_jwt.py` (verified JWT identity), `ratelimit.py` (in-process budgets), `settings.py` (server env), `supabase_store.py`/`persistence.py` (DB), `billing.py` (Lemon Squeezy), `observability.py` (request IDs/logs), `api.py` (HTTP), `cli.py`, `qpu.py` (gated hardware stub)
- Migrations (source of truth): `backend/supabase/migrations/` 001→005
- Frontend: `web/` (lab + status/history/settings/save-execute panels)
- Tests: `tests/` (unit + API boundary + auth + billing lifecycle + hardening + execute-flow/runner/schema)
- CI scripts: `scripts/` (migrations, secrets, versions)
- Docs: `docs/` (setup, api, experiments, billing, security, deployment, review, release-checklist) + `README.md`, `CHANGELOG.md`

## Commands
`pip install -e ".[dev]"` · `pytest` · `python scripts/validate_migrations.py` · `python scripts/secret_scan.py` · `python scripts/check_versions.py` · `python -m rift.cli demo|serve`

## Rules
- Preserve working behavior; smallest sound fix + regression test.
- Validate inputs via `limits.py`/`experiments.py`; never silently truncate science.
- Secrets server-side only; no traceback/secret leakage in responses.
- Migrations additive + idempotent + RLS-safe.
- Never claim hardware speedup, live billing, reviews, or deployments without evidence.
