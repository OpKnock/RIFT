"""Real quantum execution boundary: Qiskit Aer simulator + IBM hardware path.

- `solve_on_aer` runs QAOA through the actual Qiskit SDK (AerSimulator with
  shot sampling) and is tested in CI. This is real quantum-software
  execution, still classical simulation — never hardware.
- `solve_on_ibm` connects to IBM Quantum hardware via qiskit-ibm-runtime.
  It is fully implemented except the final job submission, which requires
  human credentials no automation may invent: without RIFT_QPU_TOKEN (or a
  saved account) it raises an actionable error with the exact setup steps.
  First hardware run is EXTERNAL (see docs/external-gates.md).

Qiskit stays an optional extra: every import happens inside the function
that needs it, so the stdlib-only default install is unaffected.
"""
from __future__ import annotations

import os

from .optimizer import QUBO, OptimizationResult

HARDWARE_SETUP_STEPS = (
    "IBM Quantum hardware setup: 1) create a free account at "
    "https://quantum.cloud.ibm.com/ (Open Plan: 10 min / 28 days). "
    "2) pip install qiskit-ibm-runtime. 3) create an API key on the "
    "dashboard and export RIFT_QPU_TOKEN=<44-char-key>. 4) call "
    "solve_on_ibm(qubo, backend_name=<backend>) with an operational backend. "
    "Never commit the token; it is read from the environment only."
)


def qiskit_aer_available() -> bool:
    try:
        import qiskit  # noqa: F401
        import qiskit_aer  # noqa: F401
        return True
    except ImportError:
        return False


def qaoa_hardware_available() -> bool:
    try:
        import qiskit  # noqa: F401
        import qiskit_ibm_runtime  # noqa: F401
        return bool(os.environ.get("RIFT_QPU_TOKEN"))
    except ImportError:
        return False


def _ising_operator(qubo: QUBO):
    """Map QUBO (x in {0,1}) to an Ising SparsePauliOp via x = (1 - Z) / 2."""
    from qiskit.quantum_info import SparsePauliOp
    n = len(qubo.variables)
    coeffs: dict[str, float] = {}
    for name, bias in qubo.linear.items():
        i = qubo.variables.index(name)
        key = ["I"] * n
        key[i] = "Z"
        label = "".join(reversed(key))
        coeffs[label] = coeffs.get(label, 0.0) - bias / 2.0
    for (a, b), strength in qubo.quadratic.items():
        i, j = qubo.variables.index(a), qubo.variables.index(b)
        key = ["I"] * n
        key[i] = "Z"
        key[j] = "Z"
        label = "".join(reversed(key))
        coeffs[label] = coeffs.get(label, 0.0) + strength / 4.0
        for k, name in ((i, a), (j, b)):
            single = ["I"] * n
            single[k] = "Z"
            slabel = "".join(reversed(single))
            coeffs[slabel] = coeffs.get(slabel, 0.0) - strength / 4.0
    const = sum(qubo.linear.values()) / 2.0 + sum(qubo.quadratic.values()) / 4.0
    labels = list(coeffs) or ["I" * max(n, 1)]
    values = [coeffs.get(lb, 0.0) for lb in labels]
    return SparsePauliOp(labels, values), const


def _optimized_angles(qubo: QUBO, *, p: int, seed: int):
    """Shared angle optimization: COBYLA on the statevector expectation."""
    import numpy as np
    from qiskit.circuit.library import QAOAAnsatz
    from qiskit.quantum_info import Statevector
    from scipy.optimize import minimize

    cost_op, _const = _ising_operator(qubo)
    ansatz = QAOAAnsatz(cost_op, reps=max(1, p))
    rng = np.random.default_rng(seed)
    x0 = rng.uniform(-np.pi, np.pi, ansatz.num_parameters)

    def expectation(theta):
        bound = ansatz.assign_parameters(theta)
        state = Statevector.from_instruction(bound)
        return float(np.real(state.expectation_value(cost_op).real))

    result = minimize(expectation, x0, method="COBYLA",
                      options={"maxiter": 150, "tol": 1e-3})
    return ansatz, result.x


def _counts_to_assignment(qubo: QUBO, counts: dict) -> dict[str, int]:
    best_bits = max(counts, key=lambda bits: counts[bits]).replace(" ", "")
    return {name: int(bit) for name, bit in zip(qubo.variables, reversed(best_bits))}


def solve_on_aer(qubo: QUBO, *, p: int = 1, shots: int = 1024, seed: int = 7) -> OptimizationResult:
    """QAOA executed by the Qiskit Aer simulator with shot sampling.

    Angles are optimized with COBYLA against the statevector expectation,
    then the final circuit is sampled on AerSimulator. Deterministic for a
    fixed seed. Returns the most-sampled bitstring and its exact energy.
    """
    if not qubo.variables:
        raise ValueError("QUBO has no variables")
    if not qiskit_aer_available():
        raise RuntimeError("Install rift-engine[qiskit] (qiskit, qiskit-aer) for the Aer backend.")
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    ansatz, theta = _optimized_angles(qubo, p=p, seed=seed)
    measured = ansatz.assign_parameters(theta).measure_all(inplace=False)
    backend = AerSimulator(seed_simulator=seed)
    transpiled = transpile(measured, backend, seed_transpiler=seed)
    counts = backend.run(transpiled, shots=max(1, shots)).result().get_counts()
    assignment = _counts_to_assignment(qubo, counts)
    return OptimizationResult(assignment, qubo.energy(assignment), "qaoa-aer-simulator")


def solve_on_ibm(qubo: QUBO, backend_name: str, shots: int = 1000) -> OptimizationResult:
    """QAOA sampled on IBM Quantum hardware via qiskit-ibm-runtime Sampler.

    Angles are optimized locally (Aer statevector); the final circuit is
    transpiled for the named backend and sampled with SamplerV2. Requires
    RIFT_QPU_TOKEN or a saved qiskit-ibm-runtime account. First execution
    needs a human with credentials — see HARDWARE_SETUP_STEPS.
    """
    if not qubo.variables:
        raise ValueError("QUBO has no variables")
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
        from qiskit import transpile
    except ImportError as exc:
        raise RuntimeError(
            "Install rift-engine[qiskit] with qiskit-ibm-runtime for hardware. "
            + HARDWARE_SETUP_STEPS) from exc
    token = os.environ.get("RIFT_QPU_TOKEN")
    try:
        service = (QiskitRuntimeService(token=token)
                   if token else QiskitRuntimeService())
    except Exception as exc:
        raise RuntimeError(
            "Could not authenticate to IBM Quantum. " + HARDWARE_SETUP_STEPS) from exc
    try:
        backend = service.backend(backend_name)
    except Exception as exc:
        raise RuntimeError(
            f"Backend {backend_name!r} unavailable: {exc}. "
            "Pick an operational backend from the IBM Quantum dashboard.") from exc
    ansatz, theta = _optimized_angles(qubo, p=1, seed=7)
    measured = ansatz.assign_parameters(theta).measure_all(inplace=False)
    transpiled = transpile(measured, backend)
    sampler = Sampler(mode=backend)
    job = sampler.run([(transpiled,)], shots=max(1, shots))
    counts = job.result()[0].data.meas.get_counts()
    assignment = _counts_to_assignment(qubo, counts)
    return OptimizationResult(assignment, qubo.energy(assignment), f"qaoa-ibm:{backend_name}")
