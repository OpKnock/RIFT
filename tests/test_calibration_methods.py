"""Tests for calibration methods: Platt, Isotonic, Beta."""
import pytest

from rift.health.evaluate import (
    fit_platt_scaling, apply_platt,
    fit_isotonic_regression, apply_isotonic,
    fit_beta_calibration, apply_beta,
    calibration_report,
)

CAL_DAYS = [
    {"predicted_risk": 0.1, "realized_event": False},
    {"predicted_risk": 0.2, "realized_event": False},
    {"predicted_risk": 0.3, "realized_event": False},
    {"predicted_risk": 0.4, "realized_event": True},
    {"predicted_risk": 0.5, "realized_event": True},
    {"predicted_risk": 0.6, "realized_event": True},
    {"predicted_risk": 0.7, "realized_event": True},
    {"predicted_risk": 0.8, "realized_event": True},
    {"predicted_risk": 0.9, "realized_event": True},
]

TEST_DAYS = [
    {"predicted_risk": 0.15, "realized_event": False},
    {"predicted_risk": 0.35, "realized_event": True},
    {"predicted_risk": 0.55, "realized_event": True},
    {"predicted_risk": 0.85, "realized_event": True},
]


def test_platt_scaling_fits_and_applies():
    params = fit_platt_scaling(CAL_DAYS)
    assert "a" in params and "b" in params
    p = apply_platt(0.5, params)
    assert 0.0 <= p <= 1.0


def test_isotonic_regression_fits_and_applies():
    params = fit_isotonic_regression(CAL_DAYS)
    assert "raw_probs" in params and "fitted" in params
    p = apply_isotonic(0.5, params)
    assert 0.0 <= p <= 1.0


def test_isotonic_preserves_order():
    params = fit_isotonic_regression(CAL_DAYS)
    # Isotonic should be monotonic
    fitted = params["fitted"]
    for i in range(1, len(fitted)):
        assert fitted[i] >= fitted[i - 1] - 1e-9


def test_beta_calibration_fits_and_applies():
    params = fit_beta_calibration(CAL_DAYS)
    assert "a" in params and "b" in params and "c" in params
    p = apply_beta(0.5, params)
    assert 0.0 <= p <= 1.0


def test_calibration_report_all_methods():
    report = calibration_report(CAL_DAYS, TEST_DAYS, methods=("platt", "isotonic", "beta"))
    assert "methods" in report
    for m in ("platt", "isotonic", "beta"):
        assert m in report["methods"]
        assert "raw" in report["methods"][m]
        assert "calibrated" in report["methods"][m]


def test_calibration_unknown_method_raises():
    with pytest.raises(ValueError, match="unknown calibration method"):
        calibration_report(CAL_DAYS, TEST_DAYS, methods=("platt", "unknown"))


def test_isotonic_monotonic_on_noisy_data():
    """Isotonic should handle non-monotonic input and produce monotonic output."""
    noisy = [
        {"predicted_risk": 0.1, "realized_event": False},
        {"predicted_risk": 0.2, "realized_event": True},   # anomaly
        {"predicted_risk": 0.3, "realized_event": False},  # anomaly
        {"predicted_risk": 0.4, "realized_event": True},
        {"predicted_risk": 0.5, "realized_event": True},
        {"predicted_risk": 0.6, "realized_event": True},
        {"predicted_risk": 0.7, "realized_event": True},
        {"predicted_risk": 0.8, "realized_event": True},
        {"predicted_risk": 0.9, "realized_event": True},
    ]
    params = fit_isotonic_regression(noisy)
    fitted = params["fitted"]
    for i in range(1, len(fitted)):
        assert fitted[i] >= fitted[i - 1] - 1e-9


def test_beta_applies_to_edges():
    params = fit_beta_calibration(CAL_DAYS)
    p0 = apply_beta(0.001, params)
    p1 = apply_beta(0.999, params)
    assert 0.0 < p0 < 1.0
    assert 0.0 < p1 < 1.0


def test_empty_calibration_raises():
    with pytest.raises(ValueError):
        fit_platt_scaling([])
    with pytest.raises(ValueError):
        fit_isotonic_regression([])
    with pytest.raises(ValueError):
        fit_beta_calibration([])


def test_single_observation_calibration():
    single = [{"predicted_risk": 0.5, "realized_event": True}]
    params = fit_platt_scaling(single)
    p = apply_platt(0.5, params)
    assert 0.0 <= p <= 1.0
    params_iso = fit_isotonic_regression(single)
    p = apply_isotonic(0.5, params_iso)
    assert 0.0 <= p <= 1.0
    params_beta = fit_beta_calibration(single)
    p = apply_beta(0.5, params_beta)
    assert 0.0 <= p <= 1.0


def test_identical_probabilities_calibration():
    identical = [
        {"predicted_risk": 0.5, "realized_event": False},
        {"predicted_risk": 0.5, "realized_event": True},
        {"predicted_risk": 0.5, "realized_event": True},
    ]
    params = fit_isotonic_regression(identical)
    # All identical raw probs should map to single fitted value
    assert len(params["raw_probs"]) == 1
    assert len(params["fitted"]) == 1
    p = apply_isotonic(0.5, params)
    assert p == params["fitted"][0]


def test_extreme_probabilities_calibration():
    extreme = [
        {"predicted_risk": 0.001, "realized_event": False},
        {"predicted_risk": 0.01, "realized_event": False},
        {"predicted_risk": 0.99, "realized_event": True},
        {"predicted_risk": 0.999, "realized_event": True},
    ]
    params = fit_platt_scaling(extreme)
    p0 = apply_platt(0.001, params)
    p1 = apply_platt(0.999, params)
    assert 0.0 < p0 < p1 < 1.0
    params_iso = fit_isotonic_regression(extreme)
    p0 = apply_isotonic(0.001, params_iso)
    p1 = apply_isotonic(0.999, params_iso)
    assert 0.0 <= p0 <= p1 <= 1.0
    params_beta = fit_beta_calibration(extreme)
    p0 = apply_beta(0.001, params_beta)
    p1 = apply_beta(0.999, params_beta)
    assert 0.0 < p0 < p1 < 1.0


def test_isotonic_empty_raw_probs():
    params = fit_isotonic_regression([{"predicted_risk": 0.5, "realized_event": True}])
    # apply_isotonic with p outside range should clamp
    p_low = apply_isotonic(0.0, params)
    p_high = apply_isotonic(1.0, params)
    assert p_low == params["fitted"][0]
    assert p_high == params["fitted"][0]