import pytest

from rift import limits


def test_policy_variable_limits():
    with pytest.raises(ValueError):
        limits.check_policy_variables(())
    with pytest.raises(ValueError):
        limits.check_policy_variables(["a", "a"])
    with pytest.raises(ValueError):
        limits.check_policy_variables([f"v{i}" for i in range(limits.MAX_POLICY_VARIABLES + 1)])


def test_perturbation_limits():
    with pytest.raises(ValueError):
        limits.check_perturbations([{"a": 1.0}] * (limits.MAX_PERTURBATIONS + 1))
    with pytest.raises(ValueError):
        limits.check_perturbations([{"a": "bad"}])
    limits.check_perturbations([{"crowd": 1.0}])


def test_scenario_bounds_reject_not_clamp():
    with pytest.raises(ValueError):
        limits.check_scenario_state({"crowd": -1})
    with pytest.raises(ValueError):
        limits.check_scenario_state({"smoke": 99})
    limits.check_scenario_state({"crowd": 100.0, "smoke": 3.0})


def test_describe_limits_shape():
    info = limits.describe_limits()
    assert info["max_qubo_variables"] == 12
    assert "crowd" in info["scenario_bounds"]
