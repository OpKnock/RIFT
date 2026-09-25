# External Gates:_exact steps, verified links, no automation possible

Every item below requires a human, an institution, or hardware. Links were
verified live on 2026-09-25. If a link rots, the step description (not just
the URL) is the source of truth.

## 1. Quantum hardware (Phase 11)

- IBM Quantum Open Plan: free, 10 minutes of QPU time per 28-day rolling window, includes Heron (`ibm_kingston`). Researchers logging 20 min / 12 months can opt into a one-time 180-minute promotion.
  - Platform: https://quantum.cloud.ibm.com/
  - Plans: https://quantum.cloud.ibm.com/docs/en/guides/plans-overview
  - Start: `pip install qiskit-ibm-runtime`, create API key on the dashboard, `QiskitRuntimeService.save_account(token="<44-char-key>")`.
  - Hello world: https://quantum.cloud.ibm.com/docs/en/guides/hello-world
- RIFT side: `solve_on_ibm(qubo, backend_name)` in `src/rift/qpu.py` is implemented and fail-closed; set `RIFT_QPU_TOKEN` and name an operational backend from the dashboard. First run + full-benchmark comparison remain the missing evidence.

## 2. Credentialed clinical data (Phases 3, 4, 16)

- PhysioNet credentialing (required for MIMIC-IV et al.): account at https://physionet.org/ → Credentialing page → CITI "Data or Specimens Only Research" (free via "Massachusetts Institute of Technology Affiliates", upload the training *report*) → supervisor reference for students/postdocs → per-dataset Data Use Agreement. Processing takes ~1–2 weeks. Details: https://physionet.org/about/citi-course/ and https://mimic.mit.edu/docs/faq/how-to-get-access.html
- License terms (no re-identification, no sharing, research-only, keep training current): https://www.physionet.org/about/licenses/physionet-credentialed-health-data-license-150/
- Open datasets (CHFDB etc.) need none of this — see `docs/real-data-ingestion.md` for the executed pull.

## 3. Regulatory (Phase 17)

- FDA Q-Submission program (Pre-Sub: voluntary, no user fee, written feedback ± meeting, ~75–90 days, limit 3–4 substantial topics): https://www.fda.gov/regulatory-information/search-fda-guidance-documents/requests-feedback-and-meetings-medical-device-submissions-q-submission-program
- Device software documentation (Basic vs Enhanced levels; keyword: risk of death/serious injury → Enhanced): "Content of Premarket Submissions for Device Software Functions" (FDA CDRH).
- Classification questions go through the 513(g) process, not Pre-Sub. Study-risk determinations (IDE need) are their own Q-Sub type.
- RIFT's honest starting position: research prototype, no submission, no predicate, no classification — the Pre-Sub package (intended use, device description, protocol synopsis, focused questions) is the first artifact, and it needs a regulatory professional to write it.

## 4. Operated production (Phases 19–22)

- PagerDuty/on-call, pen test vendor, backup storage, TLS certs, log aggregator: all procurement + humans. RIFT provides the substrates (auth, HMAC, RLS, rate limits, metrics, SLO targets, runbook template in `docs/incident-runbook.md`).
