# RIFT

**Robust Intervention & Future Testing**

> **Test the decision. Break the future.**

RIFT is a decision-intelligence engine for testing interventions before they are trusted. It enumerates counterfactual futures, searches adversarial conditions, ranks robust policies, and keeps hard safety verification outside the optimizer.

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

The current product is a runnable **Counterfactual Laboratory** built around a smart-building emergency simulation. It exposes live scenario controls, counterfactual futures, adversarial perturbations, robust optimization, a dependency-free QAOA statevector simulator, CVaR-style best-tail optimization, a three-variable policy lab, and independent Guardian checks.

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

## Product surfaces

- **Counterfactual Laboratory** — branch the present into candidate futures.
- **CHAOS** — perturb declared variables and expose high-risk futures.
- **QUANTUM** — compare classical enumeration, QAOA expectation, and QAOA CVaR.
- **POLICY LAB** — inspect the exact multi-variable robust search and quadratic QAOA projection.
- **GUARDIAN** — independently verify nominal and adversarial states.
- **Benchmarking** — expose objective quality and runtime without claiming quantum advantage.

## Persistence

Supabase migrations under `backend/supabase/migrations/` provide experiment/run tables, indexes, and row-level security. `src/rift/supabase_store.py` is an optional server-side adapter.

A live Supabase project is **not** hard-coded into the repository. Configure `RIFT_SUPABASE_URL` and `RIFT_SUPABASE_KEY` only in a trusted server environment. Never expose a service-role key to the browser.

## Review and billing integrations

The connected development environment does not expose a CodeRabbit execution connector, so RIFT does not claim that CodeRabbit reviewed this release. GitHub Actions provides the repository's automated test gate.

No Lemon Squeezy account or payment integration is connected. Billing remains outside the simulation core until a provider is intentionally configured.

## Safety boundary

RIFT is a research and simulation system. It does not autonomously control real emergency infrastructure. Real deployment would require validated domain models, calibrated sensors, human oversight, formal hazard analysis, and jurisdiction-specific certification.

## Status

**v0.6.0 — Counterfactual Laboratory release candidate.**

The release candidate is intended to be demo-ready when the repository CI gate is green. Quantum hardware, hosted Supabase, CodeRabbit, and billing are optional external integrations rather than hidden dependencies.
