# RIFT

**Robust Intervention & Future Testing**

> **Test the decision. Break the future.**

RIFT is a decision-intelligence engine for testing interventions before they are trusted. It enumerates counterfactual futures, searches adversarial conditions, ranks robust policies, and keeps hard safety verification outside the optimizer.

Its flagship demo is a **Patient Digital Twin**: EHR + replayable wearable
data → synchronized patient state → FORESIGHT future trajectories →
counterfactuals → robustness/uncertainty → Guardian → doctor dashboard
(see [Patient Digital Twin demo](#patient-digital-twin-demo)). The same
engine also powers the original smart-building Counterfactual Laboratory.

## The loop

```
WORLD STATE
    ↓
ORACLE — scenario/world transition model
    ↓
COUNTERFACTUAL FUTURES
    ↓
CHAOS — adversarial perturbation search
    ↓
QUBO — policy energy landscape
    ↓
CLASSICAL / QUANTUM OPTIMIZER
    ↓
GUARDIAN — independent verification
    ↓
ROBUST POLICY
```

The engine also ships a runnable **Counterfactual Laboratory** built around a smart-building emergency simulation. It exposes live scenario controls, counterfactual futures, adversarial perturbations, robust optimization, a dependency-free QAOA statevector simulator, CVaR-style best-tail optimization, a three-variable policy lab, and independent Guardian checks.

## Run it

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
rift demo
rift serve
```

Then open `http://127.0.0.1:8080`.

The laboratory intentionally uses Python's standard library for the web server, keeping the demo lightweight and dependency-free at runtime.

## Quantum layer — deliberately honest

RIFT represents candidate decisions as QUBOs and exposes a `QuantumOptimizer` interface. The shipped quantum path is a small dependency-free QAOA statevector simulator; exact classical enumeration remains the reference baseline.

QAOA is a hybrid quantum-classical optimization method. RIFT therefore does **not** claim that quantum hardware automatically evaluates every future, provides guaranteed speedup, or beats classical optimization. The research question is empirical: whether quantum optimization provides measurable value on particular policy-search workloads.

The optional Qiskit/IBM adapter is deliberately gated until credentials, backend selection, transpilation, sampling, and result validation are configured.

## Robust optimization

For the current two-variable emergency-routing QUBO, RIFT constructs an exact robust objective over the declared perturbation set and compares exact enumeration with expectation-QAOA and CVaR-QAOA.

The CVaR implementation is explicitly the **lowest-cost probability tail for minimization**. It should not be confused with the conventional worst-loss-tail definition used in some risk-management contexts.

## Multi-variable policy laboratory

RIFT evaluates three binary controls — `route_a`, `route_c`, and `stairwell_b` — across 8 policies using exact robust enumeration. A quadratic projection can then approximate the higher-order robust Boolean objective for QAOA.

The projection is **not** treated as exact. RIFT reports its maximum and mean absolute objective gap against the exact robust objective so the approximation error is visible rather than hidden.

## Guardian verification boundary

Guardian independently verifies the selected policy against the nominal state **and every declared adversarial perturbation**. Optimization results cannot bypass these hard constraints.

This is a simulation safety boundary, not a certification mechanism.

## Patient Digital Twin demo

RIFT's engine now also drives a healthcare demo: EHR + replayable wearable
data → synchronized patient twin → FORESIGHT trajectories → counterfactuals
→ robustness/uncertainty → Guardian → doctor dashboard. See
`docs/patient-twin.md`.

```bash
rift serve
# open http://127.0.0.1:8080
```

Target: next-24h cardiac-strain risk for one synthetic demo patient.
Synthetic data, transparent demo weights, decision support only — never
autonomous care, never clinically validated. The emergency-lab `/api/demo`
endpoint is unchanged.

## Product surfaces

- **Patient Digital Twin** — synchronized patient state, FORESIGHT trajectories, what-if policies, robustness, Guardian verdict, evidence.
- **Counterfactual Laboratory** — branch the present into candidate futures.
- **CHAOS** — perturb declared variables and expose high-risk futures.
- **QUANTUM** — compare classical enumeration, QAOA expectation, and QAOA CVaR.
- **POLICY LAB** — inspect the exact multi-variable robust search and quadratic QAOA projection.
- **GUARDIAN** — independently verify nominal and adversarial states.
- **Benchmarking** — expose objective quality and runtime without claiming quantum advantage.

## Persistence

Supabase migrations under `backend/supabase/migrations/` provide experiment/run tables (`001`), production hardening with explicit grants and metadata (`002`), a service-role-only billing mirror (`003`), the first-class experiment model with lifecycle, reproducibility, and webhook idempotency (`004`), and run ownership (`005`). `src/rift/supabase_store.py` is the optional server-side adapter; `src/rift/settings.py` centralizes env handling; `src/rift/experiments.py` defines serializable specs with fingerprints.

A live Supabase project is **not** hard-coded into the repository. Configure `RIFT_SUPABASE_URL` and `RIFT_SUPABASE_KEY` only in a trusted server environment (legacy `SUPABASE_*` names accepted as fallback). Never expose a service-role key to the browser. See `docs/supabase-setup.md`.

When configured, the server exposes persistence endpoints (`POST /api/experiments`, `GET /api/experiments/{id}`, `POST /api/experiments/{id}/runs`, `POST /api/experiments/{id}/execute` for server-side reproducible runs, `GET /api/experiments/{id}/runs`, `GET /api/runs/{id}`); when absent they return `503 persistence_not_configured` and the engine still runs offline.

## Review and billing integrations

`.coderabbit.yaml` enables CodeRabbit reviews **only if** the CodeRabbit GitHub App is installed on the repository. It does not by itself perform a review. Do not treat this release as CodeRabbit-reviewed unless a CodeRabbit check run is visible on the corresponding PR. See `docs/review.md`. GitHub Actions (`test.yml`) provides the repository's automated test gate.

Lemon Squeezy billing is implemented as a provider boundary (`src/rift/billing.py`) with `POST /api/billing/checkout` and `POST /api/billing/webhook` (HMAC `X-Signature` verification, fail-closed without a webhook secret, idempotent retries, subscription lifecycle mapping, server-derived entitlements via `GET /api/billing/entitlement`). It is disabled by default and requires `RIFT_LEMON_SQUEEZY_API_KEY`, `RIFT_LEMON_SQUEEZY_STORE_ID`, and `RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET` on the server. No account, credentials, or products are configured in this environment, so no live checkout or webhook delivery has been executed or claimed. See `docs/billing.md`.

## Safety boundary

RIFT is a research and simulation system. It does not autonomously control real emergency infrastructure, and its healthcare demo never directs care: predictions are decision support for a human clinician, built on synthetic data with synthetic weights. Real deployment would require validated domain models, calibrated sensors, human oversight, formal hazard analysis, and jurisdiction-specific certification.

## Status

**v0.6.0 — Patient Digital Twin release candidate (Counterfactual Laboratory included).**

The release candidate is intended to be demo-ready when the repository CI gate is green. Quantum hardware, hosted Supabase, CodeRabbit, and billing are optional external integrations rather than hidden dependencies.
