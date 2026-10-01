# RIFT — Robust Intervention & Future Testing

> **Research prototype, not clinical software.** AGPL-3.0-or-later.

RIFT is a domain-neutral optimization platform for generating counterfactual futures, stress-testing them with adversarial chaos, and verifying decisions with a staged safety system (Guardian). The reference domain is smart-building emergency evacuation; a second domain (traffic optimization) validates the plugin architecture. A third domain (cardiovascular digital twin) demonstrates clinical decision support with honest evaluation.

## Quick Start

```bash
# One-command local startup (API + Redis + Prometheus + Grafana + UI)
./local.sh start

# Serve Stitch UI foreground (Ctrl+C to stop)
./local.sh ui

# Run demo
./local.sh demo

# Health check
./local.sh health

# Run tests
./local.sh test

# Full diagnostics
./local.sh diag

# Initialize demo data
./local.sh init

# Generate config files
./local.sh gen-config

# Shell into container
./local.sh shell

# Clean reset
./local.sh reset
```

## Track A: Cardiovascular Digital Twin (NEW)

A complete cardiovascular domain built on the UCI Z-Alizadeh Sani Extension dataset (303 patients, 59 features, 4 targets: CAD, LAD, LCX, RCA stenosis).

### What's included
- **4 registered models**: `cad-v1` (logreg), `lad-stenosis-v1` (RF), `lcx-stenosis-v1` (RF), `rca-stenosis-v1` (logreg)
- **Leakage firewall** — LAD/LCX/RCA/Cath columns never reach model inputs
- **OOF calibration** — isotonic regression fit on train+val, test reported once
- **Permutation explainability** — AUC-drop on held-out test, corrective counterfactuals
- **Honest model cards** — RCA flagged "NOT decision-grade", LCX "does NOT rule out"
- **3D Coronary viewer** — schematic LM/LAD/LCX/RCA with calibrated probabilities
- **Evaluation dashboard** — metrics, reliability curves, feature importance, model cards
- **Safety layer** — refuses uncalibrated models, flags weak models & OOD inputs
- **Verify checklist** — 7 automated checks (data hash, registry, artifacts, mirrors, pages, API, bandit)

### Quick start (Track A)
```bash
# Reproduce entire pipeline from raw UCI zip
python -m rift.health.cardiovascular.pipeline

# Run verify checklist (7 gates)
python -m rift.health.cardiovascular.verify

# Start local stack + open coronary viewer
./local.sh start
# open http://localhost:8000/coronary.html
# open http://localhost:8000/cardio-dashboard.html
```

### Cardio API endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /api/cardio/models` | List 4 registered models + test AUC |
| `GET /api/cardio/report` | Full evaluation report (test + CV) |
| `GET /api/cardio/model-cards` | Honest per-model limitation cards |
| `POST /api/cardio/predict` | Calibrated probability + safety verdict + optional counterfactuals |

### Cardio pipeline (one command)
```bash
python -m rift.health.cardiovascular.pipeline
# dataset -> train -> evaluate -> calibrate -> explain -> site
# Add --from-step=site to resume UI-only changes
```

### Verify checklist
```bash
python -m rift.health.cardiovascular.verify
# 7 gates: data hash, registry, artifacts, UI mirrors, pages, API smoke, bandit
```

## Architecture

```
RIFT Core
  → Scenario/World Engine
  → Counterfactual + CHAOS Engine
  → Digital Twin
  → Optimization Engine
  → Guardian (Safety)
  → Event/Data Infrastructure
  → Experiment/Reproducibility
  → Platform Services
  → 3D/Operational Interface
  → Developer Ecosystem
  → Testing/Governance
```

## Key Features

- **Counterfactual Engine**: Generate and rank futures under perturbations
- **CHAOS/Adversarial**: Automated stress-testing, fuzzing, regression scenarios
- **Digital Twin**: Patient state sync, risk prediction, trajectories, provenance
- **Optimization**: Exact, QAOA, CVaR-QAOA with quantum simulator backends
- **Guardian 2.0**: 16-rule staged verification (INPUT→STATE→MODEL→COUNTERFACTUAL→OPTIMIZATION→OUTPUT→DEPLOYMENT)
- **Real-time**: SSE event stream (`GET /api/events/stream`: incident/decision lifecycle), source registry with trust scoring, cross-source consistency, auto-reconciliation (no WebSocket upgrade on the stdlib server)
- **Experiments**: Templates, versioning, deterministic replay, benchmarks, comparisons, export/import
- **Model Lifecycle**: Versioning, shadow mode, champion/challenger, drift/calibration monitoring, lineage
- **Performance**: Parallel execution, deterministic caching, job queues, checkpointing, resource scheduling
- **Production**: JWT/API keys, RBAC/ABAC, rate limiting, structured logging, health checks, migrations, rollback
- **Developer**: Python/TypeScript SDKs, plugin SDK, OpenAPI docs, runbooks, examples

