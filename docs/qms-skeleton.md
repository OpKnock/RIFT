# QMS Skeleton (ISO 13485 / IEC 62304 oriented)

Scaffolding only. An operated QMS requires appointed management, trained
staff, and audit history — none of which exist in this repo. Each section
lists the procedure to write, the record to keep, and the current RIFT
substrate that anticipates it.

## 1. Document control
- Procedure: versioned docs, approval signatures, change history.
- Substrate: git history, `docs/release-checklist.md`, version-pinned CHANGELOG.
- Missing: approval authority, controlled-distribution list.

## 2. Design controls (design input → output → verification → validation)
- Procedure: requirement per feature, trace input→output→V&V.
- Substrate: `docs/traceability-matrix.md`, 281 tests, phase-matrix discipline.
- Missing: formal design reviews with clinical sign-off.

## 3. Risk management (ISO 14971)
- Procedure: hazard analysis, risk controls, residual-risk sign-off.
- Substrate: Guardian 2.0 rules G-001…G-016 as software risk controls; hazard mapping in `docs/clinical-roadmap.md` phase 12 work.
- Missing: clinical risk assessment, benefit-risk analysis, post-market surveillance plan.

## 4. Software lifecycle (IEC 62304, Class B/C assumed until classified)
- Procedure: software safety classification, unit/integration/system testing, release records.
- Substrate: test suite, CI gates, `constraints.txt`, release checklist, model registry promotion gates.
- Missing: classification memo, SOUP (third-party software) list with anomaly tracking, release sign-off.

## 5. CAPA (corrective and preventive action)
- Procedure: issue intake, root cause, action, effectiveness check.
- Substrate: GitHub issues, regression-test policy (`tests/test_internal_audit_regression.py` pattern).
- Missing: operated CAPA log, effectiveness reviews.

## 6. Complaints and post-market surveillance
- Procedure: complaint intake, vigilance reporting, trend analysis.
- Substrate: none (no marketed device).
- Missing: everything; blocked on deployment.

## 7. Supplier control
- Procedure: qualify critical suppliers (cloud, QPU vendor, data pipelines).
- Substrate: `constraints.txt` pins, SBOM-capable lockfiles.
- Missing: supplier agreements, qualification records.

## 8. Records and retention
- Procedure: retention schedule per jurisdiction.
- Substrate: evidence bundles (versioned, HMAC-signed) — technical format only.
- Missing: legal retention mapping, archive controls.
