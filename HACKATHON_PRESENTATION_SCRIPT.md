# Hackathon Presentation Script — Quantum Computing Track
**Time Budget: 8-10 minutes presentation + 2-5 minutes demo + Q&A**

---

## Slide 1: Title (15 sec)
> **RIFT: Counterfactual Decision Intelligence with Quantum-Ready Optimization**
> 
> *Mehul Wagde — OpKnock*
> 
> *Research prototype, AGPL-3.0. Not clinical software. No quantum advantage claimed.*

---

## Slide 2: The Problem (45 sec)

> **"We make high-stakes decisions with fragile models."**
>
> - Building evacuation: "Which stairwell?" — model says A, but fire blocks it
> - Traffic corridor: "Green wave timing" — model optimized for average, fails at 5pm surge
> - Cardiac cath lab: "Stent or medicate?" — model AUC 0.85, but **recall 0.26** (misses 3/4 stenoses)
>
> **Common thread**: Models optimize point estimates. Reality is distributional, adversarial, and unforgiving.
>
> **RIFT's answer**: Generate counterfactual futures → stress-test with chaos → verify with staged safety → optimize with quantum-ready solvers.

---

## Slide 3: Architecture Overview (45 sec)

> **RIFT Core** — domain-neutral platform:
>
> 1. **Scenario/World Engine** — declarative domains (building, traffic, grid, cardiac)
> 2. **Counterfactual Engine** — "What if X changes?" ranked by impact
> 3. **CHAOS Engine** — automated adversarial perturbations (fuzzing, regression scenarios)
> 4. **Digital Twin** — state sync, risk trajectories, full provenance
> 5. **Optimization Engine** — Exact / Greedy / **QAOA / CVaR-QAOA** (our quantum hook)
> 6. **Guardian 2.0** — 16-rule staged verification (INPUT → DEPLOYMENT)
> 7. **Real-time SSE** — incident/decision lifecycle events
> 8. **Plugin SDK** — new domains in hours

> **Two reference domains** validate the architecture:
> - Smart Building Emergency (evacuation routing)
> - Traffic Optimization (corridor light timing)
>
> **Track A** proves it works for a regulated domain: Cardiovascular Digital Twin

---

## Slide 4: Quantum-Ready Optimization — The Hackathon Core (2 min)

> **Here's the quantum story — honest, tested, no hype.**
>
> **Problem**: Evacuation routing, traffic lights, grid contingencies → all map to **QUBO** (Quadratic Unconstrained Binary Optimization).
>
> **Solver Stack** (all implemented, all tested):
>
> | Solver | Use Case | Status |
> |--------|----------|--------|
> | **Exact brute-force** | ≤20 vars, ground truth | ✅ Baseline |
> | **Greedy** | Fast fallback | ✅ Baseline |
> | **QAOA Statevector** | ≤12 qubits, deterministic, **zero deps** | ✅ `qaoa.py` — runs in CI |
> | **QAOA Aer (Qiskit)** | Shot sampling, COBYLA angle opt | ✅ `qpu.py::solve_on_aer` — tested vs exact |
> | **QAOA IBM Hardware** | Real backend, SamplerV2 | ✅ `qpu.py::solve_on_ibm` — **opt-in, token-gated** |
> | **CVaR-QAOA** | Risk-aware (tail optimization) | ✅ Same backends, α=0.25 default |
>
> **Key design decisions**:
> - Qiskit is **optional extra** (`pip install rift-engine[qiskit]`) — stdlib install unaffected
> - Hardware path **never default** — explicit per-call, human credentials required
> - Statevector simulator is our **development backbone** — deterministic, fast, no queue
> - **Benchmark**: `test_aer_matches_exact_on_reference_instance` — Aer matches exact statevector on reference QUBO
>
> **No quantum advantage claimed**. This is a **software stack** ready for when hardware improves.

---

## Slide 5: Track A — Cardiovascular Digital Twin (2 min)

