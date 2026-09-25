# Database

RIFT persists to an optional Postgres-compatible backend. The engine runs fully offline without one; unconfigured servers answer `503 persistence_not_configured` on persistence endpoints. No live project is evidenced in this repo.

## Migrations (source of truth)

`backend/supabase/migrations/`, applied in order `001→007`:

| Migration | Contents |
|---|---|
| `001_initial.sql` | `experiments`, `experiment_runs` tables + RLS + per-user policies |
| `002_production_hardening.sql` | Explicit grants, metadata columns, indexes |
| `003_billing.sql` | `billing_customers`, `billing_subscriptions`, `billing_events` (service-role only; anon/authenticated revoked) |
| `004_experiment_model.sql` | Experiment lifecycle columns, `provider_event_id` + `idempotency_key` on `billing_events`, guarded `UNIQUE(idempotency_key)` constraint, status check constraint, `updated_at` triggers |
| `005_runs_owner.sql` | `user_id` owner column on `experiment_runs` + index |
| `006_model_registry.sql` | `model_registry`, `prediction_audit` (unique `prediction_id`) + RLS |
| `007_observations.sql` | `observations`, `observation_revisions` + RLS |

Rules (enforced by `scripts/validate_migrations.py` in CI):

- **Additive + idempotent only**: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, constraint adds guarded by `pg_constraint` checks. Migrations must be safely re-runnable.
- **RLS on every table**, least-privilege grants, `updated_at` triggers where rows mutate.

Apply with `supabase db push` or the SQL editor, in order. Full steps: `docs/supabase-setup.md`.

## Data model & ownership

- Rows carry `user_id` (nullable for legacy ownerless rows). Reads enforce `owner_mismatch` fail-closed: a caller with no identity never sees owned rows; cross-user reads return 403.
- Webhook idempotency is a **database** guarantee (`UNIQUE(idempotency_key)`), not just the in-process key cache — concurrent duplicate deliveries resolve to duplicate-acks.
- `experiment_runs` listing is capped (`LIST_RUNS_LIMIT = 200`); keyset pagination is future work, not silent unlimited output.

## Store layer

`src/rift/supabase_store.py` is the only server-side DB client. All credentials stay server-side (`settings.py`); the browser never sees keys. Every store failure surfaces as `502 persistence_error` with a `request_id` — except billing webhooks, which return 502 deliberately so the provider retries (see `API-Guide.md`).
