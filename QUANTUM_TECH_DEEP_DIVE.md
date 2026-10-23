# Quantum Technical Deep-Dive — Q&A Reference

## QAOA Implementation Details

### Statevector Simulator (`src/rift/qaoa.py`)
```python
def simulate_qaoa(qubo: QUBO, p: int = 1, grid_steps: int = 5,
                  iterations: int = 3, objective: str = "expectation",
                  alpha: float = 0.25, accelerator: str = "off") -> QAOAResult:
    """
    - Exact statevector evolution (no sampling noise)
    - Coordinate/grid search for variational parameters
    - Deterministic for fixed seed
    - Limited to ≤12 qubits (2^12 = 4096 amplitudes)
    - Objective: "expectation" or "cvar" (CVaR-QAOA)
    - Accelerator: "off" (pure Python) or "torch" (GPU if available)
    """
```
**Key functions**:
- `_energies(qubo)` — Precompute all 2^n energies (classical)
- `_apply_mixer(state, n, beta)` — X-mixer layer (Rx rotations)
- `_state(energies, n, betas, gammas)` — Full QAOA circuit on statevector
- `_expectation(state, energies)` — ⟨ψ|H|ψ⟩
- `_cvar(state, energies, alpha)` — Conditional Value at Risk

**Grid search**: For each layer, sweep β ∈ [0, π), γ ∈ [0, 2π) with `grid_steps` points, `iterations` refinement passes.

### Aer Simulator (`src/rift/qpu.py::solve_on_aer`)
```python
def solve_on_aer(qubo: QUBO, *, p: int = 1, shots: int = 1024, seed: int = 7):
    """
    1. _optimized_angles() — COBYLA on statevector expectation (Qiskit QAOAAnsatz)
    2. ansatz.assign_parameters(theta).measure_all() — Add measurements
    3. AerSimulator(seed_simulator=seed) — Shot sampling
    4. Return most-sampled bitstring + exact energy
    """
```
- Uses Qiskit's `QAOAAnsatz` + `AerSimulator` + `transpile`
- Angles optimized on **statevector expectation** (exact), then **sampled** on Aer
- Deterministic for fixed `seed` (transpiler + simulator)

### IBM Hardware (`src/rift/qpu.py::solve_on_ibm`)
```python
def solve_on_ibm(qubo: QUBO, backend_name: str, shots: int = 1000):
    """
    1. _optimized_angles() — Same local COBYLA optimization
    2. transpile(measured, backend) — Hardware-native gates
    3. SamplerV2(mode=backend).run([(transpiled,)], shots=shots)
    4. job.result()[0].data.meas.get_counts()
    """
```
- **Requires**: `RIFT_QPU_TOKEN` env var or saved `qiskit-ibm-runtime` account
- **Human gate**: First run requires manual credential setup (see `HARDWARE_SETUP_STEPS`)
- **Never default** — explicit per-call opt-in only

### CVaR-QAOA (`src/rift/cvar.py`)
```python
def cvar_from_distribution(energies: list[float], probs: list[float], alpha: float) -> float:
    """Sort by energy, accumulate probability until alpha, average tail."""
    # alpha=0.25 → optimize worst 25% of distribution
```
- Same QAOA circuit, different objective
- Risk-aware: protects against worst outcomes
- Critical for safety-critical domains (evacuation, medical)

---

## QUBO Formulation (Domain → Optimization)

### General Mapping
```
Decision variables: x_i ∈ {0,1}
Objective: minimize x^T Q x + c^T x
Constraints: penalty terms → quadratic penalties
```

### Domain Examples

**Evacuation Routing** (Smart Building):
- Variables: `person_p_stairwell_s` ∈ {0,1}
- Objective: minimize total evacuation time
- Constraints: each person one stairwell, capacity limits

**Traffic Light Timing** (Traffic):
- Variables: `intersection_i_phase_p` ∈ {0,1}
- Objective: minimize total delay / maximize throughput
- Constraints: one phase per intersection, minimum green times

**Grid Contingency** (Power Grid):
- Variables: `generator_g_on_off` ∈ {0,1}, `line_l_switch` ∈ {0,1}
- Objective: minimize load shed / maximize stability margin
- Constraints: power flow equations (linearized), N-1 security

**Cardiac (Track A)**: Not a QUBO — classical ML. But the **same optimizer interface** accepts QUBOs from any domain.

---

## Optimizer Interface (`src/rift/optimizer.py`)

