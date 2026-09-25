# RIFT — one-page technical evidence sheet

RIFT — a research-grade patient Digital Twin prototype that explores future
trajectories, evaluates counterfactuals, stress-tests robustness, and
applies an independent safety layer before presenting decision-support
evidence.

Not clinically validated. Designed as a reproducible research prototype.

## System

Patient Digital Twin + FORESIGHT future-trajectory and counterfactual
reasoning + CHAOS robustness + Guardian display-safety + evidence contract.

## Data

Synthetic EHR + 14-day replayable wearable stream (dashboard/demo),
60-day development/held-out series, independent 60-day external series,
strict-schema CSV adapter (`PublicDatasetSource`) ready for public data.
No real patient data anywhere in this build.

## Core capabilities (all implemented, all tested)

Dynamic patient state · future trajectories · counterfactual analysis ·
robustness testing · Guardian safety checks · uncertainty + jitter
propagation · Platt repair with split discipline · no-refit external
validation · threshold tradeoff analysis · sample-adequacy gate.

## What it is

EHR + replayable wearable stream → synchronized patient state → personal
baselines → 24h cardiac-strain risk → FORESIGHT futures/trajectories →
robustness/uncertainty → Guardian display-safety → clinician dashboard.

## Frozen evidence (synthetic; commit-pinned, CI-green)

| Check | Result |
|---|---|
| Tests | 211 passing (current HEAD; frozen metric snapshot below predates test growth) |
| Static analysis (Bandit) | 0 issues |
| 14-day backtest agreement / sens / spec | 0.67 / 0.50 / 0.75 |
| Held-out (30d) agreement / sens / spec | 0.87 / 0.33 / 0.93 |
| Brier (held-out) | 0.120 |
| Brier test-window raw → Platt-repaired | 0.116 → 0.119 |
| ECE test-window raw → Platt-repaired | 0.198 → 0.058 |
| Interval coverage (held-out) | 0.87 |
| External series agreement (59d, no refit) | 0.90 [0.80–0.95], sens 0.40, spec 0.94 |
| External Brier raw → repaired | 0.119 → 0.078 |
| External ECE raw → repaired | 0.225 → 0.009 |
| Calibration slope | refused (1 populated bin — reported, not hidden) |
| Sample adequacy | `limited` (5 events / 54 non-events vs 100/100 bar) |
| Noise stress (0/5/15%) | agreement ≥ 0.87, uncertainty rises |

## Standing limitations (displayed in-product, not footnotes)

- Sensitivity 0.33: sudden-onset shocks; threshold table proves structural, not tunable.
- Probabilities uncalibrated for deployment (ECE repaired on split data only).
- Synthetic weights, synthetic series, synthetic outcome rule — no clinical validity.
- No live Supabase / billing / deployment credentials in this build.

## Reproduce in 2 minutes

```bash
pip install -e ".[dev]" && pytest -q && python -m rift.cli twin-demo
python -m rift.cli serve  # http://127.0.0.1:8080 ; /api/twin/evidence
```

## Repository

OpKnock/RIFT — feature-frozen research prototype. Remaining upgrades need
independent event volume / real-world data, not more code.
