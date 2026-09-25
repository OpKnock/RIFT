# Threat Model (Phase 19 substrate)

Scope: the RIFT decision-support API + twin pipeline as code. Out of scope:
attacker capabilities against operated infrastructure (needs deployment).

## Assets

1. Prediction integrity (most critical: a wrong or forged risk display can mislead care).
2. Evidence-bundle authenticity.
3. Ledger append-only history (prospective, reviews).
4. Credentials (Supabase service key, billing secrets, JWT secret, QPU token).
5. Patient data confidentiality (when connected to real sources).

## Attackers and abuse cases

| # | Threat | Control in code | Residual |
|---|---|---|---|
| T-01 | Forged prediction display | Guardian WITHHOLD on bounds/schema/model-identity; deterministic prediction IDs | No signature on `/twin/demo` responses — add before clinical use |
| T-02 | Tampered evidence bundle | HMAC-signed bundles, explicit unsigned marking | Key management is operator duty |
| T-03 | Rewritten audit history | Hash-chained ledgers + JSONL fsync append | Single-file store: needs offline backup + rotation (see runbook) |
| T-04 | Replay of billing webhooks | DB-unique idempotency keys, `_seen` vs `_remember` split | — |
| T-05 | SSRF via fetch URLs | Scheme/IP allowlist, no redirects, DNS timeout | Dev-only private override must stay dev-only |
| T-06 | Auth bypass / user spoofing | Fail-closed 401s, 403 on mismatch, spoof-proof JWT check | MFA/rotation are operator duties |
| T-07 | PII exfiltration via logs | Request IDs, no payload logging in `_finish` path | Log-pipeline redaction is operator duty |
| T-08 | Dependency compromise | `constraints.txt` pins, SAST in CI | No lockfile hash/SBOM yet — add before clinical use |
| T-09 | QPU token theft | Env-only, never logged, never committed | Rotation is operator duty |
| T-10 | Model substitution | Weights digest pin + G-015 identity check | Registry DB needs RLS + backup |

## Explicitly not covered (external)

Penetration test, MFA, secret rotation schedule, immutable log shipping,
backup/DR drills, incident response drills. See `docs/incident-runbook.md`.
