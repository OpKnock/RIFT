# RIFT security audit (v0.6.0, this commit)

## Authentication modes (server decides identity, never the browser)
- **JWT mode** (`RIFT_SUPABASE_JWT_SECRET` set): `Authorization: Bearer <Supabase JWT>` is HS256-verified (signature, exp/nbf with leeway, optional aud/iss); `alg=none` and foreign algorithms rejected; identity is the token `sub` and caller-supplied `user_id` is ignored entirely. This is the production mode.
- **Service-token mode** (`RIFT_API_TOKEN` set): shared bearer credential for single-tenant/proxy deployments; per-row ownership still enforced.
- **Open dev mode** (neither set): `user_id` is caller-asserted — local development only.

## Rate limiting
- In-process fixed-window limiter (`src/rift/ratelimit.py`), enabled with `RIFT_RATE_LIMIT_ENABLED=true`; separate lower budget for the expensive `.../execute` endpoint; `429 + Retry-After` on excess. Defense-in-depth behind edge rules (see `docs/deployment.md`); static assets uncounted; client IP from direct peer unless `RIFT_TRUST_PROXY=true`.

## Checked and passing (evidence in repo/tests)
- Webhook HMAC verification fail-closed; forged signatures get 401 (`tests/test_api_boundaries.py`, `tests/test_api_hardening.py`).
- Webhook replay returns `duplicate: true` via in-memory + DB idempotency keys.
- Upstream errors return generic 502 + request ID; no tracebacks (`test_upstream_errors_do_not_leak`).
- Oversized payloads get 413; malformed JSON gets 400; invalid UUIDs get 400.
- Cross-user reads/writes denied via `owner_mismatch` (403) when stored `user_id` differs.
- Optional `RIFT_API_TOKEN` bearer gate (401 when mismatched).
- Security headers on all responses; CSP on the served page; no ACAO wildcard.
- Secret scan in CI (`scripts/secret_scan.py`); migration safety gate (`scripts/validate_migrations.py`).
- Frontend renders only via `escapeHtml`; no embedded keys in `web/`.

## Residual risks (do not ignore in production)
1. **Multi-tenancy without an IdP.** `user_id` is caller-asserted. Deploy behind Supabase Auth (verify JWTs server-side) before treating rows as private. RLS is a second layer, not the only layer — and service-role keys bypass RLS by design. Setting `RIFT_SUPABASE_JWT_SECRET` switches the server to verified-identity mode; until then, `RIFT_REQUIRE_USER_ID` + ownership checks are assertion-based only.
2. **Service-role key handling.** The server supports service-role keys for writes; anyone holding the key bypasses RLS. Store it in a vault, rotate regularly, never log it (logs redact key-like fields).
3. **Single-token auth is coarse.** `RIFT_API_TOKEN` is one shared service credential, not per-user auth. Use it for a single-tenant deployment or a fronting proxy, not as user login.
4. **No rate limiting in-process.** Add edge rate limits (reverse proxy / gateway) for `/api/demo` and webhook endpoints; the simulator is CPU-bound per request.
   Update: in-process limiting now ships (`RIFT_RATE_LIMIT_ENABLED=true`, stricter `.../execute` budget, `429 + Retry-After`) but remains defense-in-depth — keep edge rules as the primary control, and exclude `/api/billing/webhook` from aggressive edge limits so Lemon Squeezy retries are not throttled into failure.
5. **TLS/CORS at the edge.** The stdlib server serves plain HTTP for local dev. Terminate TLS and set explicit CORS/rate-limit policy at the deployment edge (see `docs/deployment.md`).
6. **Dependency surface.** Runtime stays stdlib-only, but `supabase`/`qiskit` extras pull third-party code when installed. Pin and audit those in production images.