```python
@dataclass(frozen=True)
class QUBO:
    variables: tuple[str, ...]
    linear: dict[str, float]
    quadratic: dict[tuple[str, str], float]

@dataclass(frozen=True)
class OptimizationResult:
    assignment: dict[str, int]
    energy: float
    method: str  # "exact", "greedy", "qaoa-statevector-simulator", "qaoa-aer-simulator", "qaoa-ibm:backend"

def exact_minimize(qubo: QUBO) -> OptimizationResult:        # Brute force ≤20 vars
def greedy_minimize(qubo: QUBO) -> OptimizationResult:        # Fast heuristic
def qaoa_minimize(qubo: QUBO, p=1, objective="expectation", ...) -> OptimizationResult:
def qaoa_aer_minimize(qubo: QUBO, p=1, shots=1024, ...) -> OptimizationResult:
def qaoa_ibm_minimize(qubo: QUBO, backend_name: str, shots=1000, ...) -> OptimizationResult:
```

**All solvers share the same interface** — domain code doesn't care which backend.

---

## Benchmark & Validation

### Test: `tests/test_qpu_aer.py::test_aer_matches_exact_on_reference_instance`
```python
def test_aer_matches_exact_on_reference_instance():
    qubo = REFERENCE_QUBO  # Fixed 8-variable problem
    exact = exact_minimize(qubo)
    aer = solve_on_aer(qubo, p=1, shots=2048, seed=7)
    # Aer result should match exact energy (within sampling variance)
    assert abs(aer.energy - exact.energy) < 1e-6
```
- **Proves**: Aer implementation correctly executes QAOA
- **Reference QUBO**: 8 variables, known exact optimum
- **Runs in CI** — no hardware needed

### Test: `test_aer_deterministic_for_fixed_seed`
```python
def test_aer_deterministic_for_fixed_seed():
    r1 = solve_on_aer(qubo, seed=42)
    r2 = solve_on_aer(qubo, seed=42)
    assert r1.assignment == r2.assignment
```
- **Proves**: Reproducibility (critical for scientific computing)

---

## Performance Characteristics

| Backend | Max Variables | Time (typical) | Deterministic | Hardware |
|---------|---------------|----------------|---------------|----------|
| Exact | ≤20 | 2^n × poly | Yes | CPU |
| Greedy | ∞ | O(n^2) | Yes | CPU |
| Statevector QAOA | ≤12 | O(p × grid^2p × 2^n) | Yes | CPU/GPU |
| Aer QAOA | ≤20* | O(p × COBYLA_iter × shots) | Yes (fixed seed) | CPU |
| IBM Hardware | ≤127* | Queue + execution | No (shot noise) | QPU |

*Limited by transpilation/connectivity, not simulator

---

## Integration Points

### From Domain to QUBO
```python
# In domain plugin (e.g., src/rift/domains/traffic/domain.py)
def build_qubo(self, world_state) -> QUBO:
    # Map domain decisions → binary variables
    # Build linear + quadratic coefficients
    return QUBO(variables, linear, quadratic)

# In optimization call
result = qaoa_minimize(qubo, p=2, objective="cvar", alpha=0.25)
# Or: result = qaoa_aer_minimize(qubo, p=2, shots=2048)
# Or: result = qaoa_ibm_minimize(qubo, "ibm_brisbane", shots=1000)
```

### From QUBO Result to Domain Action
```python
assignment = result.assignment  # {"var_name": 0/1, ...}
# Map back to domain actions
actions = decode_assignment(assignment)
```

---

## Common Judge Questions — Technical Answers

### "How do you handle barren plateaus?"
> Statevector simulator computes exact gradients via expectation value — no sampling noise. For Aer, we use COBYLA (derivative-free) on statevector expectation, not parameter-shift on hardware. Barren plateaus are a hardware sampling issue; we optimize on exact simulator first.

### "Why p=1 or p=2 only?"
> Statevector: 2^n amplitude vector. p layers = 2p parameters. Grid search is O(grid_steps^{2p}). p=2 with grid_steps=5 = 25^4 = 390k evaluations — already slow. For larger p, need gradient-based optimizers (future work).

### "How does CVaR-QAOA differ from standard QAOA?"
> Standard QAOA minimizes ⟨H⟩ = Σ p_i E_i. CVaR minimizes average of worst α-fraction: (1/α) Σ_{E_i > VaR_α} p_i E_i. Same circuit, different classical post-processing of measurement distribution. Implemented in `cvar.py::cvar_from_distribution()`.

### "Can you do constrained optimization?"
> Yes — penalty method. Constraints → quadratic penalties added to QUBO. Example: `x_i + x_j ≤ 1` → penalty `M * x_i * x_j` (M large). Exact/statevector handles exactly; hardware needs careful penalty scaling.

