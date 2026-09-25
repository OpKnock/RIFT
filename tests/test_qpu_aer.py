"""Qiskit Aer backend: real SDK execution; hardware path fail-closed."""
import pytest

qiskit_aer = pytest.importorskip("qiskit_aer", reason="qiskit extra not installed")

from rift.optimizer import QUBO, exact_minimize
from rift.qpu import (HARDWARE_SETUP_STEPS, qiskit_aer_available,
                      solve_on_aer, solve_on_ibm)

Q = QUBO(("a", "b"), {"a": -2, "b": -1}, {("a", "b"): 3})


def test_aer_available():
    assert qiskit_aer_available() is True


def test_aer_matches_exact_on_reference_instance():
    result = solve_on_aer(Q, shots=1024, seed=7)
    assert result.method == "qaoa-aer-simulator"
    assert set(result.assignment) == {"a", "b"}
    assert result.energy == exact_minimize(Q).energy


def test_aer_deterministic_for_fixed_seed():
    first = solve_on_aer(Q, shots=512, seed=7)
    second = solve_on_aer(Q, shots=512, seed=7)
    assert first.assignment == second.assignment


def test_aer_rejects_empty_qubo():
    with pytest.raises(ValueError, match="no variables"):
        solve_on_aer(QUBO((), {}, {}))


def test_hardware_gating_actionable_without_credentials(monkeypatch):
    monkeypatch.delenv("RIFT_QPU_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="IBM Quantum"):
        solve_on_ibm(Q, "ibm_kingston")
    assert "quantum.cloud.ibm.com" in HARDWARE_SETUP_STEPS
    assert "RIFT_QPU_TOKEN" in HARDWARE_SETUP_STEPS