> **Why cardiac? Proves the platform works for regulated, high-stakes domains.**
>
> **Data**: UCI Z-Alizadeh Sani Extension — 303 real patients, 59 features, 4 angiographic targets (CAD, LAD, LCX, RCA stenosis ≥50%).
>
> **Leakage Firewall**: Cath/LAD/LCX/RCA columns **hard-coded dropped** before any model sees them. API validates all 55 predictors; 422 if forbidden column sneaks in.
>
> **Split**: 183/60/60 (seed=7, fixed forever). Test set scored **once**.
>
> **4 Models — Honest Evaluation**:
>
> | Model | Algorithm | Test AUC | Verdict |
> |-------|-----------|----------|---------|
> | `cad-v1` | LogReg | **0.978** | ✅ Strong |
> | `lad-stenosis-v1` | RandomForest | **0.857** | ✅ Strong |
> | `lcx-stenosis-v1` | RandomForest | **0.816** | ⚠️ Recall 0.259 — **"does NOT rule out"** |
> | `rca-stenosis-v1` | LogReg | **0.594** | ❌ **"NOT decision-grade"** |
>
> **We flag weak models in plain language** — not in footnotes, in the model cards the clinician sees.
>
> **Pipeline** (one command, reproducible):
> ```
> python -m rift.health.cardiovascular.pipeline
> # dataset → train → evaluate → calibrate → explain → site
> ```
>
> **Calibration**: Isotonic regression, OOF-fit on train+val, test reported once. ECE tracked before/after.
>
> **Explainability**: Permutation AUC-drop on held-out test. Top drivers per model — **explanation only, tunes nothing**.
>
> **Safety Layer**: Every `/predict` call assessed before response:
> - Refuses uncalibrated models
> - Flags OOD inputs (Mahalanobis distance)
> - Weak model warnings (LCX/RCA) surfaced in verdict
> - Plain-language disclaimer included
>
> **Verify Gate** (7 automated checks):
> ```
> python -m rift.health.cardiovascular.verify
> # Data hash, Registry, Artifacts, UI mirrors, Pages, API smoke, Bandit=0
> ```

---

## Slide 6: Live Demo — Coronary Viewer (1.5 min)

> **Let me show you the clinician interface.** *[Open coronary.html]*
>
> **What you're seeing**: Schematic coronary tree — LM, LAD (with D1/D2), LCX (with OM1/OM2), RCA (with RM). **Not anatomy — schematic**. Colors = calibrated stenosis probabilities for this patient.
>
> **[Click patient tabs]** — Different test patients from the held-out set. Each has ground-truth labels.
>
> **[Hover vessel]** — Tooltip: `P = 0.615` for LAD, "representative site (schematic)". No false precision.
>
> **[Right panel: What-if]** — *"If Typical Chest Pain were 1 (was 0) → P 0.615 → 0.823 ✓ toward truth"*. This is **permutation counterfactual** — single observed-value change, model-behavior explanation. **Not medical advice**.
>
> **[Switch to LCX patient]** — Notice P=0.312 (green) but truth = Stenotic. Model missed it. Right panel: "Stable — no single observed-value change flips this prediction." That's the **recall 0.259** problem, visible to the clinician.

---

## Slide 7: Live Demo — Evaluation Dashboard (1.5 min)

> **Now the honest evaluation — what we show the regulator.** *[Open cardio-dashboard.html]*
>
> **Metrics Table** — LCX recall 0.259 **highlighted amber**. RCA AUC 0.594 **highlighted amber**. We don't hide these.
>
> **Reliability Curves** — [Click CAD/LAD/LCX/RCA tabs]. Amber X = raw probabilities. Green dots = calibrated. Diagonal = perfect. LCX calibration **didn't help** — reported as-is.
>
> **Feature Importance** — Permutation AUC-drop, top 10 per model. "What drives LAD? Typical Chest Pain, HTN, EF-TTE..."
>
> **Model Cards** — Each has: Intended Use, Training Data, Metrics, **Limits** in plain language.
> - RCA card: *"This model is NOT decision-grade (test AUC 0.594). Do not use for clinical decisions."*
> - LCX card: *"This model does NOT rule out stenosis (recall 0.259). Negative result requires confirmatory testing."*

---

## Slide 8: The Platform Vision (45 sec)

> **RIFT Core + Domain Plugins = Decision Intelligence Platform**
>
> - **Track A** proved: regulated domain, honest eval, safety layer, plugin SDK works
> - **Power Grid** domain: N-1 contingency analysis → QUBO → QAOA
> - **Custom domains**: `DomainPlugin` SDK → manifest.json → deploy
> - **Python/TypeScript SDKs** — generated from OpenAPI, typed, versioned
>
> **Next**: 
> - Multi-agent Guardian (LLM-assisted rule authoring)
> - Federated digital twins (cross-organization state sync)
> - Hardware QAOA benchmarking on IBM Kingston/Heron

