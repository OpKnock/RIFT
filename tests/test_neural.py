"""Neural state estimation: MLP surrogates learn scenario transitions.

Surrogates train on deterministic rollouts, predict with hull-based
abstention, and never touch the clinical twin path.
"""
import pytest

np = pytest.importorskip("numpy")

from rift.domains.powergrid.domain import create_powergrid_scenario
from rift.domains.traffic.domain import create_traffic_scenario
from rift.neural import (
    MLPRegressor,
    fit_world_estimator,
    predict_with_estimator,
    rollout_dataset,
)


def _policies_grid():
    return [
        {"load_shed_ratio": 0.0, "peaker_dispatch": 0.0},
        {"load_shed_ratio": 0.1, "peaker_dispatch": 0.5},
        {"load_shed_ratio": 0.2, "peaker_dispatch": 1.0},
        {"load_shed_ratio": 0.05, "peaker_dispatch": 0.25},
    ]


def test_rollout_dataset_shapes_and_determinism():
    scenario = create_powergrid_scenario()
    x1, y1, sk1, pk1 = rollout_dataset(scenario, _policies_grid(), steps=4)
    x2, y2, sk2, pk2 = rollout_dataset(scenario, _policies_grid(), steps=4)
    assert x1.shape == (16, 7) and y1.shape == (16, 5)
    assert (x1 == x2).all() and (y1 == y2).all()
    assert sk1 == sk2 == sorted(scenario.initial_state.keys())


def test_mlp_deterministic_weights():
    a = MLPRegressor((4, 8, 2), seed=11)
    b = MLPRegressor((4, 8, 2), seed=11)
    for wa, wb in zip(a.weights, b.weights):
        assert (wa == wb).all()


def test_surrogate_learns_powergrid_transition():
    scenario = create_powergrid_scenario()
    bundle = fit_world_estimator(scenario, _policies_grid(), seed=7, iterations=300)
    # Must beat the naive baseline (predicting the mean next state).
    x_raw, y_raw, _, _ = rollout_dataset(scenario, _policies_grid())
    baseline = float(((y_raw - y_raw.mean(axis=0)) ** 2).mean())
    assert bundle["train_mse"] < baseline * 0.5
    assert bundle["train_rows"] == 24
    assert bundle["scenario_name"] == "powergrid-emergency"


def test_surrogate_learns_traffic_transition():
    from rift.domains.traffic.domain import TRAFFIC_PERTURBATIONS  # noqa: F401
    scenario = create_traffic_scenario()
    policies = [{"green_time_ratio": 0.3, "cycle_length": 60.0},
                {"green_time_ratio": 0.6, "cycle_length": 120.0}]
    bundle = fit_world_estimator(scenario, policies, seed=7, iterations=300)
    x_raw, y_raw, _, _ = rollout_dataset(scenario, policies)
    baseline = float(((y_raw - y_raw.mean(axis=0)) ** 2).mean())
    assert bundle["train_mse"] < baseline * 0.5


def test_neural_prediction_matches_analytical_near_data():
    scenario = create_powergrid_scenario()
    bundle = fit_world_estimator(scenario, _policies_grid(), seed=7, iterations=400)
    state = dict(scenario.initial_state)
    policy = {"load_shed_ratio": 0.1, "peaker_dispatch": 0.5}
    out = predict_with_estimator(bundle, scenario, state, policy)
    assert out["source"] == "neural"
    assert out["abstained"] is False
    truth = scenario.transition(dict(state), dict(policy))
    for key, value in out["prediction"].items():
        assert abs(value - truth[key]) < max(1.0, abs(truth[key]) * 0.05)
    assert out["provenance"]["estimator"] == "mlp-surrogate"


def test_abstention_far_from_training_hull():
    scenario = create_powergrid_scenario()
    bundle = fit_world_estimator(scenario, _policies_grid(), seed=7, iterations=200)
    far_state = {"demand_mw": 1999.0, "supply_mw": 1.0, "frequency_hz": 45.0,
                 "reserve_pct": 0.0, "shed_mw": 599.0}
    out = predict_with_estimator(bundle, scenario, far_state,
                                 {"load_shed_ratio": 0.3, "peaker_dispatch": 1.0})
    assert out["source"] == "analytical-fallback"
    assert out["abstained"] is True
    assert out["distance"] > out["abstain_distance"]


def test_fallback_equals_analytical_transition():
    scenario = create_powergrid_scenario()
    bundle = fit_world_estimator(scenario, _policies_grid(), seed=7, iterations=100)
    bundle = dict(bundle, abstain_distance=-1.0)  # force abstention
    state = dict(scenario.initial_state)
    policy = {"load_shed_ratio": 0.0, "peaker_dispatch": 0.0}
    out = predict_with_estimator(bundle, scenario, state, policy)
    truth = scenario.transition(dict(state), dict(policy))
    assert out["prediction"] == {k: float(truth[k]) for k in bundle["state_keys"]}


def test_mlp_rejects_bad_shapes():
    model = MLPRegressor((2, 4, 1), seed=1)
    with pytest.raises(ValueError):
        model.fit([[1.0]], [[1.0, 2.0]])
    with pytest.raises(ValueError):
        MLPRegressor((4, 2), seed=1)
