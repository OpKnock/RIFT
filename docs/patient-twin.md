# Patient Digital Twin (healthcare demo)

Human-in-the-loop **decision support only**. Synthetic demo data. Nothing
here is clinically validated, and nothing acts autonomously.

## The distinction

Normal ML: EHR + wearable → risk score.

RIFT: EHR + wearable → personalized patient state → synchronized digital
twin → **FORESIGHT** future trajectories → counterfactuals →
robustness/uncertainty → Guardian → clinician dashboard.

```
EHR ──normalize──┐
                 ├─→ PatientState(t) ──→ twin.sync ──→ baseline(<t) ──→ deviations
wearable ─replay─┘          │                  │              │
  (ReplaySource /           │                  ▼              ▼
   LiveIngestSource)        │           24h strain risk ──→ contributions
                            │                  │
                            │                  ├─→ FORESIGHT: 4 policies ──→ futures
                            │                  │                    ├─→ 3-day trajectories
                            │                  │                    └─→ robust ranking (perturbations)
                            │                  │
                            │                  ├─→ uncertainty = quality-base + spread/2
                            │                  │
                            │                  └─→ Guardian (reject vs flag) ──→ reasons
                            │
                            └─→ snapshot → history (replayable) → dashboard
```


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

## Forecasting hygiene (no baseline leakage)

The baseline for day `t` uses only observations with `day_index < t`, so an
abnormal today can never redefine today's "normal". Day 0 has an empty
baseline (cold start); missing values then fall back through
baseline → EHR clinic value → documented cold-start anchors, every fallback
reported in `imputed_fields`.

## Data sources

`twin` accepts any `WearableSource`: `ReplaySource` (this demo's fixed
14-day series) or `LiveIngestSource` (append-only, rejects duplicates and
time-travel). A future live IoT adapter implements the same interface —
no twin/risk/Guardian changes needed.

## Validation vs clinical validation

`tests/test_health_*.py` validate software behavior (normalization,
replay, baselines, bounds, determinism, Guardian rejection, endpoint
contract, spell-vs-calm selectivity). They do **not** validate medicine.

Measured backtest on the synthetic series (days 7–12, `evaluate.backtest`):
1-day-ahead MAE — resting HR 4.98 bpm, HRV 7.71 ms, sleep 1.17 h, activity
16.57; event agreement 4/6 (sensitivity 0.0, specificity 0.8 — the spell
onset lags prediction by one day, visible per-day in the report, not
averaged away); Brier 0.145; interval coverage 0.50. These are regression
bounds for pipeline self-consistency on synthetic data, not clinical
performance. Risk intervals are explicitly labeled `demo / not calibrated`
in the API payload and the dashboard.

## Phase-4 evidence (independent outcomes, held-out timeline)

Phase-3 labels were circular (observed vitals scored by the same risk
function). Phase 4 replaces them with outcome definition v1
(`evaluate.OUTCOME_RULE`): an event is **observed** resting HR ≥ 75 **and**
(sleep ≤ 5.5 h **or** HRV ≤ 35 ms) — no model weights, no baselines. The
model can now genuinely miss, and it does.

60-day series, calibration days 0–29, held-out days 30–59
(`GET /api/twin/evidence`): event agreement 0.87, sensitivity 0.33,
specificity 0.93, Brier 0.120, interval coverage 0.87, onset lags
`[-99,-99,0]` (−99 = realized event with no prediction within ±2 days).
Sensor-noise stress (0/5/15%): agreement stays ≥ 0.87 with no crashes;
mean uncertainty now rises with noise (0.085 → 0.09 → 0.11) via the
jitter path below. Public datasets plug in through
`PublicDatasetSource` (strict CSV schema, same normalized pipeline).

## Phase-7 external validation (separate synthetic series, no refit)

