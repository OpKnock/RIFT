import pytest

from rift.experiments import validate_run_payload, validate_spec_payload


def test_spec_legacy_scenario_shape():
    spec = validate_spec_payload({"name": "lab", "scenario": {"crowd": 100.0}})
    assert spec.name == "lab"
    assert spec.initial_state == {"crowd": 100.0}
    assert spec.scenario_name == "smart-building-emergency"


def test_spec_rejects_bad_inputs():
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "", "scenario": {}})
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "x", "scenario_name": "nope"})
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "x", "perturbations": [{"crowd": "huge"}]})
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "x", "policy_variables": ["a", "a"]})
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "x", "optimizer": "quantum-supremacy"})
    with pytest.raises(ValueError):
        validate_spec_payload({"name": "x", "initial_state": {"crowd": -5}})


def test_spec_fingerprint_deterministic():
    a = validate_spec_payload({"name": "lab", "scenario": {"crowd": 100.0}, "seed": 7})
    b = validate_spec_payload({"name": "lab", "scenario": {"crowd": 100.0}, "seed": 7})
    c = validate_spec_payload({"name": "lab", "scenario": {"crowd": 101.0}, "seed": 7})
    assert a.fingerprint() == b.fingerprint()
    assert a.fingerprint() != c.fingerprint()
    assert len(a.fingerprint()) == 64


def test_run_payload_validation():
    ok = validate_run_payload({"optimizer": "exact", "metrics": {"a": 1}, "seed": 3})
    assert ok["optimizer"] == "exact"
    with pytest.raises(ValueError):
        validate_run_payload({})
    with pytest.raises(ValueError):
        validate_run_payload({"optimizer": "exact", "metrics": []})
