"""Service-level targets and optimizer-outage fallback."""
import pytest

from rift import service_levels as sl
from rift.optimizer import QUBO, exact_minimize

Q = QUBO(("a", "b"), {"a": -2, "b": -1}, {("a", "b"): 3})


def test_slo_targets_declared_as_targets():
    assert sl.RTO_SECONDS == 300
    assert sl.RPO_SECONDS == 60
    assert sl.SLO_AVAILABILITY == 0.999
    assert sl.SLO_P95_LATENCY_MS == 2000.0
    assert sl.SLO_FAILURE_RATE == 0.01
    assert "target-only" in sl.SLO_TARGETS["status"]


def test_exact_primary_needs_no_fallback():
    result = sl.minimize_with_fallback(Q, primary="exact")
    assert result.fallback_used is False
    assert result.primary_error is None
    assert result.energy == exact_minimize(Q).energy


def test_qaoa_primary_succeeds_without_fallback():
    result = sl.minimize_with_fallback(Q, primary="qaoa")
    assert result.fallback_used is False
    assert set(result.assignment) == {"a", "b"}


def test_fallback_runs_on_primary_failure_and_reports():
    def boom():
        raise RuntimeError("backend down")

    def fallback():
        return exact_minimize(Q)

    result, used, error = sl.run_with_fallback(boom, fallback)
    assert used is True
    assert "RuntimeError" in error
    assert result.energy == exact_minimize(Q).energy


def test_unknown_backend_rejected_fail_closed():
    with pytest.raises(ValueError, match="unknown optimizer backend"):
        sl.minimize_with_fallback(Q, primary="quantum-magic")
