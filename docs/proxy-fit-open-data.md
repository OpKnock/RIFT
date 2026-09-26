# Open-Data Ingestion & Proxy Fit Record (executed 2026-09-26)

## What ran

**1. Open PhysioNet datasets ingested (no credentials required):**

| Dataset | Records | Beats | Description |
|---|---|---|---|
| CHFDB | 1 (chf01) | 333 | Heart failure, 71M NYHA III-IV |
| MIT-BIH Arrhythmia | 6 (100,101,103,105,106,108) | 13,852 | Arrhythmia strips |
| NSRDB | 5 (16265,16272,16273,16420,16483) | 495,195 | Normal sinus rhythm |
| FANTASIA | 8 (f1o01, f1o02, f1y01, f1y02, f2o01, f2o02, f2y01, f2y02) | 58,028 | Young/elderly normals |
| EDB | 5 (e0103-e0107) | 36,321 | European ST-T database |
| LTAFDB | 5 (00,01,03,05,06) | 500,014 | Long-term AF |
| QTDB | 3 (sel100,sel102,sel103) | 3,271 | QT database |
| **Total** | **33 records** | **1,111,079 beats** | **8 open datasets** |

All through `wfdb` → `rr_to_hr_hrv` → (HR, HRV) features.

**2. Proxy ML pipeline executed (MIT-BIH only):**

Pipeline: wfdb annotations → `rr_to_hr_hrv` → features (hr, hrv) →
LogisticRegression(random_state=7, max_iter=200) → train/test split (3/3 patient-level).

Task: predict 'has_ventricular' (vburden > 0) from (hr, hrv).

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