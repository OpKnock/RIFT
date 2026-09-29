# RIFT security audit (v1.0.0, this commit)

> **Research prototype, not clinical software.** This document describes code-level controls only; it is not a clinical safety case.

## Authentication modes (server decides identity, never the browser)
- **JWT mode** (`RIFT_SUPABASE_JWT_SECRET` set): `Authorization: Bearer <Supabase JWT>` is HS256-verified (signature, exp/nbf with leeway, optional aud/iss); `alg=none` and foreign algorithms rejected; identity is the token `sub` and caller-supplied `user_id` is ignored entirely. This is the production mode.
- **Service-token mode** (`RIFT_API_TOKEN` set): shared bearer credential for single-tenant/proxy deployments; per-row ownership still enforced. Browsers should exchange the token once via `POST /api/auth/session` for an HttpOnly session cookie (`rift_session`, `SameSite=Lax`, 30-minute sliding expiry, server-side store) instead of keeping the token in localStorage — see `src/rift/sessions.py`. Cookie and bearer satisfy the same gate; `GET /api/auth/session-info` reports which mechanism a request authenticated with.
- **Open dev mode** (neither set): `user_id` is caller-asserted — local development only.

## Rate limiting
- In-process fixed-window limiter (`src/rift/ratelimit.py`), enabled with `RIFT_RATE_LIMIT_ENABLED=true`; separate lower budget for the expensive `.../execute` endpoint; `429 + Retry-After` on excess. Defense-in-depth behind edge rules (see `docs/deployment.md`); static assets uncounted; client IP from direct peer unless `RIFT_TRUST_PROXY=true`.

## Server-side request forgery (FHIR extraction)
- `fhir_clinical.checked_open` gates every fetch hop: http/https schemes only, no redirects, DNS-resolved targets must be globally routable. Loopback/private targets require explicit `RIFT_ALLOW_PRIVATE_FETCH=true` (dev/test only). Tested: metadata-IP, file://, and gopher URLs refused; loopback refused by default and allowed under the flag.

## Checked and passing (evidence in repo/tests)
- Static analysis: `bandit -r src` reports **zero issues** (triaged 2026-09-23: one medium `urlopen` hardened with an endpoint allowlist; low `try/except/pass` sites converted to redacted `log_event` diagnostics except three justified `nosec` best-effort paths; `assert` replaced with an explicit raise). Enforced in CI (`security` job).
- Supply chain: RIFT's runtime dependencies are `[]`; auditing the full declared closure (`pytest`, `supabase`, `qiskit`, `qiskit-ibm-runtime`) with pip-audit found **no known vulnerabilities**. (The host machine's global environment has unrelated CVEs in packages RIFT never imports — not a repo finding.)
- Static analysis: Semgrep (`semgrep --config auto --error src`) reports **zero findings** when run locally/manually; not currently an active CI gate (CI `security` job runs Bandit only). Bandit + test gates provide automated SAST coverage in CI; Semgrep provides supplementary coverage.
- Webhook HMAC verification fail-closed; forged signatures get 401 (`tests/test_api_boundaries.py`, `tests/test_api_hardening.py`).
- Webhook replay returns `duplicate: true` via in-memory + DB idempotency keys.
- Upstream errors return generic 502 + request ID; no tracebacks (`test_upstream_errors_do_not_leak`).
- Oversized payloads get 413; malformed JSON gets 400; invalid UUIDs get 400.
- Cross-user reads/writes denied via `owner_mismatch` (403) when stored `user_id` differs.
- Optional `RIFT_API_TOKEN` bearer gate (401 when mismatched).
- Security headers on all responses; CORS is an explicit origin allow-list (`RIFT_CORS_ORIGINS`, empty by default = same-origin only) — no wildcard; disallowed origins get no ACAO headers. Set it to the origin serving the Stitch UI.
- Secret scan in CI (`scripts/secret_scan.py`); migration safety gate (`scripts/validate_migrations.py`).
- Frontend renders only via `escapeHtml`; no embedded keys in `web/`.

## Endpoint authentication matrix (authoritative; verified against `src/rift/api.py`)

`_identity()` passes silently in open dev mode and enforces 401 whenever
JWT or service-token auth is configured. So "gated" below means *gated in
production, open in local dev*.

**Open in all modes** (no identity; public demo/telemetry surface):
`GET /api/health`, `GET /api/meta`, `GET /api/persistence/status`,
`GET /api/billing/status`, `GET /api/demo`, `GET /api/twin/demo`,
`GET /api/twin/evidence`.

