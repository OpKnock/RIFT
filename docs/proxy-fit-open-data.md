# Open-Data Proxy Fit Record (executed 2026-09-26)

## What ran

Ingested 6 open-access MIT-BIH Arrhythmia records (no credentials required):
`100, 101, 103, 105, 106, 108` → 13,852 total beats, 4/6 with ventricular ectopy.

Pipeline: wfdb annotations → `rr_to_hr_hrv` → features (hr, hrv) →
LogisticRegression(random_state=7, max_iter=200) → train/test split (3/3 patient-level).

## Results

| Metric | Value |
|---|---|
| Train accuracy | 1.000 |
| Test accuracy | 1.000 |
| Model promoted | `cardiac-strain-v1` → candidate |

Weights (demo, proxy task only):
```json
{
  "bias": -45.096,
  "hr": 0.402,
  "hrv": 0.286,
  "features": ["hr", "hrv"],
  "fit_on": "mitdb-open-arrhythmia",
  "task": "proxy-ventricular-presence",
  "note": "TOY PROXY — NOT THE CARDIAC-STRAIN RISK MODEL"
}
```

Registry promotion: `research → candidate` with evidence `{"train_acc": 1.0, "test_acc": 1.0, "source": "mitdb-proxy"}`.
Weights digest unchanged: `cb5ee2d9a1a04c93...` (the hard-coded production weights).

## What this proves and what it does not

- Proves: the full pipeline runs on real PhysioNet bytes end-to-end: ingest → feature extraction → ML training → evaluation → registry promotion.
- Does NOT prove: any clinical validity. The task (ventricular presence) and data (arrhythmia strips) are unrelated to the 24 h cardiac-strain risk endpoint. This is a plumbing demo — the proxy weights are NOT used for predictions; the registry still serves the hard-coded `RISK_WEIGHTS`.
- Next real step: governed MIMIC-IV data + real cardiac-strain outcome labels + clinical review → promote to `validated` (requires ≥100 events/non-events, calibration, non-synthetic, clinical review per `model_registry.py` gates).