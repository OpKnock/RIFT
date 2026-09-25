# Study Protocol Template (silent prospective → clinical validation)

Fill every `[BRACKET]` before enrollment. No silent run starts with blanks.
Statistical analysis plan (SAP) must be locked before first prediction;
any change after lock is a protocol amendment with version + reason.

## 1. Intended use
- Target population: `[e.g., hospitalized adults ≥18 on telemetry step-down]`
- Prediction task: `[e.g., 24h cardiac-strain risk at 06:00 daily]`
- Decision supported: `[e.g., escalation review priority — support only]`
- Explicit non-uses: `[no autonomous action, no discharge decisions, …]`

## 2. Endpoints
- Primary: `[definition, adjudication, time window]`
- Secondary: `[calibration-in-the-large, AUROC by subgroup, abstention rate, …]`
- Safety: `[withhold rate, alert burden, override rate, harm review trigger]`

## 3. Sample size
- Target N: `[ ]`, basis: `[precision of calibration slope ±x / subgroup minimums]`
- Interim looks: `[count, alpha-spending rule, stopping criteria]`

## 4. Data
- Sources: `[EHR export spec, device stream spec]`
- Eligibility/exclusions: `[ ]`
- Missing-data plan: `[adequacy gate 100/100 applies; below → withhold, logged]`
- Leakage controls: `[baseline windows strictly historical; patient-level splits]`

## 5. Model lock
- Registry version: `[e.g., risk-model vX.Y approved-for-study]`
- Guardian rule versions: `[G-001 v.. … G-016 v..]`
- Weights source: `[fitted on TRAIN cohort v.., never on validation]`
- Weight-freeze date: `[ ]`

## 6. Silent phase
- Duration: `[ ]`
- Comparison: locked model predictions vs standard care, no display
- Prospective locks via `health/prospective.py` on durable ledger (in-memory store is demo-only — replace before use)

## 7. Analysis
- Pre-registered metrics: `[ ]`
- Subgroup plan: `[age band, sex, comorbidity, device type — minimum N each]`
- Abstention analysis: withhold rate, withhold-outcome association, harm review

## 8. Oversight
- IRB: `[protocol #, approval date]`
- Data use: `[DUA reference]`
- Safety board: `[members, review cadence, stopping authority]`
- Clinical owner per Guardian rule: see `docs/clinical-roadmap.md` phase 12

## 9. Publication
- Report per TRIPOD-AI; publish negative results; limitations section mandatory.
