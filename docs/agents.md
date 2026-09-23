# RIFT Agent Model

## ORACLE — World Model
Generates plausible future transitions from the current state and declared transition model. It describes possibilities; it does not approve actions.

## CHAOS — Adversarial Search
Searches declared perturbation space for plausible conditions where a candidate policy performs badly. It cannot mutate variables outside the scenario's allowed perturbation set.

## QUANTUM — Optimization Adapter
Solves a QUBO using a configured optimizer. The result must identify whether it was exact, heuristic, simulated quantum, or hardware-backed. The MVP intentionally has no fake quantum implementation.

## GUARDIAN — Safety Verifier
Independently evaluates hard constraints and returns machine-readable violations. An optimizer cannot override it.

## Orchestration
The MVP uses deterministic Python orchestration. These contracts can later become asynchronous workers without changing the domain semantics.
