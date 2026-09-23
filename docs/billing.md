# Billing (Lemon Squeezy boundary)

Billing is **outside the simulation core**. The engine, optimizer, and
Guardian run identically with billing disabled, which is the default: no
credentials, store IDs, variant IDs, or products are hard-coded anywhere in
this repository.

## What is implemented

- `src/rift/billing.py` — `LemonSqueezyProvider` boundary:
  - reads server-side env only (see below),
  - builds Lemon Squeezy v1 `POST /checkouts` JSON:API payloads,
  - verifies webhook `X-Signature` (HMAC-SHA256 hex of raw body),
  - validates `meta.event_name` shape without crashing on new event types,
  - derives idempotency keys (`event_name:provider_event_id`),
  - maps subscription events to mirror updates and server-side entitlements
    (`active`/`trialing`/`past_due` entitled; everything else fail-closed).
- HTTP endpoints in `src/rift/api.py` (stdlib only):
  - `GET /api/billing/status` → `{configured, provider, ...}` (no secrets),
  - `POST /api/billing/checkout` → live Lemon Squeezy checkout creation,
    or `503 billing_not_configured` when env is absent,
    or `400 variant_id is required` when no variant is supplied,
  - `POST /api/billing/webhook` → fail-closed HMAC verification, `401` on
    bad signature, `503 billing_webhook_not_configured` when the webhook
    secret is absent, duplicate replays get `{received: true, duplicate: true}`,
    subscription events upsert `billing_subscriptions` best-effort,
  - `GET /api/billing/entitlement?user_id=` → `{entitled, status}` derived
    only from the server-side subscription mirror, never browser input.
- `backend/supabase/migrations/003_billing.sql` — service-role-only
  `billing_customers`, `billing_subscriptions`, `billing_events` tables;
  `004` adds the webhook idempotency unique constraint.
- Tests cover signature verification, lifecycle mapping, entitlement rules,
  idempotent replay, and the not-configured paths with zero network access
  (`tests/test_billing.py`, `tests/test_billing_lifecycle.py`).

## Configuration (server only, all optional)

```bash
RIFT_LEMON_SQUEEZY_API_KEY=
RIFT_LEMON_SQUEEZY_STORE_ID=
RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET=
RIFT_LEMON_SQUEEZY_VARIANT_ID=   # optional default variant
```

`LEMON_SQUEEZY_*` names (without `RIFT_`) are accepted as fallbacks.
Leave all values empty to keep billing disabled.

## Connecting a real account (manual, in the Lemon Squeezy dashboard)

No account tooling or credentials are available from this environment, so
these steps are intentionally manual and no live checkout has been executed:

1. Create a store + product + variant in Lemon Squeezy; note the numeric
   store ID and variant ID.
2. Create an API key (**Settings → API**) and export it as
   `RIFT_LEMON_SQUEEZY_API_KEY` on the server only.
3. Create a webhook endpoint pointing at
   `https://<your-host>/api/billing/webhook`, copy the signing secret into
   `RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET`.
4. Smoke-test:
   ```bash
   curl http://127.0.0.1:8080/api/billing/status
   curl -X POST http://127.0.0.1:8080/api/billing/checkout \
     -H 'Content-Type: application/json' \
     -d '{"variant_id":"<VARIANT_ID>","email":"buyer@example.com"}'
   ```
   Expect a `checkout_url` on success, `503` when unconfigured.
5. Send a test webhook from the Lemon Squeezy dashboard; expect
   `{"received": true, ...}` and a row in `billing_events` (if Supabase is
   configured).

## Blocked by external access (explicitly not done)

- No Lemon Squeezy account, API key, store, variant, or product was
  available in this environment, so no live checkout, webhook delivery, or
  sandbox transaction was executed or claimed.
- No credentials or product IDs were invented to fill the gap; placeholders
  remain empty until a real account is connected.
