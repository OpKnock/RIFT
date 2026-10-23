# RIFT Hackathon Cheatsheet — Know It Cold

## One-Liner Elevator Pitch
> **RIFT** is a counterfactual decision-intelligence platform with a **quantum-ready optimization layer** (QAOA/CVaR-QAOA on statevector + Aer + IBM hardware path). The reference domain is smart-building evacuation; Track A adds a **cardiovascular digital twin** (4 calibrated stenosis models on real UCI data) with honest evaluation (weak models flagged, not hidden).

---

## Architecture (2-Minute Mental Map)

```
RIFT Core (src/rift/)
├── api.py                    # HTTP server, route table, identity gate
├── optimizer.py              # QUBO, exact brute-force, greedy baseline
├── qaoa.py                   # 🔑 Statevector QAOA simulator (≤12 qubits, no deps)
├── qpu.py                    # 🔑 AerSimulator + IBM hardware path (optional extra)
├── cvar.py                   # CVaR risk-aware objective
├── guardian_core.py          # 16-rule staged safety (INPUT→DEPLOYMENT)
├── realtime.py               # SSE event stream (no WebSocket upgrade)
├── performance.py            # Parallel, caching, job queues
├── domains/
│   ├── powergrid/            # Grid stability contingency analysis
│   └── traffic/              # Urban corridor light timing
├── health/
│   └── cardiovascular/       # 🔑 TRACK A — 4 models, pipeline, safety, verify
│       ├── pipeline.py       # dataset→train→eval→calibrate→explain→site
│       ├── safety.py         # Refuses uncalibrated, flags weak/OOD
│       ├── verify.py         # 7 automated gates (GREEN = ship)
│       └── routes_cardio.py  # /api/cardio/* endpoints
├── operations/               # Incidents, decisions, monitoring
├── developer/                # Plugin SDK, Python/TS SDKs, docs
└── routes/                   # All API route handlers
```

**Key Principle**: Everything is **fail-closed** (no wildcard CORS, no silent failures, 422 on leakage, 503 not-ready until artifacts exist).

---

## Quantum Story — The Hackathon Hook

### What You Have (Real, Running, Tested)
| Component | File | What It Does |
|-----------|------|--------------|
| **Statevector QAOA** | `qaoa.py` | Deterministic coordinate-search on exact statevector (≤12 vars). No Qiskit required. Runs in CI. |
| **Aer QAOA** | `qpu.py::solve_on_aer()` | Real Qiskit SDK: COBYLA angle opt → AerSimulator shot sampling. 1024 shots, deterministic seed. |
| **IBM Hardware Path** | `qpu.py::solve_on_ibm()` | Fully implemented: local angle opt → transpile for backend → SamplerV2. **Requires `RIFT_QPU_TOKEN`**. Human-only first run (external gate). |
| **CVaR-QAOA** | `cvar.py` + `qaoa.py` | Risk-aware objective (α=0.25 default). Optimizes tail of distribution, not just mean. |
| **Benchmark Harness** | `tests/test_qpu_aer.py` | `test_aer_matches_exact_on_reference_instance` — Aer matches exact statevector on a reference QUBO. |

### What You **Don't** Claim (Judges Will Ask)
- ❌ No quantum advantage demonstrated
- ❌ No hardware runs in CI (token required)
- ❌ Simulator only for ≤12 qubits (statevector exponential)
- ✅ "Quantum-ready" = the software stack exists and is tested; hardware is opt-in per-call

### One Slide: Quantum Pipeline
```
Problem (domain) → QUBO → [Exact | Greedy | QAOA-statevector | QAOA-Aer | QAOA-IBM] → Assignment + Energy
                                              ↑
                                    CVaR-QAOA (risk-aware, same backends)
```

---

## Track A: Cardiovascular Digital Twin (Your Second Big Story)

### Data (Real, Not Synthetic)
- **Source**: UCI Z-Alizadeh Sani Extension (303 patients, 59 features, 4 angiographic targets)
- **Split**: 183 train / 60 val / 60 test (seed=7, fixed forever)
- **Leakage firewall**: Cath/LAD/LCX/RCA columns **never** reach model inputs

