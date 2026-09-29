"""Tensor accelerator: bitwise parity with reference kernels + wiring.

The contract is strict: accelerated paths must return EXACTLY what the
pure-Python kernels return (same energies, same product-order tie-breaks,
same statevector amplitudes, same method strings). Speed is reported,
never asserted (timing is environment noise).
"""
import random
import time

import pytest

torch = pytest.importorskip("torch")

from rift.accelerate import (
    accelerator_report,
    default_accelerator,
    resolve_accelerator,
    torch_argmin_product_order,
    torch_energies,
    torch_exact_minimize,
    torch_qaoa_state,
)
from rift.optimizer import QUBO, exact_minimize
from rift.qaoa import _energies, _state, qaoa_minimize, simulate_qaoa
from rift.scenarios import emergency_building


def _random_qubo(rng, n):
    variables = tuple("x%d" % i for i in range(n))
    linear = {v: rng.uniform(-5, 5) for v in variables}
    quad = {}
    for a in variables:
        for b in variables:
            if a < b and rng.random() < 0.5:
                quad[(a, b)] = rng.uniform(-5, 5)
    return QUBO(variables, linear, quad or None, rng.uniform(-2, 2))


def _reference_qubo():
    from rift.robust_qubo import build_robust_qubo
    scenario = emergency_building()
    return build_robust_qubo(scenario, ("route_a", "route_c"),
                             [{"smoke": 2.0}, {"crowd": 80.0}])


def test_energies_bitwise_parity_reference_instance():
    qubo = _reference_qubo()
    assert torch_energies(qubo) == _energies(qubo)


def test_energies_bitwise_parity_fuzz():
    rng = random.Random(20260929)
    for _ in range(25):
        qubo = _random_qubo(rng, rng.randint(1, 9))
        assert torch_energies(qubo) == _energies(qubo)


def test_exact_minimize_parity_including_ties():
    rng = random.Random(77)
    cases = [_reference_qubo()]
    cases += [_random_qubo(rng, rng.randint(1, 9)) for _ in range(25)]
    # Engineered ties: duplicate energies force tie-break paths.
    cases.append(QUBO(("a", "b"), {"a": 0.0, "b": 0.0}, None, 0.0))
    cases.append(QUBO(("a", "b", "c"), {"a": 1.0}, {("a", "b"): -1.0}, 0.0))
    for qubo in cases:
        ref = exact_minimize(qubo)
        fast = torch_exact_minimize(qubo)
        assert fast.assignment == ref.assignment
        assert fast.energy == ref.energy
        assert fast.method == ref.method


def test_exact_minimize_kwarg_matches_default():
    qubo = _reference_qubo()
    assert exact_minimize(qubo, accelerator="off").energy == exact_minimize(qubo).energy
    assert exact_minimize(qubo, accelerator="auto").energy == exact_minimize(qubo).energy


def test_qaoa_state_bitwise_parity():
    rng = random.Random(913)
    for _ in range(10):
        qubo = _random_qubo(rng, rng.randint(1, 8))
        energies = _energies(qubo)
        n = len(qubo.variables)
        for angles in [((0.7,), (0.3,)), ((0.7, 0.2), (0.3, 1.1))]:
            assert torch_qaoa_state(energies, n, *angles) == _state(energies, n, *angles)


def test_qaoa_minimize_parity():
    qubo = _reference_qubo()
    ref = qaoa_minimize(qubo)
    fast = qaoa_minimize(qubo, accelerator="auto")
    assert fast.assignment == ref.assignment
    assert fast.energy == ref.energy
    assert fast.method == ref.method


def test_simulate_qaoa_parity_full_result():
    qubo = _reference_qubo()
    ref = simulate_qaoa(qubo)
    fast = simulate_qaoa(qubo, accelerator="cpu")
    assert fast == ref


def test_resolve_accelerator_matrix(monkeypatch):
    assert resolve_accelerator("off") == {
        "use_torch": False, "device": "cpu",
        "note": "accelerator off (RIFT_ACCELERATOR=off)"}
    auto = resolve_accelerator("auto")
    assert auto["use_torch"] is True
    assert auto["device"] in ("cpu", "cuda")
    cpu = resolve_accelerator("cpu")
    assert cpu == {"use_torch": True, "device": "cpu", "note": "torch cpu kernels"}
    cuda = resolve_accelerator("cuda")
    assert cuda["device"] in ("cpu", "cuda")
    assert cuda["use_torch"] is True
    if cuda["device"] == "cpu":
        assert "unavailable" in cuda["note"]
    unknown = resolve_accelerator("warp-drive")
    assert unknown["use_torch"] is False


def test_default_accelerator_env(monkeypatch):
    monkeypatch.delenv("RIFT_ACCELERATOR", raising=False)
    assert default_accelerator() == "off"
    monkeypatch.setenv("RIFT_ACCELERATOR", "auto")
    assert default_accelerator() == "auto"


def test_engine_env_opt_in_matches_off(monkeypatch):
    from rift.experiments import validate_spec_payload
    from rift.runner import run_spec
    spec = validate_spec_payload({
        "name": "acc-parity", "optimizer": "exact",
        "initial_state": {"crowd": 430.0, "smoke": 3.0, "corridor_capacity": 520.0},
    })
    monkeypatch.delenv("RIFT_ACCELERATOR", raising=False)
    base = run_spec(spec)
    monkeypatch.setenv("RIFT_ACCELERATOR", "auto")
    fast = run_spec(spec)
    # duration_ms is wall-clock; everything else must be identical.
    base.pop("duration_ms", None)
    fast.pop("duration_ms", None)
    assert fast == base


def test_accelerator_report_shape():
    report = accelerator_report()
    assert set(report) == {"requested", "torch_available", "cuda_available",
                           "active", "device", "note"}
    assert report["torch_available"] is True
    assert report["active"] in ("reference", "torch")


def test_speedup_reported_not_asserted(capsys):
    qubo = _reference_qubo()
    t0 = time.perf_counter()
    exact_minimize(qubo)
    ref_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    torch_exact_minimize(qubo)
    fast_ms = (time.perf_counter() - t0) * 1000
    with capsys.disabled():
        print("\nexact reference %.2fms vs torch %.2fms (%.1fx)" %
              (ref_ms, fast_ms, ref_ms / max(fast_ms, 1e-9)))
