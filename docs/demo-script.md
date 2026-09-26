# RIFT 5-minute demo script

For judges, reviewers, or new engineers. Everything below is reproducible:
same commands, same numbers, every run.

## 0. Setup (1 min)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate — macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]" -c constraints.txt
pytest -q   # 278 passed, 1 skipped on the release commit
```

## 1. Terminal twin story (1 min)

```bash
python -m rift.cli twin-demo
```

You will see the 14-day arc: calm → risk rising → EVENT days 9–10 →
recovery, each line with input quality and the Guardian verdict, then the
14-day backtest summary. Say out loud: "synthetic demo data, decision
support only — the point is the pipeline, not the predictions."

## 2. Doctor dashboard (2 min)

```bash
python -m rift.cli serve
# open http://127.0.0.1:8080
```

Walk top to bottom, one sentence each:
1. **Patient + twin state** — EHR snapshot and today's synchronized vitals.
2. **Baseline deviations** — current vs the patient's own history, never population norms.
3. **FORESIGHT trajectories** — the centerpiece: 4 policies, 3-day risk paths, threshold line.
4. **What-if** — change the policy selector; the highlighted path changes because the same transition model re-runs.
5. **Why** — reason sentences: contributors, baseline gaps, EHR factors, quality.
6. **Robustness + Guardian** — spread under sensor variation; DISPLAYABLE vs WITHHELD.
7. **Evidence** — agreement/Brier/coverage, Platt repair with the A=0 caveat shown, external block with the `limited` adequacy verdict.

Land the message: "It explores futures, stress-tests them, quantifies
uncertainty, calibrates, evaluates itself on untouched data — and refuses
to overclaim when evidence is thin."

## 3. Raw JSON (30 s, for the technical judge)

```bash
curl "http://127.0.0.1:8080/api/twin/demo?t=10"
curl "http://127.0.0.1:8080/api/twin/evidence"
```

Point at: `imputed_fields`, `guardian`, `calibration_repair.params`,
`external_validation.recalibrated: false`, `sample_adequacy.verdict`.

## 4. If asked…

- "Is it clinically validated?" → "No. Synthetic weights, synthetic data. The validation story is software self-consistency + honest uncertainty, documented in `docs/patient-twin.md`."
- "Why is sensitivity 0.33?" → "Sudden-onset shocks; the threshold table in Evidence proves it's structural, not tuning. That's the next research step with real data."
- "Where does it run in production?" → "Nowhere yet — needs a Supabase project, Lemon Squeezy account, and host. The code paths are ready; `docs/deployment.md` lists the exact env vars."
- "Why does the demo say day 9–10 but the backtest differs?" → "Different measurements on purpose: the replay narrative shows the velocity signal firing on onset days 9–10, while the backtest pairs each day-t prediction against the independent day-(t+1) outcome. Model behavior vs evaluation methodology — keep them distinct."

## 5. Demo backup plan (if anything live fails)

Everything below works with zero network beyond localhost, and the
terminal path needs no server at all:

1. Server won't start → `python -m rift.cli twin-demo` (full twin story in terminal) + `pytest -q` (278 passed, 1 skipped) + `docs/evidence-sheet.md` (frozen numbers).
2. Dashboard won't load → same as above, plus `curl` the two JSON endpoints if the server runs but the browser fails.
3. Judge wants proof without running anything → `docs/evidence-sheet.md` (one page) + CI badge history on GitHub (test + validate + security green on HEAD).
4. Record a screen capture of sections 1–2 beforehand; the numbers are deterministic (seeded), so the recording always matches live output.