### 4 Models (Registered, Calibrated, Evaluated)
| Model ID | Algorithm | Target | Test AUC | Status |
|----------|-----------|--------|----------|--------|
| `cad-v1` | LogisticRegression | CAD (any) | **0.978** | ✅ Strong |
| `lad-stenosis-v1` | RandomForest | LAD ≥50% | **0.857** | ✅ Strong |
| `lcx-stenosis-v1` | RandomForest | LCX ≥50% | **0.816** | ⚠️ Recall 0.259 — "does NOT rule out" |
| `rca-stenosis-v1` | LogisticRegression | RCA ≥50% | **0.594** | ❌ "NOT decision-grade" |

### Pipeline (One Command)
```bash
python -m rift.health.cardiovascular.pipeline
# Steps: dataset → train → evaluate → calibrate → explain → site
# --from-step=site  # resume after UI edits only
```

### Verify Checklist (7 Gates)
```bash
python -m rift.health.cardiovascular.verify
# 1. Data hash matches manifest
# 2. Registry records exist + hashes match
# 3. Model artifacts (pkl) + calibrators load
# 4. UI site JSON mirrors committed reports
# 5. Both Track A pages exist
# 6. API smoke test (/api/cardio/models, /predict)
# 7. Bandit -r src = 0 findings
```

### Safety Layer (Unique Differentiator)
```python
# safety.py — assesses every prediction before it leaves the API
verdict = assess_prediction(model_id, predictors, prob)
# Returns: safe_to_show, warnings[], disclaimer
# Refuses: uncalibrated models, OOD inputs, weak models (LCX/RCA flagged)
```

---

## Web Demo — Drive It Like You Own It

### Start Everything (One Command)
```bash
bash ./local start
# Starts: API:8080, Redis, Prometheus:9090, Grafana:3000, UI:8000 (background)
# If UI CORS fails: ensure .env.local has RIFT_CORS_ORIGINS=http://localhost:8000
```

### Demo Flow (3 Minutes Max)

#### 1. **Coronary Tree Viewer** → `http://localhost:8000/coronary.html`
- **What they see**: 3D schematic LM/LAD/LCX/RCA, color-coded by calibrated stenosis probability
- **Interact**:
  - Click patient tabs (top) — switch demo patients
  - Hover any vessel — tooltip shows `P = 0.xxx` + "representative site (schematic)"
  - Right panel — probability bars + **What-if counterfactuals** (single observed-value changes)
- **Say**: *"This is the clinician view. Schematic, not anatomy. Colors = calibrated probabilities from our 4 registered models. The what-if panel shows exactly which single observed value would flip each prediction — explanation, not advice."*

#### 2. **Evaluation Dashboard** → `http://localhost:8000/cardio-dashboard.html`
- **What they see**: Honest metrics table, calibration curves, feature importance, model cards
- **Key talking points**:
  - **Metrics table**: LCX recall 0.259 highlighted amber, RCA AUC 0.594 highlighted amber
  - **Reliability curves**: Raw (amber X) vs Calibrated (green dots) — diagonal = perfect
  - **Model cards**: Each has "Limits:" section in plain language
- **Say**: *"We don't hide weak spots. LCX misses 3/4 stenoses. RCA is barely better than coin flip. The model cards say so explicitly."*

#### 3. **API Live** (optional, for technical judges)
```bash
# List models + test AUC
curl http://localhost:8080/api/cardio/models | jq .

# Predict on a demo patient (copy predictors from UI)
curl -X POST http://localhost:8080/api/cardio/predict \
  -H "Content-Type: application/json" \
  -d '{"model_id":"lad-stenosis-v1","predictors":{...},"include_counterfactuals":true}' | jq .
```
- Shows: probability, safety verdict, disclaimer, counterfactuals

#### 4. **Verify Gate** (Proves Rigor)
```bash
python -m rift.health.cardiovascular.verify
# All 7 GREEN = this domain is ship-ready
```

---

## Smart Building Domain (Reference Domain — 30 Sec)
- **Scenario**: Multi-floor building, occupants, hazards, exits
- **Counterfactuals**: "What if stairwell B is blocked?" → re-optimize routes
- **CHAOS Engine**: Perturbs world (fire spread, crowd density) → stress-tests policies
- **Digital Twin**: Patient/occupant state sync, risk trajectories, provenance
- **Guardian**: 16-rule verification before any decision deploys

