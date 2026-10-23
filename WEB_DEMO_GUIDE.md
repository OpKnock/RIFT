# Web Demo Walkthrough Guide — Drive It Like You Built It

## Prerequisites (Do This NOW)

```bash
cd C:\Users\wagde\MegaProjects\RIFT

# 1. Install package (if not done)
pip install -e . -q

# 2. Verify Track A artifacts exist
python -m rift.health.cardiovascular.verify
# Should show 7 GREEN gates

# 3. Start the stack
bash ./local start
# Wait for: "RIFT local environment started!"
# API: http://localhost:8080
# UI:  http://localhost:8000
```

## Pre-Demo Browser Setup (2 minutes before)

Open **three tabs** in this order:

| Tab | URL | Purpose |
|-----|-----|---------|
| 1 | `http://localhost:8000/coronary.html` | Coronary Tree Viewer (main demo) |
| 2 | `http://localhost:8000/cardio-dashboard.html` | Evaluation Dashboard (honest metrics) |
| 3 | `http://localhost:8080/api/cardio/models` | API proof (JSON) |

**Verify each loads:**
- Tab 1: 3D heart renders, patient tabs visible, hover shows tooltips
- Tab 2: Tables populate, reliability curve draws, model cards show
- Tab 3: Returns 4 models with `test_roc_auc` values

**If Tab 1/2 show "Engine unreachable" banner:**
```bash
# Check .env.local has CORS origin
grep RIFT_CORS_ORIGINS .env.local
# Should show: RIFT_CORS_ORIGINS=http://localhost:8000
# If missing/empty:
echo 'RIFT_CORS_ORIGINS=http://localhost:8000' >> .env.local
bash ./local restart
```

---

## Demo Flow — Coronary Tree Viewer (Tab 1) — 90 Seconds

### 1. Opening (10 sec)
> *"This is the clinician view. Schematic coronary tree — not anatomy. Branch colors = calibrated stenosis probabilities from our 4 registered models."*

### 2. Patient Switching (20 sec)
**Action**: Click each patient tab at top (`patient-001`, `patient-002`, etc.)
**Say**: *"Six patients from the held-out test set. Each has ground-truth angiographic labels."*

### 3. Hover Interaction (20 sec)
**Action**: Hover mouse over LAD branch → tooltip appears
**Say**: *"Hover any vessel — calibrated probability, labeled 'representative site (schematic)'. No false precision."*

### 4. Probability Bars (15 sec)
**Action**: Point to right panel bars (CAD overall, LAD, LCX, RCA)
**Say**: *"Right panel: probability bars with ground truth. Green→amber→red = 0→0.5→1."*

### 5. What-If Counterfactuals (25 sec) — **KILLER FEATURE**
**Action**: Point to "What would flip each prediction?" panel
**Say**: *"Here's the unique part: permutation counterfactuals. Single observed-value changes only."*

**Demo Script for Patient with Typical Chest Pain = 0**:
> *"Watch LAD: P = 0.615. What-if panel says: 'If Typical Chest Pain were 1 (was 0) → P 0.823 ✓ toward truth'."
> *"This is model-behavior explanation — 'this feature drives this prediction' — **not medical advice**."*

**Demo Script for LCX Miss**:
> *"Switch to patient where LCX is green (P=0.312) but truth = Stenotic. What-if: 'Stable — no single observed-value change flips this prediction.' That's the recall 0.259 problem, visible to the clinician."*

---

## Demo Flow — Evaluation Dashboard (Tab 2) — 90 Seconds

### 1. Metrics Table (25 sec)
**Action**: Scroll to "Held-out test metrics + 5-fold CV stability"
**Say**: *"Honest metrics. LCX recall 0.259 highlighted amber. RCA AUC 0.594 highlighted amber. We don't hide weak spots."*

### 2. Reliability Curves (25 sec)
**Action**: Click CAD / LAD / LCX / RCA tabs under "Reliability curve"
**Say**: *"Amber X = raw probabilities. Green dots = isotonic calibrated. Diagonal = perfect. LCX calibration didn't help — reported as-is."*

### 3. Feature Importance (20 sec)
**Action**: Point to "What drives each model" grid
**Say**: *"Permutation AUC-drop on held-out test. Top 10 per model. LAD driven by Typical Chest Pain, HTN, EF-TTE..."*

### 4. Model Cards (20 sec)
**Action**: Scroll to "Model cards" section
**Say**: *"Each card has plain-language Limits section."*

**Click RCA card** → Read aloud: *"'This model is NOT decision-grade (test AUC 0.594). Do not use for clinical decisions.'*

**Click LCX card** → Read aloud: *"'This model does NOT rule out stenosis (recall 0.259). Negative result requires confirmatory testing.'*

---

## Demo Flow — API Proof (Tab 3 or Terminal) — 30 Seconds

### Option A: Browser Tab 3
**Action**: Refresh `http://localhost:8080/api/cardio/models`
**Say**: *"Same data driving the UI — 4 models, test AUC, calibration method, feature schema version."*

