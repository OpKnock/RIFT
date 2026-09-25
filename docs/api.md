# RIFT API contract (v1.0.0)

Base: `http://127.0.0.1:8080`. All responses include `X-Request-ID`. Errors are
`{"error": "<code>"}` plus optional non-sensitive `detail`. Upstream failures
are generic `502` with a `request_id` for log correlation — no stack traces.

## Authentication
- JWT mode (`RIFT_SUPABASE_JWT_SECRET` set): every gated endpoint requires `Authorization: Bearer <Supabase JWT>`; identity is the verified `sub`, and any caller-supplied `user_id` is ignored. Missing/forged/expired tokens → `401`.
- Service-token mode (`RIFT_API_TOKEN` set): `Authorization: Bearer <token>` required on gated endpoints.
- Open mode (neither set): no gate; `user_id` caller-asserted (dev only).
- The web lab has an access-token field (SETTINGS panel) sent automatically on save/execute.

## Rate limiting
Enabled with `RIFT_RATE_LIMIT_ENABLED=true`: `429 {"error": "rate_limited", "retry_after_s": N}` plus `Retry-After` header. The `.../execute` endpoint has its own lower budget. Static assets are uncounted.

## Public (no token required)
- `GET /api/health` → `{status, engine, version, quantum_backend, persistence, billing}`
- `GET /api/meta` → engine capabilities, optimizers, backends, limits, auth mode
- `GET /api/persistence/status`, `GET /api/billing/status`
- `GET /api/demo?crowd=&smoke=&corridor_capacity=&block_b=` → lab payload (422 on out-of-range input)
- `GET /api/twin/demo?t=` → patient-twin snapshot for replay day 0–13 (422 outside range); public demo endpoint, no auth required
- `POST /api/billing/webhook` → HMAC `X-Signature` required; 503 without webhook secret, 401 bad signature, duplicate replays get `{received: true, duplicate: true}`

## Gated (require `Authorization: Bearer $RIFT_API_TOKEN` when configured)
- `POST /api/experiments` — body validated by `rift.experiments.validate_spec_payload`; 201 with stored row, 400 validation, 503 offline
- `GET /api/experiments/{uuid}` — optional `?user_id=` ownership check (403 on mismatch)
- `POST /api/experiments/{uuid}/runs` (alias `.../run`) — body validated by `validate_run_payload`
- `POST /api/experiments/{uuid}/execute` — server-side run: loads the stored spec, executes `rift.runner.run_spec`, writes a run row with metrics + fingerprint, marks the experiment `succeeded`/`failed`; 422 on invalid stored specs, 503 offline
- `GET /api/experiments/{uuid}/runs`, `GET /api/runs/{uuid}`
- `POST /api/billing/checkout` — `{variant_id, email?, user_id?, metadata?}` → 201 `{checkout_url, checkout_id}`, 400/503/502
- `GET /api/billing/entitlement?user_id=` → `{entitled, status}` derived from server-side subscription mirror

Missing rows read as `404 not_found`; engine execution failures surface as
`500 execution_error` (experiment marked `failed`), distinct from `502`
dependency outages. `variant_id` must be a string (integers coerced).

When `RIFT_REQUIRE_USER_ID=true`, persistence POSTs require an asserted `user_id` (400 `missing_user_id`); reads scope by `?user_id=` with 403 on owner mismatch.

## Limits
`GET /api/meta` → `limits` (policy vars, perturbations, payload bytes, scenario bounds). Exceeding returns 400/413 with a clear message — never silent truncation.

## Status codes
200 ok · 201 created · 204 options · 400 validation · 401 auth · 403 forbidden · 404 unknown · 405 wrong method · 413 too large · 422 bad scenario · 500 internal (with request_id) · 502 dependency · 503 not configured