### "What's the largest problem you've solved?"
> Statevector: 12 variables (4096 amplitudes) — evacuation zone with 12 decision points.
> Aer: 16 variables (shot sampling, no statevector limit).
> IBM: Not yet run on hardware (token-gated, external gate).

### "How do you verify quantum results?"
> Three layers:
> 1. **Exact baseline** — brute force for ≤20 vars
> 2. **Statevector cross-check** — Aer matches exact on reference QUBO (CI test)
> 3. **Deterministic seeds** — Fixed seed = reproducible assignment

---

## Code Locations Quick Reference

| Component | File | Key Function/Class |
|-----------|------|-------------------|
| Statevector QAOA | `src/rift/qaoa.py` | `simulate_qaoa()`, `qaoa_minimize()` |
| Aer QAOA | `src/rift/qpu.py` | `solve_on_aer()` |
| IBM QAOA | `src/rift/qpu.py` | `solve_on_ibm()` |
| CVaR | `src/rift/cvar.py` | `cvar_from_distribution()` |
| QUBO/Result | `src/rift/optimizer.py` | `QUBO`, `OptimizationResult` |
| Exact/Greedy | `src/rift/optimizer.py` | `exact_minimize()`, `greedy_minimize()` |
| Accelerator (torch) | `src/rift/accelerate.py` | `resolve_accelerator()`, `torch_qaoa_state()` |
| Tests | `tests/test_qpu_aer.py` | `test_aer_matches_exact...` |
| Benchmark | `src/rift/benchmark.py` | `benchmark_optimizers()` |

---

## Hardware Setup (If Asked)

```bash
# 1. Create IBM Quantum account
# https://quantum.cloud.ibm.com/ (Open Plan: 10 min / 28 days)

# 2. Install
pip install rift-engine[qiskit]
# or: pip install qiskit qiskit-aer qiskit-ibm-runtime

# 3. Get API key from dashboard
export RIFT_QPU_TOKEN="44-char-key-from-ibm-quantum-dashboard"

# 4. Run (explicit opt-in)
python -c "
from rift.optimizer import QUBO
from rift.qpu import solve_on_ibm
qubo = QUBO(('x','y'), {'x':-1,'y':-1}, {('x','y'):2})
result = solve_on_ibm(qubo, backend_name='ibm_brisbane', shots=1000)
print(result)
"
```

**First run fails with actionable error** if token missing — tells exact setup steps.

---

## What We Don't Do (Honest Boundaries)

| Claim | Reality |
|-------|---------|
| Quantum advantage | ❌ Not demonstrated |
| Production hardware runs | ❌ External gate, human credentials required |
| Large-scale QAOA | ❌ Statevector ≤12 qubits, Aer ≤20 vars |
| Fault-tolerant | ❌ NISQ-era only (noisy, no error correction) |
| Real-time quantum | ❌ Optimize offline, deploy assignment |

**We say**: "Quantum-ready optimization stack — simulators in CI, hardware path implemented and tested for correctness, hardware execution is explicit opt-in."

---

## Talking Points for Quantum Judges

1. **Software-first approach** — Classical simulators (exact, statevector, Aer) let us develop/test quantum algorithms without queue time. Hardware is a backend swap.

2. **CVaR-QAOA for safety** — Standard QAOA optimizes average case. CVaR optimizes tail risk. Critical for evacuation/medical where worst-case matters.

3. **Deterministic CI** — Every quantum path tested against exact baseline. `test_aer_matches_exact_on_reference_instance` proves Aer correctness.

4. **Domain-agnostic** — Same QUBO interface serves building, traffic, grid, custom domains. Quantum is an optimization backend, not a domain feature.

5. **Honest about limits** — Statevector exponential, hardware noisy, no advantage claimed. This is infrastructure for when hardware improves.

---

## One-Liner for Each Component

| Component | One-Liner |
|-----------|-----------|
| `qaoa.py` | "Dependency-free statevector QAOA with grid search — exact for ≤12 qubits" |
| `qpu.py` | "Aer shot-sampling + IBM hardware path — opt-in, token-gated, never default" |
| `cvar.py` | "CVaR from measurement distribution — same circuit, risk-aware objective" |
| `optimizer.py` | "Unified interface: Exact/Greedy/QAOA-Aer/QAOA-IBM all return `OptimizationResult`" |
| `benchmark.py` | "Times all solvers on same QUBOs — exact baseline, speed/quality tradeoffs" |
| `tests/test_qpu_aer.py` | "Aer matches exact statevector on reference QUBO — deterministic, in CI" |