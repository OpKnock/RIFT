# Changelog

All notable changes to RIFT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Tensor acceleration (`src/rift/accelerate.py`, `RIFT_ACCELERATOR=off|auto|cpu|cuda`): bitwise-identical torch kernels for exact enumeration and the QAOA statevector path, with CPU fallback and honest `/api/meta` reporting (measured CPU-torch on 12 vars: exact 40→10ms, QAOA 652→461ms; CUDA activates with a CUDA torch build)
- Third domain `powergrid-emergency` (emergency load-shedding: demand/supply/frequency/reserve state, shed+peaker policy, statutory-band guardian rules, template, registry wiring, 7 tests)
- Neural state estimation (`src/rift/neural.py`, numpy-only MLP): deterministic surrogates trained on scenario rollouts with hull-based abstention back to the analytical transition and per-prediction provenance; clinical twin untouched (8 tests)

### Removed
- React UI deleted (`frontend/` removed; Stitch project "RIFT Premium - Counterfactual Decision Intelligence" builds the premium UI from scratch, 9 screens wired to this API). This service is API-only now: `/` returns an index JSON, `/app/*` answers an honest 404. CI `frontend`/`e2e` jobs, Dockerfile frontend stage, compose `rift-frontend` service, and `local` frontend hooks removed. Phase 19 marked PARTIAL pending Stitch export.

