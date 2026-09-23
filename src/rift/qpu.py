"""Optional real-QPU QAOA adapter boundary.
Hardware execution stays opt-in and explicit. The simulator remains the default.
"""
from .optimizer import QUBO, OptimizationResult

def qaoa_hardware_available() -> bool:
    try:
        import qiskit
        import qiskit_ibm_runtime
        return True
    except ImportError:
        return False

def solve_on_ibm(qubo: QUBO, backend_name: str, shots: int = 1000) -> OptimizationResult:
    if not qaoa_hardware_available():
        raise RuntimeError("Install rift-engine[qiskit] to enable the optional IBM Quantum adapter.")
    raise NotImplementedError("Hardware execution is intentionally gated until credentials, backend selection, transpilation, sampling, and result validation are configured.")