**Gated** (`_identity`, 401 when auth is configured):
`GET /api/ops/monitor`, `GET /api/events/stream`, `GET /metrics`,
`GET /api/billing/entitlement`, `GET /api/twin/prospective`,
`GET /api/twin/reviews`, `GET /api/operations/incidents`,
`GET /api/operations/decisions`, `GET /api/explainability/audit`,
`GET /api/explainability/evidence`, `GET /api/intelligence/status`,
all `GET /api/experiments/*` sub-routes (templates, versions, runs,
snapshots, benchmarks, evidence, export, replay, scheduler) and
`GET /api/experiments/:id`, `GET /api/runs/:id`.

**Gated + ownership-enforced** (403 on `owner_mismatch`):
Supabase experiment/run rows, `POST /api/experiments/compare`
(run resolution), export/replay Supabase fallbacks, `POST` incident/decision
actions (actor = authenticated caller, never a hardcoded service name).

**Listing visibility:** `GET /api/operations/incidents` and
`GET /api/operations/decisions` are workspace-visible by default (so
owner-less triage items stay reachable) with `?owner=<id>` and
`?mine=true` (caller principal) filters available. This matches the
single-tenant assumption in residual risk 3 — do not treat listing
visibility as a multi-tenant boundary.

**Special cases:**
- `POST /api/billing/webhook`: HMAC `X-Signature`, never bearer tokens.
- `POST /api/twin/reviews`: `reviewer_id` must equal the authenticated
  principal (`identity_mismatch` → 400); unattributed reviews are rejected
  whenever auth is configured and otherwise stored with
  `identity_verified: false`.
- `GET /api/events/stream`: long-lived SSE; occupies one server thread per
  client until disconnect (local/dev fan-out scale, not internet scale).

## Tenant boundary model (authoritative)

Ownership is a `user_id` string compared with `owner_mismatch()` (fail
closed: rows carrying an owner are invisible to other callers; ownerless
legacy rows stay readable). The boundary holds across **both** stores:

- Supabase rows carry `user_id` (experiments, runs); every read checks it.
- The in-process archive mirror carries `user_id` too (experiments,
  `ExperimentRun.user_id`, template `created_by` + `is_public`), and every
  archive read enforces the same check — stale/deleted Supabase rows are
  never served cross-tenant via the mirror.
- Supabase outage surfaces as `unavailable` → `502`; handlers never fall
  back to the mirror on outage (compare included). When Supabase is
  configured, a clean miss is final — the archive is a mirror/cache, not
  a second source of truth, so deleted rows cannot resurrect from it.
- Incidents bind `owner` at create; incident/decision mutations require
  owner/proposer match (ownerless legacy objects stay actionable).
- Versions write through to Supabase (`versions` column, migration `008`);
  imports persist authoritatively with ownership re-assigned to the
  importer (package owner claims are never trusted). Both report
  `"durable": true/false` so clients can see what survives restart.

## Residual risks (do not ignore in production)
1. **Multi-tenancy without an IdP.** `user_id` is caller-asserted. Deploy behind Supabase Auth (verify JWTs server-side) before treating rows as private. RLS is a second layer, not the only layer — and service-role keys bypass RLS by design. Setting `RIFT_SUPABASE_JWT_SECRET` switches the server to verified-identity mode; until then, `RIFT_REQUIRE_USER_ID` + ownership checks are assertion-based only.
2. **Service-role key handling.** The server supports service-role keys for writes; anyone holding the key bypasses RLS. Store it in a vault, rotate regularly, never log it (logs redact key-like fields).
3. **Single-token auth is coarse.** `RIFT_API_TOKEN` is one shared service credential, not per-user auth. Use it for a single-tenant deployment or a fronting proxy, not as user login.
4. **In-process rate limiting present** (`RIFT_RATE_LIMIT_ENABLED=true`, separate `.../execute` budget, `429 + Retry-After`); remains defense-in-depth — keep edge rules as the primary control, and exclude `/api/billing/webhook` from aggressive edge limits so Lemon Squeezy retries are not throttled into failure.
5. **TLS/CORS at the edge.** The stdlib server serves plain HTTP for local dev. Terminate TLS and set explicit CORS/rate-limit policy at the deployment edge (see `docs/deployment.md`).
6. **Dependency surface.** Runtime stays stdlib-only, but `supabase`/`qiskit` extras pull third-party code when installed. Pin and audit those in production images.
