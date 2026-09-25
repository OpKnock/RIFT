"""Service-level targets and optimizer-outage fallback (Phase 20).

The constants below are declared objectives for an operated deployment, not
measurements. Meeting them requires live infrastructure, load testing, and
incident history — all EXTERNAL (see docs/clinical-roadmap.md phase 20).
In particular RPO_SECONDS cannot be met by the in-memory prospective/review
ledgers; it binds the durable-persistence handoff, not current code.

The fallback path is real code: if the primary optimizer backend raises,
minimization degrades to exact enumeration and the result says so
(fallback_used=True with the primary error attached). Unknown backends are
rejected, never silently substituted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# Target: restore serving within 5 minutes of a failure.
RTO_SECONDS = 300
# Target: lose at most 60 s of ledger writes. Requires durable persistence;
# in-memory ledgers (prospective, reviews) do NOT meet this — stated, not hidden.
RPO_SECONDS = 60
# Target: 99.9% monthly serving availability for the decision-support API.
SLO_AVAILABILITY = 0.999
# Target: interactive p95 latency (stricter than the 5000 ms ops alert).
SLO_P95_LATENCY_MS = 2000.0
# Target: 5xx failure rate (stricter than the 0.10 ops alert).
SLO_FAILURE_RATE = 0.01

SLO_TARGETS = {
    "rto_seconds": RTO_SECONDS,
    "rpo_seconds": RPO_SECONDS,
    "availability": SLO_AVAILABILITY,
    "p95_latency_ms": SLO_P95_LATENCY_MS,
    "failure_rate": SLO_FAILURE_RATE,
    "status": "target-only: unmeasured without operated deployment",
}


@dataclass(frozen=True)
class ResilientResult:
    energy: float
    assignment: dict[str, int]
    method: str
    fallback_used: bool
    primary_error: str | None = None


def run_with_fallback(primary_fn: Callable[[], Any],
                      fallback_fn: Callable[[], Any]) -> tuple[Any, bool, str | None]:
    """Run primary_fn; on any exception run fallback_fn and report the swap."""
    try:
        return primary_fn(), False, None
    except Exception as exc:  # noqa: BLE001 -- fallback must catch everything the backend can raise
        return fallback_fn(), True, f"{type(exc).__name__}: {str(exc)[:200]}"


def minimize_with_fallback(qubo, *, primary: str = "qaoa", **kwargs) -> ResilientResult:
    """Minimize a QUBO with a guaranteed exact-enumeration fallback.

    primary="qaoa" tries the statevector simulator, then falls back to exact.
    primary="exact" uses exact enumeration directly (no fallback possible).
    Any other backend name raises ValueError (fail-closed, no silent default).
    """
    from .optimizer import exact_minimize
    from .qaoa import simulate_qaoa

    if primary == "exact":
        result = exact_minimize(qubo)
        return ResilientResult(result.energy, dict(result.assignment),
                               result.method, False, None)
    if primary == "qaoa":
        def _primary():
            return simulate_qaoa(qubo, **kwargs)

        def _fallback():
            return exact_minimize(qubo)

        result, used, error = run_with_fallback(_primary, _fallback)
        return ResilientResult(result.energy, dict(result.assignment),
                               result.method, used, error)
    raise ValueError(f"unknown optimizer backend {primary!r}; expected 'qaoa' or 'exact'")
