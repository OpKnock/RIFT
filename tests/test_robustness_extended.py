"""Tests for expanded adversarial robustness + degradation suites."""
import pytest

from rift.health.models import PatientState, PersonalBaseline, EHRRecord
from rift.health.robustness import (
    degrade_missing, degrade_stale, degrade_noisy, degrade_biased,
    degrade_temporal_shift, degrade_correlated_dropout,
    DEGRADATION_SUITES, run_suite, run_all_suites,
)

STATE = PatientState(
    day_index=10, resting_hr=70.0, hrv_rmssd=50.0, sleep_hours=7.0,
    activity_load=0.0, heart_rate=70.0, rr_sd=50.0,
    data_quality=1.0, stale_days=0, provenance="test"
)
BASELINE = PersonalBaseline(resting_hr=69.0, hrv_rmssd=40.0, sleep_hours=7.0, activity_load=0.0)
EHR = EHRRecord(age=58, sex="M", conditions=["hypertension"], medications=[])


def test_all_suites_defined():
    expected = {"sensor_dropout", "stale_data", "sensor_noise",
                "systematic_bias", "temporal_shift", "correlated_dropout",
                "combined_realistic"}
    assert set(DEGRADATION_SUITES) == expected


def test_individual_degradations_preserve_type():
    for fn in (degrade_stale, degrade_noisy,
               degrade_biased, degrade_temporal_shift, degrade_correlated_dropout):
        result = fn(STATE)
        assert isinstance(result, PatientState)
        assert result.day_index == STATE.day_index
    # degrade_missing needs a field argument
    result = degrade_missing(STATE, "resting_hr")
    assert isinstance(result, PatientState)
    assert result.day_index == STATE.day_index


def test_degrade_missing_sets_none():
    s = degrade_missing(STATE, "resting_hr")
    assert s.resting_hr is None
    assert s.hrv_rmssd == STATE.hrv_rmssd


def test_degrade_stale_increases_days():
    s = degrade_stale(STATE, 5)
    assert s.stale_days == 5
    assert s.data_quality == 0.0  # 1.0 - 0.2*5 = 0.0


def test_degrade_noisy_deterministic():
    s1 = degrade_noisy(STATE, seed=7, magnitude=0.1)
    s2 = degrade_noisy(STATE, seed=7, magnitude=0.1)
    assert s1.resting_hr == s2.resting_hr
    assert s1.hrv_rmssd == s2.hrv_rmssd


def test_degrade_biased_applies_bias():
    s = degrade_biased(STATE, seed=9, bias={"resting_hr": 10.0})
    # bias is 10.0 plus small noise (±1%); seed=9 gives ~79.93
    assert abs(s.resting_hr - (STATE.resting_hr + 10.0)) < 0.1


def test_degrade_temporal_shift_changes_hr():
    s = degrade_temporal_shift(STATE, hours=6)
    assert abs(s.resting_hr - STATE.resting_hr) > 0.1


def test_degrade_correlated_dropout_all_or_nothing():
    # Run many times; either all three missing or none
    missing_count = 0
    for seed in range(100):
        s = degrade_correlated_dropout(STATE, seed=seed, p=0.5)
        missing = sum(1 for f in ("resting_hr", "hrv_rmssd", "sleep_hours") if getattr(s, f) is None)
        assert missing in (0, 3), f"seed {seed}: expected 0 or 3 missing, got {missing}"
        if missing == 3:
            missing_count += 1
    assert 30 < missing_count < 70  # ~50% with p=0.5


def test_run_suite_returns_aggregated_metrics():
    result = run_suite(STATE, BASELINE, EHR, "sensor_dropout")
    assert result["suite"] == "sensor_dropout"
    assert result["n_degradations"] == 4
    assert "max_spread" in result
    assert isinstance(result["max_spread"], float)


def test_run_all_suites_covers_all():
    all_results = run_all_suites(STATE, BASELINE, EHR)
    assert set(all_results.keys()) == set(DEGRADATION_SUITES.keys())
    for name, result in all_results.items():
        assert result["suite"] == name
        assert result["n_degradations"] > 0