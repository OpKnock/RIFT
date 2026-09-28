# API Guide

Practical usage for the RIFT HTTP API. Full contract: `docs/api.md`. Base URL in all examples is `http://127.0.0.1:8080` (see `rift serve --host/--port`).

Every response carries `X-Request-ID`. Errors look like `{"error": "<code>"}` — never a traceback. Include that request ID if you report a problem.

## Start the server

```bash
pip install -e ".[dev]" -c constraints.txt
rift serve                       # http://127.0.0.1:8080
```

## Production UI entry (`/app`)

The React bundle is served by the API under `/app` (vite base + router
basename); `/` 302-redirects to `/app/`, so ingress `/` and `/app` resolve
to one canonical UI. Deep links (`/app/runs/…`) serve `index.html` via SPA
fallback. Dev server: `http://localhost:5173/app/`.

## Health & discovery (always open)

```bash
curl http://127.0.0.1:8080/api/health
# {"status":"ok","engine":"rift","version":"1.0.0",...}

curl http://127.0.0.1:8080/api/meta
# capabilities, optimizers, backends, limits, auth mode
```

## Authentication

Three modes, decided by server env (never by the client):

| Mode | Server config | Client behavior |
|---|---|---|
| Open dev | nothing set | no header; `user_id` is caller-asserted |
| Service token | `RIFT_API_TOKEN` set | `Authorization: Bearer <token>` on gated endpoints |
| Verified JWT | `RIFT_SUPABASE_JWT_SECRET` set | `Authorization: Bearer <Supabase JWT>`; identity is the token `sub`, supplied `user_id` ignored |

```bash
TOKEN=tok-123
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/experiments/...
```

Missing/forged/expired credentials → `401`. Owned rows read by someone else → `403`.

## Twin demo (public)

```bash
# Snapshot for replay day 10 (valid range 0–13, else 422)
curl "http://127.0.0.1:8080/api/twin/demo?t=10"

# Frozen synthetic evidence bundle
curl http://127.0.0.1:8080/api/twin/evidence
```

The snapshot contains state, baseline, deviations, risk + uncertainty, FORESIGHT trajectories, robustness, Guardian verdict, reasons, and a deterministic prediction ID.

## Prospective predictions (gated when auth is set)

```bash
# Lock a prediction
curl -X POST http://127.0.0.1:8080/api/twin/prospective \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"lock"}'
# → {"lock_id": "...", ...} — immutable once issued

# Reconcile when the outcome arrives
curl -X POST http://127.0.0.1:8080/api/twin/prospective \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"reconcile","lock_id":"<id>","realized_event":true}'
```

Reads and writes are both gated (GET and POST require identity when auth
is configured). Locks survive restarts — see Durable ledgers below.

## Clinician reviews (audited judgments, gated when auth is set)

```bash
# Record a review (OVERRIDE and REJECT require a rationale).
# reviewer_id must equal the authenticated principal (user_id in
# service-token mode, token sub in JWT mode) — mismatches get 400
# identity_mismatch. Unattributed reviews are rejected when auth is on.
curl -X POST http://127.0.0.1:8080/api/twin/reviews \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"ACCEPT","evidence_id":"ev-1","reviewer_id":"dr-a","user_id":"dr-a"}'
# → 201 {"review_id": "...", "action": "ACCEPT", "identity_verified": true, ...} — append-only

# Supersede a prior judgment (history preserved, never edited)
curl -X POST http://127.0.0.1:8080/api/twin/reviews \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"OVERRIDE","evidence_id":"ev-1","reviewer_id":"dr-b","user_id":"dr-b",
       "rationale":"bedside exam overrides","supersedes":"<review_id>"}'

# List + counts (gated)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/twin/reviews
```

Actions: `ACCEPT`, `REJECT`, `OVERRIDE`, `REQUEST_REVIEW`. Unknown actions,
missing reviewer/evidence, and rationale-free overrides are rejected (400).

## Durable ledgers (crash-safe by default)

Both ledgers fsync every append and replay on boot. Default location is
`RIFT_DATA_DIR`/`./data` (`reviews.jsonl`, `prospective.jsonl`); override
with explicit paths, or set the variable to empty string to force pure
in-memory mode (tests only — audit data is lost on restart):

```bash
export RIFT_PROSPECTIVE_LEDGER=/var/lib/rift/prospective.jsonl
export RIFT_REVIEWS_LEDGER=/var/lib/rift/reviews.jsonl
export RIFT_DATA_DIR=/var/lib/rift
```

Back up JSONL files by copying them; restore by placing the copy at the
configured path. One API process per ledger file — concurrent
multi-process writers are not supported. Ledger files are runtime state
(`data/*.jsonl` is gitignored) and are never committed.

## Quantum backends

- `qaoa-statevector-simulator`: default, stdlib-only.
- `qaoa-aer-simulator`: real Qiskit SDK execution (`pip install -e ".[qiskit]"`).
- IBM hardware: `solve_on_ibm(qubo, backend_name)` with `RIFT_QPU_TOKEN` set —
  see `docs/external-gates.md` §1 for the free-tier setup. No token, no run:
  the error tells you exactly what to do.

## Experiments & runs (gated when auth is set; needs database)

