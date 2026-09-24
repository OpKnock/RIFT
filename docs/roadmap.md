# RIFT post-submission research roadmap

The prototype is feature-frozen. Nothing below is promised or scheduled;
each phase needs what this build deliberately lacks: real data, clinical
endpoints, and prospective evaluation. Recorded here so future work has a
starting point, not a backlog of half-built features.

## Phase A — Real/public data

Replace synthetic-only evaluation with appropriately governed public or
permitted datasets. Entry point is ready: `PublicDatasetSource` accepts
any CSV following the documented schema, feeding the unchanged twin,
risk, Guardian, and evaluation layers.

Target shape: development cohort → calibration cohort → external cohort
→ temporal validation → prospective evaluation.

## Phase B — Better outcome definition

The current target ("high cardiac-strain day") is a demo physiological
criterion. Do not relabel it as a clinical event. A future version
should move: physiological deterioration → predefined clinical endpoint
→ time-to-event evaluation, chosen with (not instead of) clinical input.

## Phase C — Proper uncertainty

Current: heuristic uncertainty + jitter + coverage + calibration repair.
Future: measurement uncertainty + model uncertainty + distribution shift
+ calibrated prediction intervals, each estimated from data rather than
constructed from weights.

## Phase D — Strong external validation

More independent patients + more events + genuinely different data
source/population — designed around the precision required for the
intended performance estimates (see `sample_adequacy`), not around
hitting an event count. This is the single biggest scientific upgrade
available and the only legitimate path to upgrading Item 8.

## Phase E — Decision validation

Prediction ("what will happen?") is not decision support ("what happens
if we choose A vs B?"). RIFT's counterfactual/robustness architecture is
built for the second question; validating it requires decision-aware
evaluation designs, a deeper research direction in its own right.

## Explicitly out of scope

LLM chatbot, AI doctor persona, Bluetooth hardware, more diseases,
extra dashboards, speculative quantum features, blockchain, animations,
AI-generated medical recommendations, fake deployments, clinical-accuracy
claims. These add surface without addressing the evidence gap.