### Fixed
- Navigation no longer flashes the fullscreen loading screen: route chunks preload on idle, later transitions show a slim progress bar (branded screen only at boot)
- Settings text overflow fixed (long mono values wrap instead of colliding); save button shows a proper Saved state
- `local start` self-heals stale gated stacks (clears the old dev-default token, regenerates stale compose with backup) and prints the effective auth mode, so 401 walls are never a surprise
- First-run UX: local stack defaults to open dev mode (no mystery token, no 401 walls); 401s now render a professional AuthRequired state with a direct link to token settings
- Settings detects open-dev servers and says so instead of showing a useless token form; session state restores across reloads
- 3D twin performance: no more per-frame React setState across 72 nodes, no unconfigured shadow passes, memoized meshes with stable hover callbacks
- Loading skeletons replace blank-then-error flashes on dashboard/operations pages; stale "no push channel" copy corrected
- EventBus async fan-out no longer throws loop exceptions on full subscriber queues (drop-in-callback + closed-loop guard); regression tests included
- Removed dead WebSocket transport (`WSConnection`, `WebSocketMessage`); SSE is the only supported transport, with a test proving no WS surface remains
- Reconciliation rule failures and optimizer failures are explicit `{status: failed, ...}` / `{triggered: false, ...}` results instead of action-shaped dicts
- Clarified determinism contract: content-derived fingerprints are pure; opaque unique IDs guarantee uniqueness only
- Supabase-authoritative export/replay/compare (miss 404 incl. `candidate_not_found`, outage 502); resolvers no longer resurrect deleted rows from the archive mirror
- Bandit clean: non-security MD5 uses `usedforsecurity=False` (IDs unchanged), narrow justified `nosec` on intentional binds/placeholders/fan-out resilience
- Frontend builds in CI again (`@types/node`); production Dockerfile drops the obsolete `web/` copy; phase-19 evidence points at real `frontend/` files
- Config drift fixed (`.env.example`/README use canonical `RIFT_*` names, SSE endpoint documented); `local` propagates `.env.local` into compose and drops SQLite/required-host-Node assumptions
- Removed 37 unreachable trailing `return False` statements from the split route modules
- Production React routing unified under `/app` (vite base + router basename, base-aware navigation, manifest scope; API `/` 302-redirects to `/app/`)
- Tenant isolation closed on archive-backed reads: mirrors carry `user_id`, `_resolve_experiment`/`_resolve_run` enforce on the archive path, versions/runs/snapshots/evidence/replay/export/templates all gate ownership (403)
- Archive fallback no longer crosses the persistence boundary on outage: compare and resolvers surface `unavailable` → 502 instead of silently serving stale mirrors (also fixes a double-send)
- Incident ownership assigned at create (fixes `?mine=true` for fresh incidents); incident/decision mutations enforce owner/proposer (403)
- Versions are durable: new `versions` column (migration 008) with Supabase write-through, `durable` flag on write, pre-migration DBs stay working with honest `durable: false`
- Import persists authoritatively to Supabase when configured (with ownership re-assignment, `durable` flag, `runs_imported` count); invalid packages are 400, not 500
- Runs list reads the authoritative store with per-row tenant filtering (and archive fallback unconfigured); dead duplicate `/runs` handler removed
- Frontend consumes realtime SSE on the operations page (live badge, polling fallback); session state restores across reloads via `/auth/session-info`
- Removed unused `socket.io-client` dependency (backend exposes SSE, not Socket.IO)
- Export/replay read Supabase first when configured (outage 502, miss 404); the archive is only used unconfigured — stale mirrors can no longer resurrect deleted rows or mask outages
- `_resolve_experiment`/`_resolve_run` no longer consult the archive when Supabase is configured (miss stays missing)
- Compare returns 404 `candidate_not_found` (with ids) instead of silently comparing a smaller candidate set
- Production CSP explicitly allows Google Fonts (previously contradicted index.html); PWA/manifest scope fixed under `/app/`
- Removed 37 unreachable trailing `return False` statements left by the api.py split
- Frontend served-asset contract gated in CI (built HTML must reference `/app/`); new Playwright E2E job exercises the production image in a real browser
- `local` health checks hit `/app/`, drops SQLite references (JSONL ledgers), and no longer requires host Node/npm
- Experiment import no longer crashes on frozen `ExperimentRun` (runs get fresh ids, specs re-validated)
- Experiment version creation no longer self-references (standalone version records; specs validated)
- Reviewer identity bound to authenticated principal (`identity_mismatch` → 400; unattributed reviews rejected when auth is on; `identity_verified` flag in ledger)
- Review/prospective reads and prospective mutations now gated like other ops endpoints
- Incident/decision/template audit actors use the authenticated caller (or `anonymous`), never hardcoded names
- Traffic domain accepted end-to-end (validator, bounds, runner dispatch, live execution verified)
- Scheduler stores real jobs (validated specs, listable state) instead of acknowledging without scheduling
- `GET` routes no longer shadowed inside `do_POST` (templates/versions/runs/snapshots/benchmarks/evidence/export/replay/scheduler)
- `local.sh` generators synced with fixed Dockerfile/compose; canonical `RIFT_*` env names
- Vite dev proxy honors `VITE_API_TARGET` (host `npm run dev` works again)
- Dropped `className` props now forwarded in Badge/Input/Textarea/Select/Checkbox/Switch
- User menu buttons navigate (Settings/API Keys/Security tabs); sign-out clears the token; Language removed (no i18n); profile name shown
- `window.open` calls use `noopener,noreferrer`; ErrorBoundary no longer claims team notification nor leaks stacks in prod
- Missing `datetime` import (versions endpoint 500'd always); missing `__main__` block (API container crash-looped); Vite port/index.html/config mounts; CORS allow-list for browser API access

### Added
- `GET /api/events/stream` (SSE lifecycle events), `GET /api/intelligence/status`, `POST /api/intelligence/scenario|explain` (mock-labeled by default)
- `GET /api/experiments/*` Supabase fallbacks with ownership for export/replay; Supabase→archive dual-write mirror
- Domain-agnostic `guardian_core` stages; traffic domain with Guardian rules T-001…T-005
- Frontend CI job (lint zero-warnings, 15 Vitest tests, build) + bundle-size gate (2 MB JS)
- `prometheus.local.yml` for compose (production file stays k8s-only)
- Production image builds and serves the React app at `/app/` with SPA fallback
- Authoritative endpoint auth matrix in `docs/security.md`; `UPGRADE.md`, `EXTENSION.md`
- Durable-by-default review/prospective JSONL ledgers (lazy singletons, `RIFT_DATA_DIR`)
- JSON checkpoints with fingerprint integrity (pickle removed)
- `?owner=` / `?mine=true` listing filters for incidents/decisions

## [1.0.0] - 2026-09-27

### Added
- **Core Platform Foundation**: Domain-neutral optimization core, plugin architecture, formal scenario/state/intervention/perturbation specs
- **Decision Engine**: Counterfactual generation, policy enumeration, pruning, constraint-aware search, multi-objective, Pareto, robustness
- **CHAOS Engine**: Branching futures, multi-step, correlated/compound/probabilistic/worst-plausible disturbances, adversarial generation, fuzzing, regression scenarios
- **Digital Twin**: Sync, history, prediction, provenance, freshness, confidence, divergence detection, snapshots, replay, branching
- **Optimization Engine**: Exact, QAOA-expectation, QAOA-CVaR, quantum simulator backend, quantum-classical benchmarks
- **Guardian 2.0**: 16-rule staged verification (INPUT→STATE→MODEL→COUNTERFACTUAL→OPTIMIZATION→OUTPUT→DEPLOYMENT), PASS/WARN/WITHHOLD
- **Real-time Event System**: WebSocket/SSE event bus, source registry with trust scoring, cross-source consistency checking, auto-reconciliation/re-optimization
- **Live Operations**: Incident lifecycle (open→ack→investigating→resolved→closed), decision workflow (propose→accept/reject/override/request_review→execute), alert routing
- **3D Computational Twin**: Future tree with playback, pause/resume/step, historical replay, scenario comparison, perturbation/uncertainty visualization
- **Explainability**: Decision reasoning, assumption/provenance/model/evidence/fingerprint/guardian/audit explorers, LLM-grounded explanations
- **Experiment Platform**: Templates, versioning, deterministic replay, benchmarks, optimizer/model/perturbation/robustness/regression comparison, evidence bundles, export/import, scheduler
- **Model Lifecycle**: Semantic versioning, shadow mode, champion/challenger, drift/calibration monitoring, regression testing, lineage tracking
- **Performance**: Parallel simulations/perturbations/policies, deterministic caching, job queues, checkpointing, resource scheduling, benchmarks
- **Production Engineering**: JWT/API keys, RBAC/ABAC, rate limiting, abuse protection, input validation, structured logging, health checks, migrations, backup/restore, rollback
- **Developer Platform**: Python SDK (sync/async), TypeScript SDK generator, Plugin SDK (Domain/Optimizer/DataSource/EventAdapter/Webhook), OpenAPI/Markdown docs, runbooks, examples

### Domains
- **Smart Building Emergency** (reference): Evacuation route optimization with 3 routes, 4 policies
- **Traffic Optimization**: Urban corridor traffic light timing with green time ratio & cycle length

### Security
- AGPL-3.0-or-later license
- JWT/API key authentication, RBAC/ABAC authorization
- Signed webhook verification (HMAC-SHA256)
- Rate limiting (token bucket, sliding window)
- Input validation with size limits
- Structured JSON logging with correlation IDs

### Testing
- 283 backend tests passing
- Frontend TypeScript/Vite build passing
- Bandit security scan clean
- Semgrep manual clean

### Infrastructure
- Docker Compose local stack (API, Frontend, Redis, Prometheus, Grafana)
- One-command local deployment (`./local.sh start`)
- Health checks (startup/readiness/liveness)
- Database migrations (versioned, rollback-safe)
- Backup/restore capability
- Reproducible builds with BuildInfo

### Documentation
- OpenAPI 3.0 specification
- Markdown API reference
- Architecture documentation
- Contributor guide
- Runbook generator with templates
- Python/TypeScript/cURL examples

## [0.9.0] - 2026-09-20

### Added
- Clinical audit Phase 0 (70 modules, 41 tests, 14 endpoints)
- Benchmark methodology (SA + tabu, pre-registration)
- Study protocol template, QMS skeleton, traceability matrix
- Real hardware run (IBM Kingston, gap 0.0)
- Proxy fit on open cardiac data (LR fit train/test 1.0)
- Threat model, incident runbook, external gates documentation

### Fixed
- Semgrep as manual gate (not CI)
- Evidence sheet: "No raw real-patient data committed"

## [0.8.0] - 2026-09-15

### Added
- Guardian 2.0 with 16 rules
- Digital twin with provenance
- Counterfactual futures with assumption ledgers
- Robust ranking with adversarial verification

## [0.7.0] - 2026-09-10

### Added
- Quantum optimization (QAOA, CVaR-QAOA)
- IBM Quantum integration (AER simulator + hardware)
- Robust QUBO formulation

## [0.6.0] - 2026-09-05

### Added
- Counterfactual engine with branching futures
- CHAOS adversarial search
- Robust ranking with worst-case evaluation

## [0.5.0] - 2026-09-01

### Added
- Digital twin core loop (observe→sync→predict→update→recompute)
- Patient state, baseline, deviations, risk prediction
- Uncertainty quantification with decomposition

## [0.1.0] - 2026-08-15

### Added
- Initial project structure
- Smart-building emergency scenario
- Basic optimization engine