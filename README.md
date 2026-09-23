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

The current product ships with a runnable **Counterfactual Laboratory** using a smart-building emergency scenario. v0.5 adds interactive state controls and a dependency-free QAOA statevector simulator for small QUBOs. The browser visualizes the world state, future branches, adversarial findings, policy-energy landscape, and Guardian result.

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


## Robust-QAOA phase
RIFT now constructs an adversarial robust QUBO from the declared perturbation set, then solves that same objective with exact classical enumeration and the dependency-free QAOA statevector simulator. The comparison reports whether both methods reach the same binary policy and objective. This is a benchmark workflow, not a claim of quantum advantage.

The robust QUBO is exact for the current two-variable emergency-routing formulation. Higher-dimensional robust objectives require a higher-order binary optimization representation or a deliberate approximation, rather than silently fitting a quadratic model.

## v0.6 risk-tail optimization
The QAOA simulator now supports a CVaR objective in addition to the standard expected-energy objective. CVaR focuses optimization on the lower-cost tail of sampled solutions for minimization, allowing RIFT to compare expectation-QAOA and risk-tail QAOA on the same robust QUBO. IBM's current QAOA documentation describes CVaR as an advanced cost-function technique for emphasizing the best portion of measured samples; RIFT uses the same conceptual risk-tail objective in its dependency-free simulator. This is an experimental comparison, not evidence of quantum advantage.

## Production integrations
- **Supabase:** migration-backed persistence and RLS policies are included. A live project is intentionally not hard-coded; configure `RIFT_SUPABASE_URL` and `RIFT_SUPABASE_KEY` to enable the optional adapter.
- **Code review:** this repository includes CI tests and a review-oriented configuration placeholder; the connected ChatGPT environment does not expose a CodeRabbit execution connector, so no CodeRabbit run is claimed.
- **Billing:** payment-provider secrets are not used by the engine. Billing remains an adapter boundary until a provider is explicitly connected.

## Multi-variable policy laboratory
RIFT now evaluates three binary controls in the emergency scenario (8 policies) using exact robust enumeration. For larger policy spaces, RIFT can construct a transparent quadratic projection and send that approximation to QAOA. The UI labels this projection as approximate; the exact enumerator remains the reference result.
