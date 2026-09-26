# RIFT — Robust Intervention & Future Testing

> **Research prototype, not clinical software.** AGPL-3.0-or-later.

RIFT is a domain-neutral optimization platform for generating counterfactual futures, stress-testing them with adversarial chaos, and verifying decisions with a staged safety system (Guardian). The reference domain is smart-building emergency evacuation; a second domain (traffic optimization) validates the plugin architecture.

## Quick Start

```bash
# One-command local startup
./local.sh start

# Run demo
./local.sh demo

# Health check
./local.sh health

# Run tests
./local.sh test

# Full diagnostics
./local.sh diag

# Clean reset
./local.sh reset
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
- **Real-time**: WebSocket/SSE event bus, source registry with trust scoring, cross-source consistency, auto-reconciliation
- **Experiments**: Templates, versioning, deterministic replay, benchmarks, comparisons, export/import
- **Model Lifecycle**: Versioning, shadow mode, champion/challenger, drift/calibration monitoring, lineage
- **Performance**: Parallel execution, deterministic caching, job queues, checkpointing, resource scheduling
- **Production**: JWT/API keys, RBAC/ABAC, rate limiting, structured logging, health checks, migrations, rollback
- **Developer**: Python/TypeScript SDKs, plugin SDK, OpenAPI docs, runbooks, examples

## Domains

1. **Smart Building Emergency** (reference) — Evacuation route optimization
2. **Traffic Optimization** — Urban corridor traffic light timing

## API Endpoints

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
| `WS /events` | Real-time event stream |

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key variables:
- `RIFT_ENV` — development/production
- `DATABASE_URL` — SQLite (dev) or PostgreSQL (prod)
- `RIFT_API_TOKEN` — Service token for auth
- `JWT_SECRET` — JWT signing key
- `IBM_QPU_TOKEN` — IBM Quantum token (optional)
- `LEMON_SQUEEZY_*` — Billing (optional)

## Development

```bash
# Install Python deps
pip install -r constraints.txt
pip install -e .

# Install frontend deps
cd frontend && npm ci

# Run API locally
python -m rift.api

# Run frontend dev server
cd frontend && npm run dev

# Run tests
python -m pytest tests/ -x -q

# Type check
cd frontend && npx tsc --noEmit
```

## Docker

```bash
# One-command local stack
./local.sh start

# Services:
# - API: http://localhost:8080
# - Frontend: http://localhost:5173
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
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