`evaluate.external_validation` replays an independent 60-day series
(seed 123, different spell days 15–16/33–34/50 — never used for model
development, calibration fitting, threshold selection, or reporting) with
the model, threshold, and Platt params all frozen. Measured:
agreement 0.90 (95% CI 0.80–0.95), sensitivity 0.40, specificity 0.94,
Brier raw 0.119 → calibrated 0.078, ECE raw 0.225 → calibrated 0.009,
coverage 0.90. Slope/intercept correctly refused (1 populated bin —
reported with warning, not hidden). This is synthetic-to-synthetic
generalization evidence, NOT external real-world validation: a real
public dataset through `PublicDatasetSource` remains the next credibility
jump, and the seam is ready for it.

## Sample adequacy (why Item 8 stays strong partial)

External validation reports a `sample_adequacy` verdict against a
CONSERVATIVE bar — ≥100 events and ≥100 non-events — not a scientific law:
required size truly depends on precision targets, event prevalence,
expected calibration, and risk distribution, and published guidance notes
substantially more is sometimes needed. The current external series
(5 events, 54 non-events) verdicts `limited`, and the dashboard shows it
next to the metrics. Good point estimates at n=59 do not upgrade the
claim: calibration evidence remains limited until the predefined
conservative sample-adequacy bar is met, and larger samples may be
required depending on the precision target and validation context.
Meeting the bar is necessary but not sufficient — representativeness,
context, and fit-for-purpose judgment still apply. The bar itself is
pinned by regression tests.

## Sensitivity and thresholds (reported, not gamed)

Held-out threshold sweep (threshold → sensitivity / specificity):
0.40 → 0.33 / 0.93 · 0.50 → 0.33 / 0.93 · 0.60 → 0.33 / 0.93 ·
0.70 → 0.33 / 0.96 · 0.80 → 0.00 / 1.00.
Lowering the threshold cannot rescue detection — the misses are sudden
onset shocks the 1-day model cannot foresee, not threshold artifacts. The
operating point stays 0.60; this table exists so the tradeoff is explicit.
A bounded velocity term (rising HR / shrinking sleep, capped, deterioration
only) lifts onsets without hurting specificity; trajectory rollout stays
level-only and says so.

## Reliability (empirical, still uncalibrated)

`evaluate.reliability` bins held-out predicted risks and compares against
realized frequencies: ECE 0.22 (mid bin overconfident 0.28 vs 0.07, high
bin 0.71 vs 0.33 on n=3). The probabilities are therefore NOT calibrated —
the dashboard says so, and this number is the receipt.

## Calibration repair (Platt, fit/test split, operating point untouched)

`evaluate.calibration_report` fits p_cal = sigmoid(A·p + B) on calibration
days 30–44 only (grid search, A ≥ 0 so the map can never invert risk
ordering) and scores untouched test days 45–59: ECE 0.198 → 0.058, Brier
0.116 → 0.119. The fit chose a near-constant map — i.e. the data supports
"predict near base rate" more than the raw spread — which is itself an
honest finding about a 15-day fit window. The event threshold and all
model weights stay fixed; calibrated probabilities are reported
alongside, never swapped in silently. Small-sample caveat applies
throughout.

## Measurement jitter → uncertainty

Day-over-day jumps are compared against typical fluctuation (MAD): only
the excess counts, so ordinary wobble scores near 0 while shocks and
sensor noise score toward 1 and widen the interval (`JITTER_WEIGHT`).
Calm demo days measure 0.04–0.28. The dashboard stress table shows noise
level, agreement, and uncertainty side by side, and states explicitly
whether uncertainty responded.

## Demo target (narrow, short-horizon)

**Next-24h high-strain day** (risk ≥ 0.60) for demo-patient-01 (58, M,
hypertension + hyperlipidemia). The 14-day synthetic series is calm, spikes
on days 9–10 (poor sleep + exertion), and recovers — the event fires on
days 9–10 (velocity term catches the onset day). Weights in
`risk.py`/`transition.py` are transparent demo constants.

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

