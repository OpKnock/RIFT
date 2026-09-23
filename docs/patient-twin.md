# Patient Digital Twin (healthcare demo)

Human-in-the-loop **decision support only**. Synthetic demo data. Nothing
here is clinically validated, and nothing acts autonomously.

## The distinction

Normal ML: EHR + wearable → risk score.

RIFT: EHR + wearable → personalized patient state → synchronized digital
twin → **FORESIGHT** future trajectories → counterfactuals →
robustness/uncertainty → Guardian → clinician dashboard.

## Pipeline

```
EHR (normalize) ─┐
                 ├→ PatientState → twin.sync(day) → baseline (personal medians)
wearable stream ─┘                                    ↓ deviations from baseline
                                                      ↓
                         24h cardiac-strain risk + contributions + quality + uncertainty
                                                      ↓
                         FORESIGHT: 4 intervention policies → counterfactual futures
                                    → 3-day trajectory rollout per policy
                                    → robustness ranking under sensor/parameter variation
                                                      ↓
                         Guardian display-safety verdict (REJECT vs FLAG vs clear)
                                                      ↓
                         doctor dashboard + reasons ("why did risk change?")
```

New observations update the twin: call `twin.update(day)` (or replay a
range); baselines, risk, futures, and Guardian are all recomputed.

## Demo target (narrow, short-horizon)

**Next-24h high-strain day** (risk ≥ 0.60) for demo-patient-01 (58, M,
hypertension + hyperlipidemia). The 14-day synthetic series is calm, spikes
on days 9–10 (poor sleep + exertion), and recovers — the event fires on day
10 only. Weights in `risk.py`/`transition.py` are transparent demo constants.

## Module map (`src/rift/health/`)

| Module | Role | Reuses |
|---|---|---|
| `models.py` | EHRRecord, WearableObservation, PatientState, baselines, deviations | — |
| `ehr.py` | schema + normalization, demo fixture | — |
| `wearable.py` | replayable stream, staleness/completeness | — |
| `baseline.py` | personal medians, deviations | — |
| `transition.py` | bounded next-day vitals, binary policies | — |
| `risk.py` | 24h strain risk + contributions + quality | — |
| `twin.py` | DigitalTwin sync/update/replay/history | all above |
| `foresight.py` | Scenario adapter, futures, trajectories, health causal graph | `counterfactual`, `robust`, `verifier`, `causal`, `models` |
| `robustness.py` | dropout/stale/noise degradations, spread uncertainty | `robust`, `adversarial` semantics |
| `guardian.py` | display-safety verdict (reject vs flag) | `verifier` philosophy |
| `explain.py` | reason sentences per prediction | — |
| `demo_data.py` | seeded 14-day series (seed 42) | — |

Generic engines (`optimizer`, QUBO, QAOA, experiment runner, persistence,
auth) are untouched and remain available; quantum stays an optional
experimental backend, never the healthcare claim.

## Demo

```bash
python -m rift.cli serve
# open http://127.0.0.1:8080  (doctor dashboard)
# raw JSON: curl "http://127.0.0.1:8080/api/twin/demo?t=10"
```

Replay `t=0..13`; change the what-if selector to compare policies.
The `/api/demo` emergency lab endpoint still exists unchanged.

## Validation vs clinical validation

`tests/test_health_*.py` validate software behavior (normalization,
replay, baselines, bounds, determinism, Guardian rejection, endpoint
contract, spell-vs-calm selectivity). They do **not** validate medicine.
