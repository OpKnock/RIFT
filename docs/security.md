# RIFT security audit (v0.6.0, this commit)

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
1. **Multi-tenancy without an IdP.** `user_id` is caller-asserted. Deploy behind Supabase Auth (verify JWTs server-side) before treating rows as private. RLS is a second layer, not the only layer — and service-role keys bypass RLS by design.
2. **Service-role key handling.** The server supports service-role keys for writes; anyone holding the key bypasses RLS. Store it in a vault, rotate regularly, never log it (logs redact key-like fields).
3. **Single-token auth is coarse.** `RIFT_API_TOKEN` is one shared service credential, not per-user auth. Use it for a single-tenant deployment or a fronting proxy, not as user login.
4. **No rate limiting in-process.** Add edge rate limits (reverse proxy / gateway) for `/api/demo` and webhook endpoints; the simulator is CPU-bound per request.
5. **TLS/CORS at the edge.** The stdlib server serves plain HTTP for local dev. Terminate TLS and set explicit CORS/rate-limit policy at the deployment edge (see `docs/deployment.md`).
6. **Dependency surface.** Runtime stays stdlib-only, but `supabase`/`qiskit` extras pull third-party code when installed. Pin and audit those in production images.
