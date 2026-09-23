# RIFT — Robust Intervention & Future Testing

RIFT is a decision-intelligence engine for testing interventions across counterfactual futures, searching adversarial failures, optimizing candidate policies, and independently verifying constraints before a decision is accepted.

## Core loop

State -> World Model -> Counterfactual Futures -> CHAOS -> QUBO -> Classical/Quantum Optimizer -> GUARDIAN -> Decision

## MVP status

- Deterministic scenario engine
- Counterfactual intervention enumeration
- Adversarial failure-search primitives
- QUBO representation
- Exact classical baseline optimizer
- Explicit quantum optimizer interface (no fake quantum execution)
- Independent safety verification
- Supabase schema with row-level security
- Automated pytest workflow

## Run locally

    python -m venv .venv
    pip install -e ".[dev]"
    pytest
    python -m rift.cli demo

## Architecture

See docs/PRD.md, docs/architecture.md, docs/agents.md, and docs/design-system.md.

## Scientific position

RIFT does not assume that quantum optimization is faster or better. Quantum methods are treated as benchmarkable backends. Experiments should report solution quality, runtime, constraint violations, noise sensitivity, and reproducibility.

## Integrations

Supabase is represented by the versioned schema under backend/supabase. A hosted Supabase project is intentionally not hard-coded into the repository. Billing and code-review integrations are planned behind provider adapters so secrets never enter source control.

## License

TBD before public release.
