# RIFT Product Brief (Phase 1 foundation)

## Core problem

Teams adopt interventions (evacuation plans, clinical protocols, capacity policies) without seeing how those
decisions behave under plausible disturbances. RIFT exists to test a decision *before* it is trusted:
enumerate counterfactual futures, attack them with declared perturbations, optimize for robustness rather
than nominal performance, and verify the result through an independent gate that the optimizer cannot bypass.

## Primary users

1. **Operator / researcher** — defines scenarios, runs simulations, reads Guardian verdicts, records audited
   decisions. Primary user of this UI.
2. **Reviewer / auditor** — inspects evidence bundles, review ledger, fingerprints, and run history after the fact.
3. **Platform operator** — configures persistence, billing, auth, and backup; owns RTO/RPO, rotation, and deployment.

RIFT is a research prototype: decision support only, human-in-the-loop required, no clinical use.

## Layer separation

| Layer | Lives in | Role |
|---|---|---|
| Core engine (domain-neutral) | `src/rift/` (`engine.py`, `optimizer.py`, `qaoa.py`, `robust*.py`, `verifier.py`) | Deterministic computation; no HTTP, no database |
| Domain models | `src/rift/scenarios.py`, `src/rift/health/` | Scenario definitions, transitions, bounds; the engine stays generic |
| Platform services | `src/rift/api.py`, `supabase_store.py`, `billing.py`, `monitoring` | HTTP, persistence, billing boundary, telemetry |
| Presentation | `frontend/` | Consumes the REST contract only; never reimplements engine math |

The frontend must never duplicate engine logic. Anything it displays comes from a live response or is
explicitly labeled local/demo.

## Extension points (inventory, not promises)

- **Domains**: add a driver under `frontend/src/domains/` implementing `DomainDriver`, and — separately —
  a backend scenario plus transition model. One side without the other is not a domain.
- **Optimizers**: `SUPPORTED_OPTIMIZERS` in `src/rift/experiments.py`; UI reads them from `GET /api/meta`, never hardcodes.
- **Data adapters**: `src/rift/health/adapters.py` + provenance envelope; UI surfaces dataset/safety strings verbatim.
- **Calibration methods**: `src/rift/health/evaluate.py`; UI renders whichever methods the bundle reports.

## Environments

- **Local dev**: stdlib HTTP server + file/JSONL ledgers or in-memory demo mode; Supabase unconfigured (503 on persistence paths).
- **Staging/production**: Supabase project, service-token/JWT auth, ledger files with backup, edge TLS — operator-owned, evidenced before any claim.

## Versioning

Engine version (`ENGINE_VERSION`, currently 1.0.0), contract version (`frontend/src/contracts/v1.ts`,
`CONTRACT_VERSION = 'v1'`), experiment fingerprints (SHA-256 over canonical spec JSON). The UI warns when
the live engine version differs from its expected version.
