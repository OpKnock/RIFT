"""Optional tensor acceleration for the exact and QAOA simulation kernels.

Bitwise-identical to the reference pure-Python kernels by construction and
by test (tests/test_accelerate.py parity fuzz): same energies, same
product-order tie-breaking, same statevector amplitudes. The only
difference is speed: assignments are evaluated as batched tensor ops
instead of one Python dict evaluation per bitstring.

Device selection honors ``RIFT_ACCELERATOR`` (``off``/``auto``/``cpu``/
``cuda``; default ``off`` so stock behavior never changes implicitly):

- ``off``: reference kernels, no torch import.
- ``auto``: torch kernels when torch is importable, else reference.
- ``cpu``: torch kernels on CPU (ImportError surfaces if torch missing).
- ``cuda``: torch kernels on CUDA; falls back to torch-CPU with an
  explicit note when CUDA is unavailable (never fails closed here —
  callers that need hard CUDA should check :func:`accelerator_report`).

torch is an optional dependency: every kernel raises a clear error when
torch cannot be imported, and :func:`accelerator_report` always works.
"""
from __future__ import annotations

import math
import os

try:
    import torch as _torch
except Exception:  # pragma: no cover - exercised when torch is absent
    _torch = None


def torch_available() -> bool:
    return _torch is not None


def cuda_available() -> bool:
    try:
        return bool(_torch is not None and _torch.cuda.is_available())
    except Exception:
        return False


def requested_accelerator() -> str:
    return os.getenv("RIFT_ACCELERATOR", "off").strip().lower() or "off"


def default_accelerator() -> str:
    """Accelerator setting for engine call sites (env-driven, default off)."""
    return requested_accelerator()


def resolve_accelerator(requested: str | None = None) -> dict:
    """Decide whether torch kernels run and on which device.

    Returns ``{"use_torch": bool, "device": "cpu"|"cuda", "note": str}``.
    Never raises for unknown values (falls back to ``off`` with a note).
    """
    want = (requested if requested is not None else requested_accelerator())
    want = (want or "off").strip().lower()
    if want in ("off", "none", "false", "0"):
        return {"use_torch": False, "device": "cpu", "note": "accelerator off (RIFT_ACCELERATOR=off)"}
    if _torch is None:
        return {"use_torch": False, "device": "cpu",
                "note": "torch not importable; reference kernels in use"}
    if want == "cuda":
        if cuda_available():
            return {"use_torch": True, "device": "cuda", "note": "torch CUDA kernels"}
        return {"use_torch": True, "device": "cpu",
                "note": "CUDA requested but unavailable; torch-CPU kernels in use"}
    if want in ("auto", "cpu", "torch", "true", "1"):
        device = "cuda" if cuda_available() else "cpu"
        return {"use_torch": True, "device": device,
                "note": "torch %s kernels" % device}
    return {"use_torch": False, "device": "cpu",
            "note": "unknown RIFT_ACCELERATOR=%r; reference kernels in use" % want}


def accelerator_report() -> dict:
    """Honest status block for /api/meta: what was asked, what is active."""
    resolved = resolve_accelerator()
    return {
        "requested": requested_accelerator(),
        "torch_available": torch_available(),
        "cuda_available": cuda_available(),
        "active": "torch" if resolved["use_torch"] else "reference",
        "device": resolved["device"],
        "note": resolved["note"],
    }


def _require_torch():
    if _torch is None:
        raise ImportError("torch is not installed; set RIFT_ACCELERATOR=off "
                          "or install torch to use accelerated kernels")
    return _torch


def _bit_matrix(n: int, device: str):
    torch = _require_torch()
    if n < 0:
        raise ValueError("negative variable count")
    size = 1 << n
    idx = torch.arange(size, device=device).unsqueeze(1)
    # LSB-first bit order matches reference _energies exactly.
    return ((idx >> torch.arange(n, device=device)) & 1).to(torch.float64)


def torch_energies(qubo, device: str = "cpu") -> list:
    """All 2^n QUBO energies, bitwise-identical to qaoa._energies.

    Vectorized over assignments but sequential over terms, preserving the
    reference summation order (dict insertion order) exactly.
    """
    torch = _require_torch()
    n = len(qubo.variables)
    bits = _bit_matrix(n, device)
    energy = torch.full((1 << n,), float(qubo.offset), dtype=torch.float64, device=device)
    for k, name in enumerate(qubo.variables):
        coefficient = float(qubo.linear.get(name, 0.0))
        if coefficient:
            energy = energy + coefficient * bits[:, k]
    for (left, right), coefficient in (qubo.quadratic or {}).items():
        coefficient = float(coefficient)
        if coefficient:
            energy = energy + coefficient * bits[:, qubo.variables.index(left)] * bits[:, qubo.variables.index(right)]
    return energy.cpu().tolist()


def torch_argmin_product_order(energies: list, n: int, device: str = "cpu") -> int:
    """Index of the minimum under product((0,1)) tie-breaking.

    ``product`` enumerates variable 0 slowest, so the rank of an
    assignment is the bit-reversal of its LSB-first index.
    """
    torch = _require_torch()
    energy = torch.tensor(list(energies), dtype=torch.float64, device=device)
    powers = torch.tensor([2.0 ** (n - 1 - k) for k in range(n)],
                          dtype=torch.float64, device=device)
    bits = _bit_matrix(n, device)
    ranks = bits @ powers
    floor = energy.min()
    candidates = torch.where(energy == floor)[0]
    return int(candidates[ranks[candidates].argmin()].item())


def torch_exact_minimize(qubo, device: str = "cpu"):
    """Exact minimum with reference-identical results (see module docstring)."""
    from .optimizer import OptimizationResult
    n = len(qubo.variables)
    energies = torch_energies(qubo, device=device)
    best = torch_argmin_product_order(energies, n, device=device)
    assignment = {name: ((best >> j) & 1) for j, name in enumerate(qubo.variables)}
    return OptimizationResult(assignment, energies[best], "exact-enumeration")


def torch_qaoa_state(energies: list, n: int, betas, gammas, device: str = "cpu") -> list:
    """QAOA statevector, bitwise-identical to qaoa._state."""
    torch = _require_torch()
    size = 1 << n
    energy = torch.tensor(list(energies), dtype=torch.float64, device=device)
    state = torch.full((size,), 1 / math.sqrt(size), dtype=torch.complex128, device=device)
    for beta, gamma in zip(betas, gammas):
        state = state * torch.exp(torch.complex(torch.zeros(size, dtype=torch.float64, device=device),
                                                -float(gamma) * energy))
        cosine, sine = math.cos(beta), -1j * math.sin(beta)
        for qubit in range(n):
            step = 1 << qubit
            layer = state.reshape(-1, step * 2)
            x = layer[:, :step].clone()
            y = layer[:, step:].clone()
            layer[:, :step] = cosine * x + sine * y
            layer[:, step:] = sine * x + cosine * y
            state = layer.reshape(size)
    return [complex(z) for z in state.cpu().tolist()]