```bash
# Save a spec (validated; 201 with stored row, 400 on bad spec, 503 offline)
curl -X POST http://127.0.0.1:8080/api/experiments \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"smoke","scenario":{"crowd":10}}'

# Read (ownership-checked), list runs (capped at 200), execute server-side
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/experiments/<uuid>?user_id=u1
curl http://127.0.0.1:8080/api/experiments/<uuid>/runs
curl -X POST http://127.0.0.1:8080/api/experiments/<uuid>/execute \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl http://127.0.0.1:8080/api/runs/<uuid>
```

With `RIFT_REQUIRE_USER_ID=true`, persistence POSTs require an asserted `user_id` (`400 missing_user_id` otherwise).

## Billing webhooks (gated by HMAC, not by token)

```bash
# X-Signature = HMAC-SHA256(raw body, RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET)
```

Behavior: 503 without a webhook secret; 401 on bad signature; duplicates acknowledged with `{received: true, duplicate: true}`; persistence failures answer 502 so the provider retries (never a silent drop).

## Ops (gated when auth is set)

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/ops/monitor
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/metrics
```

`/metrics` is Prometheus exposition over the in-process collector (request/latency/failure counters, Guardian action rates, prediction distribution). In open dev mode no header is needed.

## Real-time event stream (SSE, gated when auth is set)

```bash
# Long-lived stream of incident/decision lifecycle events.
# ?topics= subset of: twin.updates, guardian.verdicts, alerts.firing,
# incidents.lifecycle, decisions.lifecycle, metrics.snapshot,
# sources.heartbeat (default: all). Occupies one server thread per
# client until disconnect — local/dev fan-out scale.
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/events/stream?topics=incidents.lifecycle,decisions.lifecycle"
```

No WebSocket upgrade exists on the stdlib server; SSE over plain HTTP is
the real-time transport (see `src/rift/realtime.py`).

## Experiment platform (templates, versions, compare, import, replay, scheduler)

All gated when auth is set; experiment/run creation additionally needs
the database (503 otherwise). Supabase writes are mirrored into the
local archive, so compare/export/replay see a unified view. Ownership is
enforced on both stores (403 on mismatch); a Supabase outage is 502, never
a silent mirror read. When Supabase is configured it is authoritative for
reads: export/replay/compare resolve there first (miss is 404, outage is
502) and never fall back to the archive, so deleted rows cannot resurrect
from a stale mirror; compare answers 404 `candidate_not_found` (with ids)
rather than silently comparing fewer candidates than requested.
Versions/import responses carry `"durable": true`
when the write reached Supabase (migration `008` adds the `versions`
column); archive-only writes report `"durable": false`. Templates are
visible when public, system/legacy, or owned by the caller.

```bash
# Templates (spec validated; created_by = authenticated caller)
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"night-shift","spec":{"name":"ns","optimizer":"exact"}}' \
  http://127.0.0.1:8080/api/experiments/templates
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/experiments/templates

# Versions (standalone records; validated specs only)
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"spec":{"name":"v2","optimizer":"exact"},"description":"try cvar"}' \
  http://127.0.0.1:8080/api/experiments/<id>/versions

# Compare (ownership-enforced run resolution: Supabase first, archive mirror second)
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"optimizer","baseline_id":"<run>","candidate_ids":["<run>"]}' \
  http://127.0.0.1:8080/api/experiments/compare

# Export / import (validated on import; runs get fresh ids)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/experiments/<id>/export

# Replay (deterministic server-side re-execution via run_spec)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/experiments/<id>/replay

# Scheduler (local in-process queue; jobs do not survive restarts)
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"experiment_id":"<id>","spec":{"name":"nightly","optimizer":"exact"}}' \
  http://127.0.0.1:8080/api/experiments/scheduler/jobs
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/experiments/scheduler/jobs
```

## Operations: incidents & decisions (gated; actor = authenticated caller)

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"manual","severity":"high","title":"...","description":"...","user_id":"op-1"}' \
  http://127.0.0.1:8080/api/operations/incidents
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"acknowledge","note":"...","user_id":"op-1"}' \
  http://127.0.0.1:8080/api/operations/incidents/<id>/action
```

Incident lifecycle: `open → acknowledged → investigating → resolved → closed`.
Decision lifecycle: `pending → approved/rejected → overridden → executed`
(or `under_review`, `expired`). Every transition is timestamped in the
object timeline and published on the event stream.

## Intelligence: grounded NL helpers (gated; mock provider by default)

```bash
# Which provider is active (mock unless OPENAI_API_KEY is set)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/intelligence/status

# Natural language -> validated ExperimentSpec (invalid proposals get 422, never execute)
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"description":"stress the night shift with a smoke surge"}' \
  http://127.0.0.1:8080/api/intelligence/scenario

# Grounded explanation of a deterministic twin snapshot (LLM narrates, engine decides)
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"day":13}' http://127.0.0.1:8080/api/intelligence/explain
```

## Authentication matrix (authoritative)

See `docs/security.md` § "Endpoint authentication matrix" — the single
source of truth for which endpoints are open, gated, ownership-enforced,
or HMAC-signed.

## Status codes

`200` ok · `201` created · `204` options · `400` validation · `401` auth · `403` forbidden · `404` unknown · `405` wrong method · `413` too large · `422` bad scenario · `500` internal (with `request_id`) · `502` dependency · `503` not configured.

Rate limiting (when `RIFT_RATE_LIMIT_ENABLED=true`): `429 {"error": "rate_limited", "retry_after_s": N}` plus `Retry-After` header; `.../execute` has its own lower budget.