## Domains

1. **Smart Building Emergency** (reference) — Evacuation route optimization
2. **Traffic Optimization** — Urban corridor traffic light timing
3. **Power Grid** — Grid stability & contingency analysis (`src/rift/domains/powergrid/`)
4. **Cardiovascular Digital Twin** (Track A) — Coronary stenosis prediction with honest evaluation

## Cardio API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/cardio/models` | List 4 registered models + test AUC |
| `GET /api/cardio/report` | Full evaluation report (test + CV) |
| `GET /api/cardio/model-cards` | Honest per-model limitation cards |
| `POST /api/cardio/predict` | Calibrated probability + safety verdict + optional counterfactuals |

## Existing API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/meta` | Engine metadata, capabilities, limits |
| `GET /api/demo` | Run smart-building demo |
| `GET /api/twin/demo?t=13` | Digital twin snapshot |
| `GET /api/twin/evidence` | Full evidence bundle |
| `GET /api/ops/monitor` | Operational metrics |
| `POST /api/experiments` | Create experiment |
| `GET /api/experiments` | List experiments |
| `POST /api/experiments/compare` | Compare optimizer/model/perturbation |
| `GET /api/experiments/templates` | List templates |
| `GET /api/operations/incidents` | Incident lifecycle |
| `GET /api/operations/decisions` | Decision workflow |
| `GET /api/explainability/audit` | Audit trail |
| `GET /api/events/stream` | Real-time event stream (SSE, no WebSocket upgrade) |

## Stitch UI Pages

| Page | Description |
|------|-------------|
| `dashboard.html` | Main landing — engine status, quick actions |
| `scenarios.html` | Scenario builder & runner |
| `simulation.html` | Simulation runner with live metrics |
| `runs.html` | Run history, comparison, export |
| `experiments.html` | Experiment templates, versioning, replay |
| `evidence.html` | Evidence bundles, review workflow |
| `incidents.html` | Incident lifecycle, acknowledgements |
| `explainability.html` | Audit trail, feature importance |
| `settings.html` | Auth, billing, integrations, purge |
| `coronary.html` | **Track A** — 3D coronary tree with calibrated stenosis probabilities |
| `cardio-dashboard.html` | **Track A** — Evaluation dashboard (metrics, calibration, features, model cards) |

Access at `http://localhost:8000/<page>.html` after `./local.sh start` or `./local.sh ui`.

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key variables:
- `RIFT_ENV` — development/production
- `RIFT_SUPABASE_URL` / `RIFT_SUPABASE_KEY` — database (unset = in-process archive + durable-JSONL fallback under `data/`; no SQLite)
- `RIFT_SUPABASE_JWT_SECRET` — Verified-JWT identity (production)
- `RIFT_API_TOKEN` — Service token for auth (leave empty for local open-dev mode; the UI then needs no login)
- `RIFT_QPU_TOKEN` — IBM Quantum token (optional)
- `RIFT_LEMON_SQUEEZY_*` — Billing (optional)

## Development

```bash
# Install Python deps
pip install -r constraints.txt
pip install -e .

# Run API locally
python -m rift.api

# Run tests
python -m pytest tests/ -x -q

# Track A: Cardiovascular pipeline & verify
python -m rift.health.cardiovascular.pipeline
python -m rift.health.cardiovascular.verify
```

The web UI is built in Stitch (project "RIFT Premium - Counterfactual
Decision Intelligence", 9 screens) and talks to this API over HTTP.
This repo ships the engine API only.

## Docker

```bash
# One-command local stack (API + Redis + Prometheus + Grafana + UI background)
./local.sh start

# Serve Stitch UI foreground (Ctrl+C to stop)
./local.sh ui

# Services:
# - API: http://localhost:8080 (`/` returns the API index JSON)
# - UI: http://localhost:8000 (Stitch screens, served automatically)
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)

# Other local commands
./local.sh init      # Initialize demo data
./local.sh diag      # Full environment diagnostics
./local.sh shell     # Shell into API container
./local.sh gen-config # Generate Dockerfile.dev, docker-compose, .env.local
./local.sh logs [svc] # Show logs
```

## Extending with Plugins

```python
# Create a custom domain
from rift.developer.plugin_sdk import DomainPlugin

class MyDomain(DomainPlugin):
    @property
    def domain_id(self): return "my-domain"
    # ... implement required methods

# Register via manifest.json in extensions/my-domain/
```

## License

AGPL-3.0-or-later — Copyright 2026 Mehul Wagde (OpKnock)

## Disclaimer

**Research prototype, not clinical software.** No clinical capability claimed without validation. No quantum advantage demonstrated. All synthetic/demo results clearly identified.