# API Guide

Practical usage for the RIFT HTTP API. Full contract: `docs/api.md`. Base URL in all examples is `http://127.0.0.1:8080` (see `rift serve --host/--port`).

Every response carries `X-Request-ID`. Errors look like `{"error": "<code>"}` — never a traceback. Include that request ID if you report a problem.

## Start the server

```bash
pip install -e ".[dev]" -c constraints.txt
rift serve                       # http://127.0.0.1:8080
```

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

## Prospective predictions (public demo shape)

```bash
# Lock a prediction
curl -X POST http://127.0.0.1:8080/api/twin/prospective \
  -H 'Content-Type: application/json' \
  -d '{"action":"lock"}'
# → {"lock_id": "...", ...} — immutable once issued

# Reconcile when the outcome arrives
curl -X POST http://127.0.0.1:8080/api/twin/prospective \
  -H 'Content-Type: application/json' \
  -d '{"action":"reconcile","lock_id":"<id>","realized_event":true}'
```

Note: the ledger is currently in-memory, so locks do not survive restarts — fine for the demo, not for a real study.

## Clinician reviews (audited judgments)

```bash
# Record a review (OVERRIDE and REJECT require a rationale)
curl -X POST http://127.0.0.1:8080/api/twin/reviews \
  -H 'Content-Type: application/json' \
  -d '{"action":"ACCEPT","evidence_id":"ev-1","reviewer_id":"dr-a"}'
# → 201 {"review_id": "...", "action": "ACCEPT", ...} — append-only

# Supersede a prior judgment (history preserved, never edited)
curl -X POST http://127.0.0.1:8080/api/twin/reviews \
  -H 'Content-Type: application/json' \
  -d '{"action":"OVERRIDE","evidence_id":"ev-1","reviewer_id":"dr-b",
       "rationale":"bedside exam overrides","supersedes":"<review_id>"}'

# List + counts
curl http://127.0.0.1:8080/api/twin/reviews
```

Actions: `ACCEPT`, `REJECT`, `OVERRIDE`, `REQUEST_REVIEW`. Unknown actions,
missing reviewer/evidence, and rationale-free overrides are rejected (400).
Same in-memory caveat as prospective: durable persistence required before
clinical use.

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

## Status codes

`200` ok · `201` created · `204` options · `400` validation · `401` auth · `403` forbidden · `404` unknown · `405` wrong method · `413` too large · `422` bad scenario · `500` internal (with `request_id`) · `502` dependency · `503` not configured.

Rate limiting (when `RIFT_RATE_LIMIT_ENABLED=true`): `429 {"error": "rate_limited", "retry_after_s": N}` plus `Retry-After` header; `.../execute` has its own lower budget.
