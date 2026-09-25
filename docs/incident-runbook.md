# Incident Runbook + Backup (Phase 19/20 substrate)

Template for operators. Undrilled until a team exists — an undrilled
runbook is a draft, labeled as such.

## Severity levels

- SEV-1: wrong prediction displayed or suspected tampering → freeze display (Guardian WITHHOLD-all via config), preserve ledgers, page on-call.
- SEV-2: outage or 5xx above SLO → fail over per `service_levels.RTO_SECONDS` target (300 s), serve cached WITHHOLD state, never serve stale predictions as fresh.
- SEV-3: degraded dependency (Supabase, billing, QPU) → degraded mode, 502s with request IDs, no silent retries that double-charge.

## First 15 minutes

1. Confirm scope from `/metrics` + `/api/ops/monitor` (which routes, since when).
2. Snapshot ledger files (`RIFT_PROSPECTIVE_LEDGER`, `RIFT_REVIEWS_LEDGER`) before any restart — restarts are safe (replay on boot) but copy first.
3. Do NOT delete or edit ledger files; audit history is evidence.
4. Record every action with timestamps in the incident log.

## Backup and restore

- Ledger files: append-only JSONL. Back up by copying the file (safe mid-write: readers see complete lines; fsync guarantees prefix durability). Restore by placing the backup at the configured path and restarting — replay rebuilds state. Verify with `JsonlStore.count()` vs pre-incident stats.
- Supabase: point-in-time recovery per project plan (operator duty) + migration replay via `scripts/validate_migrations.py`.
- RPO target: 60 s (`service_levels.RPO_SECONDS`) — met only when ledgers are file-backed AND backups run at least minutely. In-memory demo mode explicitly does not meet it.

## Post-incident

Blameless writeup: timeline, root cause, which Guardian rule should have caught it (or new rule proposal with owner), CAPA entry per `docs/qms-skeleton.md` §5.
