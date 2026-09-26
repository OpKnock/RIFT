# Changelog

All notable changes to RIFT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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