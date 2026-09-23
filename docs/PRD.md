 # Product Requirements Document

## Product
RIFT — Robust Intervention & Future Testing.

RIFT lets a decision-maker test an intervention against plausible futures and adversarial failures before committing to it.

## Problem
Most decision systems optimize for an expected outcome or a single trajectory. RIFT treats a decision as an experiment: define state, generate counterfactuals, attack candidate policies, optimize, then independently verify constraints.

## MVP requirements
- Validated scenario definitions
- Deterministic simulation with seeds
- Counterfactual intervention generation
- Adversarial future search (CHAOS)
- QUBO construction
- Exact classical baseline
- Pluggable quantum optimizer interface
- Independent safety verification (GUARDIAN)
- Reproducible experiment records
- Supabase-ready persistence

## Success metrics
Constraint violations, worst-case objective, mean objective, robustness gap, runtime, futures explored, verification rejection rate, and classical/alternate optimizer agreement on small benchmarks.

## Explicit non-goals
No autonomous real-world control, no quantum-supremacy claims, no perfect future prediction.

## Roadmap
Core engine → experiment API → Counterfactual Laboratory → QAOA/hardware adapters → benchmark suite → auth/usage/billing → domain adapters.
