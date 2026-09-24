# RIFT post-submission research roadmap

v1 productization is underway on `main` (v0.6.0 tagged as the frozen
snapshot). Machine-verifiable status lives in `docs/phase-matrix.json`
(enforced by `scripts/check_phase_matrix.py` in CI); the prose below
summarizes it. Completed v1 platform work is marked ✅; the rest needs
real data and stays honestly pending.

## Data platform ✅ (built, synthetic/tested)

Canonical `Observation` (patient/timestamp/source/metric/value/unit/
quality/provenance) + strict validation + unit normalization;
FHIR R4 Observation import subset, CSV/JSON adapters; patient timeline
(multi-observation days, median estimation, reproducible day indices);
`ReplaySource` / `LiveIngestSource` / `PublicDatasetSource` share one
interface. Real device APIs remain future work.

## Twin state estimation ✅ (median layer; documented seam)

Timeline estimation (median per metric/day) is separated from replay and
from prediction, with the seam documented for future statistical models.
No validated estimator is claimed.

## Model registry + provenance ✅ (code-side; DB migration unapplied)

Versioned registry (`cardiac-strain-v1`, weights digest pin, threshold,
calibration method, status/gate), live weights-drift detection, and
deterministic prediction IDs (SHA-256 over patient/day/model/weights/
inputs) stamped on every twin snapshot. `backend/.../006_model_registry.sql`
adds registry + audit tables for a future live project.

## Decision comparison + deployment gate ✅ (built)

`decision_table` joins robust ranking with trajectory outcomes per policy
(expected/worst-case/uncertainty/feasibility side by side, same ordering
as the engine). `deployment_gate()` reports clinical-use closed with
evidence-based reasons until adequate validation exists; surfaced in
`/api/twin/evidence`. Gates constrain claims, never auto-open them.

## Guardian 2.0 + evidence bundles ✅ (built)

Staged enforcement (G-001…G-016) with severity, evidence payloads, and
WITHHOLD/WARN/ALLOW actions; versioned evidence bundles
(manifest + validation.json/md, optional HMAC signing) for every
validation claim.

The prototype is feature-frozen. Nothing below is promised or scheduled;
each phase needs what this build deliberately lacks: real data, clinical
endpoints, and prospective evaluation. Recorded here so future work has a
starting point, not a backlog of half-built features.

## Phase A — Real/public data

Replace synthetic-only evaluation with appropriately governed public or
permitted datasets. Entry points are ready: `PublicDatasetSource` accepts
any CSV following the documented schema, and `fhir_clinical` ingests
Patient/Condition/Medication/Encounter/Device resources with pagination,
auth, and retry — feeding the unchanged twin, risk, Guardian, and
evaluation layers.

Target shape: development cohort → calibration cohort → external cohort
→ temporal validation → prospective evaluation.

## Phase B — Better outcome definition

The current target ("high cardiac-strain day") is a demo physiological
criterion. Do not relabel it as a clinical event. A future version
should move: physiological deterioration → predefined clinical endpoint
→ time-to-event evaluation, chosen with (not instead of) clinical input.

## Phase C — Proper uncertainty

Current: heuristic uncertainty + jitter + coverage + calibration repair,
now joined by a drift-detection module (`drift.py`: distribution,
missingness, and source shifts with explicit thresholds) that reports —
not yet alerts. Future: measurement uncertainty + model uncertainty +
distribution shift + calibrated prediction intervals, each estimated from
data rather than constructed from weights, wired into monitoring with
alerting.

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
