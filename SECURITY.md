# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.0   | :white_check_mark: |
| < 1.0.0 | :x:                |

Only the current `main` release is supported. RIFT is a research prototype — see the safety boundary in `README.md` before deploying it anywhere that matters.

## Reporting a vulnerability

**Do not open a public issue for security reports.** Use GitHub's private vulnerability reporting: go to the repository's **Security** tab → **Report a vulnerability**. Reports stay private until a fix is ready.

Please include:

- Affected version/commit and component (e.g. `src/rift/api.py` webhook handler)
- Steps to reproduce (request/response pair, no real credentials)
- Impact assessment: what an attacker gains (data read, auth bypass, billing fraud, DoS)
- Whether the issue touches the trust boundary: auth, billing webhooks, FHIR fetching, Supabase RLS, or Guardian enforcement

## Response process

1. Confirm receipt and reproduce against `main`.
2. Fix on a private branch with a regression test that proves the failure mode.
3. Land the fix, then disclose via a GitHub Security Advisory if user action is needed.

This is a solo-maintained research project: expect best-effort timelines, not an SLA.

## Scope

In scope: the HTTP API and auth boundary (`src/rift/api.py`, `auth.py`, `auth_jwt.py`), billing webhook verification and idempotency, FHIR/SSRF fetch hardening, Supabase RLS migrations, Guardian enforcement bypasses, dependency vulnerabilities in `constraints.txt`.

Out of scope: the synthetic demo model itself (it is intentionally unvalidated — see `docs/evidence-sheet.md`), social engineering, physical security, and vulnerabilities in third-party services (Supabase, Lemon Squeezy, PhysioNet).

## Audited posture (v1.0.0)

- 223 tests, Bandit 0 findings, Semgrep 0 findings, secret scan clean.
- Bearer/JWT auth with fail-closed 401s; per-row ownership checks; HMAC webhook verification with durable idempotency; HTTPS-only FHIR fetching with host allowlist and private-IP refusal.
- Full audit record: `docs/security.md`. Known open gates (live infra, clinical validation) are listed in `docs/release-checklist.md`, not hidden.
