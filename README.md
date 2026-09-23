# RIFT

**Robust Intervention & Future Testing**

> **Test the decision. Break the future.**

RIFT is a decision-intelligence engine for testing interventions before they are trusted. It enumerates counterfactual futures, searches adversarial failure conditions, ranks robust policies, and keeps hard safety verification outside the optimizer.

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
GUARDIAN — independent constraint verification
    ↓
ROBUST POLICY
```

The current product ships with a runnable **Counterfactual Laboratory** using a smart-building emergency scenario. v0.3 adds interactive state controls and a dependency-free QAOA statevector simulator for small QUBOs. The browser visualizes the world state, future branches, adversarial findings, policy-energy landscape, and Guardian result.

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

The server intentionally uses Python's standard library for the first product release, so the laboratory has no heavy web dependency.

## Quantum layer — deliberately honest

RIFT represents candidate decisions as a QUBO and exposes a `QuantumOptimizer` interface. The shipped baseline is exact classical enumeration, and the default quantum adapter is now a small dependency-free QAOA statevector simulator. QAOA prepares an initial superposition, alternates a QUBO-derived cost phase with an X mixer, and uses a classical parameter search. This follows the standard hybrid structure documented by IBM Quantum. citeturn0search0

RIFT does **not** claim that quantum hardware automatically evaluates every future, provides guaranteed speedup, or beats classical optimization. The research question is empirical:

> Can hybrid causal/counterfactual decision systems gain measurable value from quantum optimization on specific policy-search workloads?

When a real quantum backend is added, benchmark solution quality, wall-clock runtime, constraint violations, measurement/sample count, and noise sensitivity.

## Product surfaces

- **Counterfactual Laboratory** — branch the present into candidate futures.
- **CHAOS** — perturb declared variables and expose worst-case futures.
- **QUANTUM** — represent policy search as an energy/QUBO problem.
- **GUARDIAN** — enforce hard constraints independently.
- **Benchmarking** — compare exact enumeration and simulated QAOA without hiding failures.
- **Scenario controls** — perturb crowd, smoke, capacity, and blocked-stairwell conditions live.

## Repository

- `src/rift/` — deterministic domain engine
- `web/` — zero-dependency laboratory UI
- `backend/supabase/` — optional persistence schema with row-level security
- `docs/PRD.md` — product requirements
- `docs/architecture.md` — architecture and API direction
- `docs/agents.md` — ORACLE / CHAOS / QUANTUM / GUARDIAN contracts
- `docs/design-system.md` — visual system

## Safety boundary

RIFT is a research and simulation system. It does not autonomously control real emergency infrastructure. A real deployment would require validated domain models, calibrated sensors, human oversight, formal hazard analysis, and jurisdiction-specific certification.

## Status

**v0.3.0 — interactive QAOA laboratory prototype.**

The core engine is deterministic and testable. Supabase, real quantum hardware, billing, and automated code-review integrations are provider-ready but are not falsely represented as connected services.
