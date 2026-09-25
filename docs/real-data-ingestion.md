# Real PhysioNet Ingestion Record (executed, not claimed)

First live pull of real patient-adjacent bytes through RIFT's own pipeline,
executed 2026-09-25 against https://physionet.org (open-access CHFDB, no
credentialing required for this dataset).

## What was pulled

- Dataset: `chfdb/1.0.0`, record `chf01` (71-year-old male, NYHA class III-IV heart failure — from the record header comments).
- Signal: `ECG1`, 250 Hz, 17,994,491 samples total (~20 h). Pulled header + first 1,250 raw samples: SHA-256 `ae8bc9608fefd6f59c1ff04bb935e74e5ebbcbf28862d75531ddb4a77724bf2b`.
- Annotations: `chf01.ecg` reference beats (extensions `qrs`/`atr`/`ari` do not exist for CHFDB — verified by probing; `ecg` returns 200).

## What the pipeline produced

Window samples 0–75000 (300 s) via `wfdb.rdann('chf01', 'ecg', pn_dir='chfdb/1.0.0')`:

| Measure | Value |
|---|---|
| Beats | 333 (symbols N + V: normal + ventricular ectopic) |
| Mean RR | 901.7 ms |
| Resting HR via `rr_to_hr_hrv` | 66.5 bpm |
| HRV RMSSD via `rr_to_hr_hrv` | 39.6 ms |

## What this proves and what it does not

- Proves: the WFDB seam ingests real bytes end-to-end (header → annotations → RR → HR/HRV) with no fixture involved. Phase 2 ingestion: genuinely advanced.
- Does NOT prove: model validity (one 300 s window is not validation), generalizability, or anything clinical. CHFDB has no outcome labels for the 24 h cardiac-strain task, so it cannot validate RIFT's risk model — only its ingestion.
- Credentialed datasets (MIMIC-IV, etc.) remain gated on human identity: PhysioNet account + CITI "Data or Specimens Only Research" (free via MIT affiliation) + reference + per-dataset DUA. No automation can or should bypass that — see `docs/external-gates.md`.
