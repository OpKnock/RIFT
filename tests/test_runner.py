"""Runner invariants: execution, determinism, Guardian honesty, feasibility flags."""

from rift.experiments import validate_spec_payload
from rift.runner import build_scenario, run_spec


def _spec(**overrides):
    payload = {"name": "repro", "scenario": {"crowd": 430.0}}
    payload.update(overrides)
    return validate_spec_payload(payload)


def test_run_spec_exact_shape():
    record = run_spec(_spec())
    assert record["engine_version"] == (__import__("rift").__version__)
    assert record["optimizer"] == "exact"
    assert record["backend"] == "statevector-simulator"
    assert set(record["assignment"]) == {"route_a", "route_c", "stairwell_b"}
    assert record["policies_evaluated"] == 8
    assert record["projection_error"] is None
    assert "guardian" in record and record["guardian"]["scope"].startswith("nominal")
    assert record["duration_ms"] >= 0
    assert len(record["spec_fingerprint"]) == 64


def test_run_spec_deterministic_reproduction():
    spec = _spec(perturbations=[{"smoke": 2.0}], seed=7)
    first = run_spec(spec)
    second = run_spec(spec)
    assert first["spec_fingerprint"] == second["spec_fingerprint"]
    assert first["assignment"] == second["assignment"]
    assert first["robust_cost"] == second["robust_cost"]
    assert first["guardian"] == second["guardian"]


def test_run_spec_qaoa_reports_approximation():
    record = run_spec(_spec(optimizer="qaoa-cvar"))
    assert record["method"] == "qaoa-statevector-simulator"
    assert record["projection_error"] is not None
    assert record["projection_error"]["approximation"] is True


def test_run_spec_guardian_rejects_infeasible_world():
    # A smoke perturbation that pushes every policy into the high-smoke regime.
    record = run_spec(_spec(perturbations=[{"smoke": 20.0}]))
    assert record["feasible"] is False
    assert record["guardian"]["passed"] is False
    assert record["constraint_violations"] >= 1
    violations = [
        violation
        for check in record["guardian"]["checks"]
        for violation in check["violations"]
    ]
    assert any("smoke" in message for message in violations)


def test_build_scenario_rejects_unknown():
    import pytest
    from dataclasses import replace

    spec = _spec()
    with pytest.raises(ValueError):
        build_scenario(replace(spec, scenario_name="nope"))
    with pytest.raises(ValueError):
        build_scenario(replace(spec, initial_state={"warp_drive": 1.0}))