---

## Killer Q&A Prep

| Judge Question | Your Answer |
|----------------|-------------|
| "Where's the quantum advantage?" | "We don't claim one. The stack is quantum-ready: statevector exact sim, Aer shot-sampling, IBM hardware path — all tested. Hardware is opt-in per-call with a token. Advantage is a research question, not a product claim." |
| "Why QAOA for this?" | "QUBO maps naturally to evacuation routing, traffic lights, grid contingencies. QAOA gives a variational path to approximate solutions; CVaR-QAOA adds risk-awareness for safety-critical domains. The simulator lets us develop/test without hardware queue." |
| "Is the cardiac data real?" | "Yes — UCI Z-Alizadeh Sani Extension, 303 real patients. But: research prototype, not clinical software. Models are calibrated and honestly evaluated; weak ones are flagged. No clinical capability claimed." |
| "How do you prevent leakage?" | "Hard-coded `leakage.py` firewall: Cath/LAD/LCX/RCA columns are dropped before any model sees them. API `/predict` validates all 55 predictor names; 422 if any forbidden column appears." |
| "What's the business model?" | "Platform (RIFT Core) + domain plugins. Track A proves the plugin architecture works for a regulated domain. Power grid, traffic, custom domains follow the same SDK." |
| "Why AGPL?" | "Ensures derivative works stay open — important for safety-critical decision intelligence where transparency protects users." |

---

## Commands You'll Need During Demo

| Action | Command |
|--------|---------|
| Start stack | `bash ./local start` |
| UI only (foreground) | `bash ./local ui` |
| Health check | `bash ./local health` |
| Run Track A pipeline | `python -m rift.health.cardiovascular.pipeline` |
| Verify Track A | `python -m rift.health.cardiovascular.verify` |
| Run all tests | `bash ./local test` |
| View API logs | `bash ./local logs rift-api` |
| Reset everything | `bash ./local reset` |
| API meta | `curl http://localhost:8080/api/meta | jq .` |
| Quantum backend status | `curl http://localhost:8080/api/meta | jq .quantum` |

---

## If Things Go Wrong

| Symptom | Fix |
|---------|-----|
| UI shows "Engine unreachable" | `.env.local` → `RIFT_CORS_ORIGINS=http://localhost:8000` then `bash ./local restart` |
| API 503 "cardio_not_ready" | Run `python -m rift.health.cardiovascular.pipeline` |
| Bandit findings | `bandit -r src` — should be 0; pickle loads are hash-gated with `# nosec` |
| Docker port conflict | `docker-compose -f docker-compose.local.yml down -v` then restart |
| Tests fail | `pip install -e .` then re-run |

---

## Your "Secret Weapon" Slides (If Time)

1. **Guardian 2.0**: 16 rules, staged (INPUT→STATE→MODEL→COUNTERFACTUAL→OPTIMIZATION→OUTPUT→DEPLOYMENT) — every decision audited
2. **Plugin SDK**: `rift.developer.plugin_sdk.DomainPlugin` — new domains in hours, not weeks
3. **Experiment Framework**: Templates, versioning, deterministic replay, benchmark comparisons
4. **SSE Event Stream**: Real-time incident/decision lifecycle without WebSocket complexity
4. **Durable JSONL Ledgers**: Audit trail survives resets; no SQLite, no migration hell

---

## Final Checklist (5 Min Before)

- [ ] `bash ./local start` → all services green
- [ ] `http://localhost:8000/coronary.html` loads, patient tabs work, hover tooltips show
- [ ] `http://localhost:8000/cardio-dashboard.html` loads, tables populate, reliability curve draws
- [ ] `curl http://localhost:8080/api/cardio/models` returns 4 models with AUCs
- [ ] `python -m rift.health.cardiovascular.verify` → 7 GREEN
- [ ] Browser tabs pre-loaded: coronary.html, cardio-dashboard.html, API demo JSON
- [ ] Backup plan: screenshots of both UIs + verify output in phone photos

---

**You built this. You know every file. Go own the room.**