---

## Slide 9: Closing / Call to Action (30 sec)

> **Three takeaways:**
>
> 1. **Quantum-ready ≠ quantum hype** — full stack implemented, tested, hardware opt-in
> 2. **Honest evaluation > inflated metrics** — weak models flagged in the UI, not hidden
> 3. **Platform, not point solution** — same core solves evacuation, traffic, grid, cardiac
>
> **Repo**: `github.com/OpKnock/RIFT` — `bash ./local start` runs everything locally
>
> **Questions?** I'll drive the demo while you ask.

---

## Appendix: Real-Life Analogies for Judges

### "Explain QAOA to a non-quantum judge"
> "Imagine you're routing 500 people out of a burning building. Each person chooses stairwell A or B — that's a binary variable. 500 people = 2^500 combinations (impossible to brute force). QAOA prepares a quantum superposition of all routes, interferes bad ones, amplifies good ones — then measures. We simulate this exactly on classical hardware (statevector) and approximately on quantum hardware (Aer/IBM). Same math, different backend."

### "Why CVaR-QAOA?"
> "Standard QAOA minimizes *expected* energy (average case). But in evacuation, the *worst 10%* of outcomes are people dying. CVaR (Conditional Value at Risk) optimizes the tail — 'make the worst cases less bad.' Same circuit, different objective function."

### "Why schematic, not anatomical 3D?"
> "Clinicians don't need a pretty heart — they need **probabilities at decision points**. A schematic shows 'LAD: 61% stenosis' at the bifurcation where they'd place a stent. Anatomy distracts; schematic decides."

### "How is this different from [competing platform]?"
> "Three things: (1) **Counterfactuals first** — every decision shows 'what would flip it', (2) **Guardian staged verification** — 16 rules before deploy, not post-hoc audit, (3) **Quantum-ready optimization** — not a bolt-on, the solver stack is the engine."

---

## Demo Fallback Script (If Live Fails)

> **If coronary.html won't load**: "The UI is served from `stitch-ui/` via `bash ./local ui`. Let me show you the committed JSON that drives it — `data/cardiovascular/site/demo_patients.json` has 6 test patients with calibrated probabilities, ground truth, and pre-computed counterfactuals. The Three.js renderer is pure CDN — no build step."
>
> **If API 503**: "Track A artifacts aren't built. One command: `python -m rift.health.cardiovascular.pipeline` — reproduces everything from raw UCI zip. Takes ~2 minutes."
>
> **If quantum questions get too deep**: "The implementation is in `src/rift/qaoa.py` (statevector, ~100 lines) and `src/rift/qpu.py` (Aer + IBM paths). Happy to walk the code after."

---

## Your "Pocket Cards" — Print These

| Card | Content |
|------|---------|
| **Quantum Stack** | Exact → Greedy → QAOA-statevector → QAOA-Aer → QAOA-IBM \| CVaR on all |
| **Cardiac Models** | CAD 0.978 ✅ \| LAD 0.857 ✅ \| LCX 0.816 ⚠️ recall 0.259 \| RCA 0.594 ❌ |
| **Safety Layer** | Refuses: uncalibrated, OOD, weak-model. Returns: verdict + disclaimer |
| **Verify Gate** | 7 checks: hash, registry, artifacts, UI mirror, pages, API, bandit=0 |
| **One Command** | `bash ./local start` → API:8080, UI:8000, Prom:9090, Grafana:3000 |

---

## Timing Cheat Sheet

| Section | Target | Hard Stop |
|---------|--------|-----------|
| Title | 0:15 | 0:30 |
| Problem | 0:45 | 1:15 |
| Architecture | 0:45 | 2:00 |
| Quantum | 2:00 | 4:00 |
| Track A | 2:00 | 6:00 |
| Demo Coronary | 1:30 | 7:30 |
| Demo Dashboard | 1:30 | 9:00 |
| Vision | 0:45 | 9:45 |
| Close | 0:30 | 10:15 |
| **Total** | **~10:15** | **10:30** |

**If running long**: Cut Vision slide, compress Quantum to 90 sec, skip Dashboard reliability curves.