### Option B: Terminal (More Impressive)
```bash
# In terminal, run:
curl -s http://localhost:8080/api/cardio/models | jq .

# Then a prediction:
curl -s -X POST http://localhost:8080/api/cardio/predict \
  -H "Content-Type: application/json" \
  -d '{"model_id":"lad-stenosis-v1","predictors":{"Age":65,"Sex":1,"Typical Chest Pain":1,"HTN":1,"EF-TTE":55},"include_counterfactuals":true}' | jq .
```
**Say**: *"POST /predict returns: probability, safety verdict, disclaimer, and counterfactuals. Safety verdict includes warnings for weak models."*

---

## Keyboard Shortcuts for Smooth Demo

| Action | Shortcut |
|--------|----------|
| Switch tabs | `Ctrl+Tab` / `Ctrl+Shift+Tab` |
| Zoom in/out | `Ctrl++` / `Ctrl+-` |
| Full screen | `F11` |
| DevTools (if needed) | `F12` |
| Refresh | `F5` |

---

## Troubleshooting During Demo

| Problem | Quick Fix |
|---------|-----------|
| 3D canvas black / "3D unavailable" | WebGL blocked? Right panel still has all data — say: *"All info in right panel; 3D is bonus."* |
| Patient tabs don't load | `bash ./local ui` in separate terminal (serves UI foreground) |
| API returns 503 "cardio_not_ready" | Run pipeline: `python -m rift.health.cardiovascular.pipeline --from-step=site` |
| CORS error in console | Check `.env.local` has `RIFT_CORS_ORIGINS=http://localhost:8000` |
| Port 8000/8080 in use | `bash ./local stop` then `bash ./local start` |
| Bandit warning in verify | Should be 0. If not: `bandit -r src` — pickle loads are hash-gated |

---

## Backup Screenshots (Take These NOW)

In case live demo fails, have these on phone/second monitor:

```bash
# Terminal: verify output
python -m rift.health.cardiovascular.verify

# Terminal: API models
curl -s http://localhost:8080/api/cardio/models | jq .

# Screenshots:
# 1. coronary.html with patient-001, LAD hover tooltip visible
# 2. coronary.html what-if panel open
# 3. cardio-dashboard.html metrics table (LCX/RCA amber)
# 4. cardio-dashboard.html reliability curve (LCX tab)
# 5. cardio-dashboard.html RCA model card (LIMITS section)
```

**How to screenshot on Windows**: `Win+Shift+S` → select area → auto-copies to clipboard

---

## What Judges Will Click (Anticipate)

| Judge Action | Your Response |
|--------------|---------------|
| Clicks patient tab | "Six held-out test patients, each with ground truth" |
| Hovers vessel | "Calibrated probability, schematic site marker" |
| Asks "what's the color scale?" | "Green→amber→red = 0→0.5→1 stenosis probability" |
| Clicks LCX reliability tab | "Calibration didn't help this model — raw and calibrated nearly overlap" |
| Reads RCA model card | "Explicitly flagged NOT decision-grade. That's the point — honest eval." |
| Asks "can I try a prediction?" | "Sure — copy predictors from right panel, POST to /api/cardio/predict" |
| Asks "where's the quantum?" | "Optimization engine — QAOA solvers in qaoa.py/qpu.py. Same QUBO from routing → cardiac." |

---

## Your Demo Mantras

> **"Schematic, not anatomy."** — Repeat when showing coronary.html
>
> **"Explanation, not advice."** — Repeat for what-if counterfactuals
>
> **"Honest evaluation."** — Repeat for dashboard metrics
>
> **"Research prototype."** — Repeat if anyone suggests clinical use
>
> **"Quantum-ready, not quantum advantage."** — Repeat for quantum questions

---

## Post-Demo: Leave Them With

1. **Repo**: `github.com/OpKnock/RIFT`
2. **Run locally**: `git clone && cd RIFT && bash ./local start`
3. **Track A verify**: `python -m rift.health.cardiovascular.verify` (7 gates)
4. **Quantum entry point**: `src/rift/qaoa.py` (statevector) → `src/rift/qpu.py` (Aer/IBM)

---

## Emergency Commands Card

```bash
# Full reset (nuclear option)
bash ./local reset
bash ./local start

# Just UI restart
bash ./local stop
bash ./local ui  # foreground, Ctrl+C to stop

# Just API logs
bash ./local logs rift-api

# Verify Track A (proves rigor)
python -m rift.health.cardiovascular.verify

# Run quantum tests
python -m pytest tests/test_qpu_aer.py -v
```

---

## Final Pre-Flight (5 Min Before)

- [ ] `bash ./local start` → all 5 services green
- [ ] Tab 1: coronary.html loads, patient tabs work, hover works
- [ ] Tab 2: cardio-dashboard.html loads, tables populate, curve draws
- [ ] Tab 3: API returns JSON
- [ ] Terminal: `python -m rift.health.cardiovascular.verify` → 7 GREEN
- [ ] Screenshots saved to phone
- [ ] Water, charged laptop, presentation clicker ready

**You're ready. Go win.**