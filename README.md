# RIFT

![Tests](https://github.com/OpKnock/RIFT/actions/workflows/test.yml/badge.svg)
![Bandit](https://img.shields.io/badge/Bandit-0%20issues-brightgreen)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)

**Robust Intervention & Future Testing — Patient Digital Twin • FORESIGHT • Guardian**

> **Don't just predict the future. Search it. Break it. Verify it.**

**v1.0.0** • Production-oriented engineering, evidence-gated research platform — not clinically validated or production-deployed.

RIFT is a decision-intelligence engine for testing interventions *before* they are trusted. It enumerates counterfactual futures, attacks candidate policies with adversarial search, optimizes for robustness (not just expected value), and keeps hard safety verification outside the optimizer — so no score can bypass the safety gate.

The engine itself is domain-free. It ships with two frontends:

1. **Patient Digital Twin** (flagship demo) — EHR + wearable data → synchronized patient state → FORESIGHT trajectories → counterfactuals → robustness/uncertainty → Guardian → clinician dashboard.
2. **Counterfactual Laboratory** (original) — smart-building emergency simulation: live scenario controls, futures, CHAOS perturbations, exact-vs-quantum optimization, Guardian checks.

---

## Table of contents

- [The loop](#the-loop)
- [Patient Digital Twin demo](#patient-digital-twin-demo)
- [Counterfactual Laboratory](#counterfactual-laboratory)
- [Run it](#run-it)
- [API reference](#api-reference)
- [Data platform](#data-platform)
- [FORESIGHT & robustness](#foresight--robustness)
- [Guardian 2.0](#guardian-20)
- [Evidence & honesty rules](#evidence--honesty-rules)
- [Quantum layer](#quantum-layer)
- [Auth, ownership & rate limiting](#auth-ownership--rate-limiting)
- [Persistence](#persistence)
- [Billing](#billing)
- [Monitoring & ops](#monitoring--ops)
- [Configuration](#configuration)
- [Docker & Kubernetes](#docker--kubernetes)
- [Repository layout](#repository-layout)
- [Documentation map](#documentation-map)
- [Quality gates](#quality-gates)
- [Status & open gates](#status--open-gates)
- [Safety boundary](#safety-boundary)
- [License](#license)

---

## The loop

```
WORLD STATE
    ↓
ORACLE — scenario / world-transition model
    ↓
COUNTERFACTUAL FUTURES — branch the present into candidate policies
    ↓
CHAOS — adversarial perturbation search over declared variables
    ↓
QUBO — policy energy landscape (exact robust objective)
    ↓
CLASSICAL (exact) / QUANTUM (QAOA simulator) OPTIMIZER
    ↓
GUARDIAN — independent verification, unbypassable
    ↓
ROBUST POLICY + assumptions + evidence
```

Design principles (`docs/architecture.md`):

1. Deterministic experiments with explicit seeds.
2. Pure domain logic independent of HTTP/database.
3. Pluggable optimizers with explicit backend metadata.
4. Verification cannot be bypassed by an optimizer score.
5. Every recommendation exposes assumptions and evidence.
6. Quantum execution is experimental; no automatic advantage is claimed.

---

## Patient Digital Twin demo

EHR + replayable wearable data → synchronized patient state → personal baselines → 24h cardiac-strain risk → FORESIGHT futures → robustness/uncertainty → Guardian verdict → reasons → dashboard (`docs/patient-twin.md`).

```
EHR ──normalize──┐
                 ├─→ PatientState(t) ──→ twin.sync ──→ baseline(<t) ──→ deviations
wearable ─replay─┘          │                  │              │
  (ReplaySource /           │                  ▼              ▼
   LiveIngestSource)        │           24h strain risk ──→ contributions
                            │                  │
                            │                  ├─→ FORESIGHT: 4 policies ──→ futures
                            │                  │                    ├─→ 3-day trajectories
                            │                  │                    └─→ robust ranking
                            │                  ├─→ uncertainty = quality-base + spread/2
                            │                  └─→ Guardian (ALLOW / WARN / WITHHOLD) ──→ reasons
                            └─→ snapshot → history (replayable) → dashboard
```

Target: next-24h cardiac-strain risk for one synthetic demo patient. **Synthetic data, transparent demo weights, decision support only — never autonomous care, never clinically validated.**

```bash
rift serve
# open http://127.0.0.1:8080
```

Key hygiene properties (all tested):

- Baselines use only observations with `day_index < t` — today can never redefine today's "normal" (no leakage).
- Generic `heart_rate` is never relabeled `resting_hr`; RR-interval SD is never relabeled RMSSD; unit conversions include offsets (300 K → 26.85 °C).
- `patient_id` is preserved end-to-end: ingestion → timeline → twin state; multi-patient streams never collapse into one.
- Outcomes (`sepsis_label`) live in a separate channel from features.

---

## Counterfactual Laboratory

The original smart-building emergency simulation (`rift demo`): live scenario controls, counterfactual futures, adversarial perturbations, robust optimization with exact classical baseline vs QAOA expectation vs QAOA-CVaR (lowest-cost tail — not the worst-loss-tail convention), a three-variable policy lab (`route_a`, `route_c`, `stairwell_b`), quadratic projection with reported approximation gap, and independent Guardian checks.

```bash
rift demo        # terminal futures + robust ranking
```

---

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]" -c constraints.txt
pytest                                # 281 passing
rift demo                             # counterfactual lab (terminal)
rift twin-demo                        # patient twin story (terminal)
rift serve                            # http://127.0.0.1:8080
```

Pinned, reproducible installs: `constraints.txt`. Optional extras: `supabase`, `qiskit`, `physio` (WFDB readers for real ECG datasets).

```bash
pip install -e ".[dev,supabase,physio]" -c constraints.txt
```

The API server is standard-library only (`http.server`) — no web framework at runtime.

---

## API reference

Base: `http://127.0.0.1:8080`. Every response carries `X-Request-ID`. Errors are `{"error": "<code>"}` — never stack traces or secrets. Full contract: `docs/api.md`.

| Endpoint | Description |
|---|---|
| `GET /api/health` | Liveness + version + persistence/billing status (always open) |
| `GET /api/meta` | Capabilities, limits, optimizer list |
| `GET /api/demo` | Emergency-lab demo (unchanged legacy endpoint) |
| `GET /api/twin/demo?t=<day>` | Twin snapshot: state, risk, trajectories, Guardian, reasons |
| `GET /api/twin/evidence` | Frozen evidence: backtest, calibration, external validation |
| `GET/POST /api/twin/prospective` | Lock predictions / reconcile outcomes |
| `GET /api/ops/monitor` | Ops snapshot + alert evaluation (auth-gated when auth is set) |
| `GET /metrics` | Prometheus exposition (auth-gated when auth is set) |
| `POST /api/experiments` | Persist a fingerprinted spec (needs database) |
| `GET /api/experiments/{id}` | Fetch spec (ownership-checked) |
| `POST /api/experiments/{id}/runs` | Record a run |
| `GET /api/experiments/{id}/runs` | List runs, capped at 200 (paginated soon) |
| `POST /api/experiments/{id}/execute` | Server-side reproducible run (stricter rate budget) |
| `GET /api/runs/{id}` | Fetch a run (ownership-checked) |
| `POST /api/billing/checkout` | Provider checkout (needs credentials) |
| `POST /api/billing/webhook` | HMAC-verified webhook, idempotent, 502-retryable |
| `GET /api/billing/entitlement` | Server-derived entitlement |
| `GET /api/billing/status`, `GET /api/persistence/status` | Integration status (no secrets) |

---

## Data platform

All measurements enter through one canonical pipeline (`src/rift/health/observations.py`): strict ISO-8601 UTC timestamps, finite values, known units with offsets, required `patient_id` + `source`, quality in [0, 1]. Rejections carry reasons; nothing is clamped or defaulted.

- **Sources** — FHIR R4 Observation subset, CSV/JSON adapters, replayable `ReplaySource`, append-only `LiveIngestSource`, and `PublicDatasetSource` (provenance-rich CSV; fail-closed on any rejected row; legacy day-index CSV deprecated).
- **FHIR clinical** (`fhir_clinical.py`) — Patient/Condition/Medication/Encounter/Device parsing, paginated authenticated extraction with retry/backoff + manifests, SSRF-hardened fetching (HTTPS-only in production, host allowlist, no redirects, private-IP refusal, DNS timeout). Tested against a local fixture, not a live hospital server.
- **Terminology** (`terminology.py`) — versioned registry (LOINC 2.83); unmapped codes rejected with reviewable status, never guessed.
- **Timeline** (`timeline.py`) — hour/day/week bucketing, median or quality-weighted estimation, per-snapshot coverage report, plus an hourly path (`to_hourly_rows`) so acute ICU data isn't collapsed into daily rows.
- **Estimators & drift** — median/weighted/EWM comparison with disagreement report; distribution/missingness/source drift with explicit thresholds (including variance-collapse detection).
- **Real-data seams** (all with provenance sidecars) — BIDSleep sleep recordings, wearable exam-stress sessions, PhysioNet Sepsis Challenge 2019 (ICULOS-relative time, per-row labels, fail-closed cohort), CHFDB congestive-heart-failure ECG via the validated `wfdb` package (`.dat`/`.hea`/`.ecg`, 15 subjects). Real sensor data proves ingestion — it does **not** validate the cardiac-strain model.

---

## FORESIGHT & robustness

- **FORESIGHT** — 4 intervention policies rolled through the bounded transition model into 3-day risk trajectories, robust-ranked under sensor/parameter perturbations.
- **Robustness** — CHAOS adversarial search, exact robust QUBO objective, uncertainty decomposed into quality/jitter/spread components (labeled heuristic-demo).
- **Evaluation** — independent outcome rule (breaks self-agreement circularity), rolling backtests with onset lead/lag, noise stress sweeps, Platt calibration repair fit on calibration days only, external no-refit validation on a disjoint synthetic series, threshold tradeoff tables, sample-adequacy gate (100/100 events bar; current 5/54 → `limited`).

---

## Guardian 2.0

Staged enforcement INPUT → STATE → MODEL → COUNTERFACTUAL → OUTPUT → DEPLOYMENT. Every check emits `{rule_id, stage, severity, action, message, evidence}`. `WITHHOLD` blocks display; `WARN` travels as a warning.

| Rule | Stage | Effect |
|---|---|---|
| G-001 impossible physiology | STATE | WITHHOLD |
| G-002 missing fields | INPUT | WARN |
| G-003 stale data | INPUT | WARN |
| G-004 unrecorded provenance | INPUT | WARN |
| G-005 implausible HR shift | STATE | WITHHOLD |
| G-006 unsupported output fields | OUTPUT | WITHHOLD |
| G-007 treatment instructions | OUTPUT | WITHHOLD |
| G-008 excessive uncertainty | OUTPUT | WARN |
| G-009 low input quality | OUTPUT | WARN |
| G-010 OOD population scope | MODEL | WARN |
| G-011 unestimated metrics | INPUT | WARN |
| G-012 feature-schema drift | INPUT | WITHHOLD (missing) / WARN (additive) |
| G-013 counterfactual assumption ledgers | COUNTERFACTUAL | WITHHOLD |
| G-014 optimization-output verification | COUNTERFACTUAL | WITHHOLD |
| G-015 model identity/digest | MODEL | WITHHOLD |
| G-016 deployment inversion | DEPLOYMENT | WITHHOLD |

Guardian is a display-safety layer, not a certification mechanism and not a substitute for clinical review.

---

## Evidence & honesty rules

- `GET /api/twin/evidence` serves the frozen synthetic evidence bundle (backtest, calibration repair, external validation, adequacy verdict). See `docs/evidence-sheet.md`.
- Sample-adequacy gate: good point estimates cannot upgrade a thin-evidence claim.
- Overclaim-language regression guard: the codebase refuses to call synthetic metrics clinical.
- Model registry pins weights digests; promotion requires evidence + approver + notes; rollback walks the audit chain; deployment gate stays closed without validated, calibrated, reviewed, non-synthetic evidence.
- Predictions carry deterministic IDs over the complete input context; prospective locks are immutable (durable storage is a known open gate — current ledger is in-memory).

---

## Quantum layer

Candidate decisions are represented as QUBOs with a `QuantumOptimizer` interface. The shipped path is a dependency-free QAOA statevector simulator; exact classical enumeration is always the reference baseline. No hardware speedup is claimed. The optional Qiskit/IBM adapter is gated until credentials, backend selection, transpilation, sampling, and result validation are configured (`qpu.py` raises `NotImplementedError` by design).

---

## Auth, ownership & rate limiting

- **Open dev mode** (nothing set): frictionless local use.
- **Service-token mode** (`RIFT_API_TOKEN`): bearer gate on persistence/checkout/entitlement + ops endpoints (`/metrics`, `/api/ops/monitor`).
- **Verified JWT mode** (`RIFT_SUPABASE_JWT_SECRET`): identity is the token `sub`; spoofed `user_id` ignored; `none`/foreign algorithms, bad signatures, expired tokens → 401.
- Per-row ownership enforced server-side (`owner_mismatch` fails closed); cross-user reads → 403.
- In-process fixed-window rate limiting (`RIFT_RATE_LIMIT_ENABLED=true`), stricter `.../execute` scope, `429 + Retry-After`; edge rules still required in production.

---

## Persistence

Seven additive, idempotent, RLS-safe migrations (`backend/supabase/migrations/001→007`): experiments/runs, hardening, billing mirror, experiment model + webhook idempotency constraint, run ownership, model registry + prediction audit, observations. An optional server-side adapter persists experiments/runs; unconfigured servers return `503 persistence_not_configured` and the engine runs offline. No live project is evidenced in this repo — see the release checklist.

---

## Billing

Provider boundary (`src/rift/billing.py`): checkout, HMAC `X-Signature` verification (`hmac.compare_digest`), idempotent webhook with DB unique constraint, check-then-resume subscription mirror (recorded-but-unprocessed events resume on retry; failures answer 502 so the provider retries), server-derived entitlements. Disabled by default; needs `RIFT_LEMON_SQUEEZY_*` server env. No live transactions claimed. See `docs/billing.md`.

---

## Monitoring & ops

In-process collector (request/latency/failure counters, prediction distribution, Guardian action rates, missingness) with linear-interpolation percentiles. Single Prometheus vocabulary (`EXPORTED_METRICS` / `render_prometheus`) shared by `/metrics`, alert rules, and the Grafana dashboard — enforced by a contract test. Alertmanager routing, Prometheus + Grafana configs under `monitoring/` and `deployment/docker/`. Delivery (PagerDuty/Slack) is intentionally absent: alerting without an operator would be theater.

---

## Configuration

Copy `.env.example` to `.env` (never commit secrets). Everything optional; engine runs offline empty.

| Variable | Purpose |
|---|---|
| `RIFT_SUPABASE_URL` / `RIFT_SUPABASE_KEY` | Persistence (service-role stays server-side) |
| `RIFT_API_TOKEN` | Service-token gate |
| `RIFT_REQUIRE_USER_ID` | Require caller `user_id` scoping |
| `RIFT_SUPABASE_JWT_SECRET` (+`_AUD`/`_ISSUER`/`_LEEWAY_S`) | Verified JWT identity |
| `RIFT_RATE_LIMIT_ENABLED`, `RIFT_RATE_LIMIT_*`, `RIFT_TRUST_PROXY` | In-process rate limiting |
| `RIFT_LEMON_SQUEEZY_*` | Billing (all four required to enable) |
| `RIFT_MAX_POLICY_VARIABLES` / `MAX_PERTURBATIONS` / `MAX_PAYLOAD_BYTES` | Compute/input bounds |
| `RIFT_ALLOW_PRIVATE_FETCH`, `RIFT_ALLOW_HTTP`, `RIFT_TRUSTED_FHIR_HOSTS` | FHIR fetch safety |
| `QUANTUM_BACKEND` | `none` (default) |

---

## Docker & Kubernetes

- **Production image** (`deployment/docker/Dockerfile`): multi-stage, non-root `rift` user, constraints-pinned, healthchecked, binds `0.0.0.0`. Built + smoke-tested in CI:
  `docker build -f deployment/docker/Dockerfile -t rift:ci .`
- **Demo image** (`Dockerfile`, repo root): simple single-stage local build.
- **Compose** (`deployment/docker/docker-compose.yml`): API + Prometheus + Grafana + Alertmanager for local observability.
- **Kubernetes** (`deployment/kubernetes/`): staging manifest + production blue/green with HPA/PDB, probes, TLS ingress, required JWT secret + rate limiting in prod, least-privilege (no workload RBAC — secrets arrive via `secretKeyRef`).
- **CI template** (`deployment/github-actions/ci.yml`): full pipeline template, explicitly not active proof. Active CI is `.github/workflows/test.yml` (+ weekly/manual `physio-integration.yml` for real WFDB extraction).

---

## Repository layout

```
src/rift/                  # domain-free engine: counterfactuals, CHAOS, QUBO,
                           # QAOA simulator, CVaR, verifier, runner, experiments,
                           # auth, billing boundary, api.py, cli.py
src/rift/health/           # patient twin: observations, adapters, timeline,
                           # baseline, transition, risk, twin, FORESIGHT,
                           # robustness, Guardian, evaluate, evidence, registry,
                           # training, FHIR, drift, monitoring, scrapers
web/                       # dashboard: index.html + app.js + styles.css
backend/supabase/migrations/  # 001→007, additive + idempotent + RLS
tests/                     # 281 tests incl. test_internal_audit_regression.py
docs/                      # architecture, PRD, api, patient-twin, evidence-sheet,
                           # security, deployment, billing, roadmap, ... (17 files)
monitoring/                # Prometheus rules + config (single metric contract)
deployment/                # docker, kubernetes (staging/production), CI template
scripts/                   # validate_migrations, secret_scan, check_versions,
                           # check_phase_matrix (+ archive/ retired tooling)
data/                      # synthetic examples + provenance-tracked public samples
constraints.txt            # pinned research environment
```

---

## Documentation map

| Document | What it is |
|---|---|
| `docs/evidence-sheet.md` | One-page frozen evidence + standing limitations |
| `docs/patient-twin.md` | Twin pipeline, Guardian registry, forecasting hygiene |
| `docs/architecture.md` | Module boundaries, principles, endpoint plan |
| `docs/PRD.md` | Product requirements, non-goals, roadmap |
| `docs/api.md` | Full API contract |
| `docs/security.md` | Auth modes, residual risks |
| `docs/deployment.md` | Local/Docker/prod edge checklist |
| `docs/supabase-setup.md` | Migration + RLS setup |
| `docs/billing.md` | Manual provider connection |
| `docs/roadmap.md` | Research roadmap, honest pending items |
| `docs/release-checklist.md` | Evidence-gated release boxes (incl. scientific gates) |
| `docs/demo-script.md` | 5-minute judged demo walkthrough |
| `docs/design-system.md` | UI tokens and conventions |
| `docs/review.md`, `docs/experiments.md`, `docs/agents.md` | Review, experiment, agent notes |
| `docs/phase-matrix.json` | 21/21 COMPLETE = code-scope (blockers listed inside) |
| `CHANGELOG.md` | Full history from v0.6.0 through v1.0.0 |
| `AGENTS.md` | Working map + rules for coding agents |

---

## Quality gates

```bash
pip install -e ".[dev]" -c constraints.txt
pytest                                  # 281 passing
python scripts/validate_migrations.py   # 7 files ok
python scripts/secret_scan.py           # clean
python scripts/check_versions.py        # 1.0.0 ok
python scripts/check_phase_matrix.py    # 21/21 code-scope ok
python -m bandit -r src -q              # 0 findings
semgrep --config auto --error --quiet src/  # 0 findings
```

CI (`test.yml`): test + validate + security + real Docker build & `/api/health` smoke — all green on `main`. Accessibility (`accessibility/`: pa11y, axe-core, Lighthouse) is manual/non-blocking until promoted.

---

## Status & open gates

`v1.0.0` is a **final audited research-prototype implementation**: 281 tests, SAST clean, real Docker 
build green, no known P1/P2 defects, no open issues/PRs.

It is **not** clinically validated or production-deployed. Open gates (documented, not hidden): governed clinical dataset + predefined endpoint + adequate event volume → independent external validation → prospective validation → clinical review/governance → live database/RLS, billing, FHIR, devices, alerting, edge TLS/CORS → jurisdiction-specific regulatory assessment. The 21-phase matrix reads COMPLETE at code scope only.

---

## Safety boundary

RIFT is a research and simulation system. It does not autonomously control real emergency infrastructure, and its healthcare demo never directs care: predictions are decision support for a human clinician, built on synthetic data with synthetic weights. Real deployment would require validated domain models, calibrated sensors, human oversight, formal hazard analysis, and jurisdiction-specific certification.

---

## License

**AGPL-3.0-or-later** — see [`LICENSE`](./LICENSE). Anyone running a modified version over a network must offer the corresponding source to its users (Section 13). Copyright (C) 2026 Mehul Wagde.
