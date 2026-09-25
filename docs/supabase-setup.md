# Supabase setup (server-side, local-first)

RIFT runs fully offline. Supabase is an **optional** persistence layer for
experiments and runs. Nothing requires a live project to run `pytest`,
`rift demo`, or `rift serve`.

## 1. Create the project

1. Create a project at https://supabase.com/dashboard.
2. Open **Project Settings → API** and copy the project URL plus a key:
   - Local/dev or browser-adjacent server use: publishable/anon key.
   - Trusted server only: service-role key (never expose to the browser).
3. Open **SQL Editor** and apply migrations in order:
   - `backend/supabase/migrations/001_initial.sql`
   - `backend/supabase/migrations/002_production_hardening.sql`
   - `backend/supabase/migrations/003_billing.sql`
   - `backend/supabase/migrations/004_experiment_model.sql`
   - `backend/supabase/migrations/005_runs_owner.sql`
   - `backend/supabase/migrations/006_model_registry.sql`

   With the Supabase CLI:

   ```bash
   supabase link --project-ref <PROJECT_REF>
   supabase db push
   ```

   Or paste each file into the dashboard SQL editor and run it.

## 2. Configure the server (never the browser bundle)

```bash
RIFT_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
RIFT_SUPABASE_KEY=<service-role-or-publishable-key>
```

Legacy fallbacks still work (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_ANON_KEY`), with `RIFT_`-prefixed
values taking precedence. `.env.example` documents the canonical names.

Security rules:

- Service-role keys stay on the server. The `web/` bundle must never embed
  any Supabase key.
- `001` enables Row Level Security with per-user policies; `002` revokes
  direct `anon`/`authenticated` table grants down to the intended set and
  adds experiment metadata/run timing columns.
- `003` billing tables grant nothing to `anon`/`authenticated` — they are
  service-role-only and read through server endpoints.
- `004` adds the experiment lifecycle (status, reproducibility, fingerprints,
  `updated_at` triggers, webhook idempotency); `005` adds run ownership;
  `006` adds the model registry + prediction-audit tables (service-role only).
  All migrations are additive and idempotent (`IF NOT EXISTS`).

## 3. Verify

```bash
pip install -e ".[supabase]" -c constraints.txt
python -c "from rift.supabase_store import SupabaseStore; print(SupabaseStore().configured)"
rift serve
curl http://127.0.0.1:8080/api/health
curl http://127.0.0.1:8080/api/persistence/status
```

`persistence.configured: false` with no env vars is the expected offline
state, not an error.

## 4. Persistence endpoints (require configuration)

| Method | Path | Behaviour when unconfigured |
|---|---|---|
| POST | `/api/experiments` | `503 persistence_not_configured` |
| GET | `/api/experiments/{id}` | `503 persistence_not_configured` |
| POST | `/api/experiments/{id}/runs` | `503 persistence_not_configured` |
| POST | `/api/experiments/{id}/execute` | `503 persistence_not_configured` |
| GET | `/api/experiments/{id}/runs` | `503 persistence_not_configured` |
| GET | `/api/runs/{id}` | `503 persistence_not_configured` |

`POST .../execute` runs the stored spec server-side (`rift.runner`), writes
the run row with metrics + fingerprint, and marks the experiment
`succeeded`/`failed` — the reproducible path. Direct `POST .../runs` remains
for externally computed results.

Example (configured server):

```bash
curl -X POST http://127.0.0.1:8080/api/experiments \
  -H 'Content-Type: application/json' \
  -d '{"name":"smoke-test","scenario":{"name":"lab"},"description":"local check"}'
```
