# RIFT API contract (v0.6.0)

Base: `http://127.0.0.1:8080`. All responses include `X-Request-ID`. Errors are
`{"error": "<code>"}` plus optional non-sensitive `detail`. Upstream failures
are generic `502` with a `request_id` for log correlation — no stack traces.

## Public (no token required)
- `GET /api/health` → `{status, engine, version, quantum_backend, persistence, billing}`
- `GET /api/meta` → engine capabilities, optimizers, backends, limits, auth mode
- `GET /api/persistence/status`, `GET /api/billing/status`
- `GET /api/demo?crowd=&smoke=&corridor_capacity=&block_b=` → lab payload (422 on out-of-range input)
- `POST /api/billing/webhook` → HMAC `X-Signature` required; 503 without webhook secret, 401 bad signature, duplicate replays get `{received: true, duplicate: true}`

## Gated (require `Authorization: Bearer $RIFT_API_TOKEN` when configured)
- `POST /api/experiments` — body validated by `rift.experiments.validate_spec_payload`; 201 with stored row, 400 validation, 503 offline
- `GET /api/experiments/{uuid}` — optional `?user_id=` ownership check (403 on mismatch)
- `POST /api/experiments/{uuid}/runs` (alias `.../run`) — body validated by `validate_run_payload`
- `GET /api/experiments/{uuid}/runs`, `GET /api/runs/{uuid}`
- `POST /api/billing/checkout` — `{variant_id, email?, user_id?, metadata?}` → 201 `{checkout_url, checkout_id}`, 400/503/502
- `GET /api/billing/entitlement?user_id=` → `{entitled, status}` derived from server-side subscription mirror

## Limits
`GET /api/meta` → `limits` (policy vars, perturbations, payload bytes, scenario bounds). Exceeding returns 400/413 with a clear message — never silent truncation.

## Status codes
200 ok · 201 created · 204 options · 400 validation · 401 auth · 403 forbidden · 404 unknown · 405 wrong method · 413 too large · 422 bad scenario · 500 internal (with request_id) · 502 dependency · 503 not configured
