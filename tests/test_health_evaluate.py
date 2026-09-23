"""Phase-3 validation: backtest metrics, calibration, adversarial Guardian.

All bounds below are SOFTWARE regression bounds on synthetic demo data —
they pin current behavior so regressions surface, and must never be read
as clinical performance claims.
"""
import math

from rift.health import guardian as G
from rift.health import robustness as R
from rift.health import ehr as E
from rift.health import risk as K
from rift.health.baseline import personal_baseline
from rift.health.demo_data import demo_stream
from rift.health.evaluate import backtest, counterfactual_sanity
from rift.health.models import EHRRecord, PatientState
from rift.health.twin import DigitalTwin


def _twin():
    ehr, _ = E.normalize_ehr(E.demo_ehr())
    return DigitalTwin(ehr, demo_stream()), ehr


def test_backtest_metrics_are_honest_and_bounded():
    twin, _ = _twin()
    first = backtest(twin, 7, 12)
    assert first["days_evaluated"] == 6
    assert first["mae"]["resting_hr"] is not None and first["mae"]["resting_hr"] < 8.0
    assert first["mae"]["activity_load"] is not None and first["mae"]["activity_load"] < 25.0
    assert all(v is None or math.isfinite(v) for v in first["mae"].values())
    assert 0.0 <= first["brier"] < 0.25
    assert first["interval_coverage"] is not None and first["interval_coverage"] >= 1 / 3
    assert first["event_agreement"] is not None and first["event_agreement"] >= 0.5
    total = sum(first["confusion"].values())
    assert total == 6
    # Deterministic: identical replay replays identical metrics.
    twin2, _ = _twin()
    second = backtest(twin2, 7, 12)
    assert second["mae"] == first["mae"]
    assert second["confusion"] == first["confusion"]


def test_backtest_timing_offset_is_visible_not_hidden():
    twin, _ = _twin()
    report = backtest(twin, 7, 12)
    # The synthetic spell onset lags prediction by a day; the per-day table
    # must expose that instead of aggregating it away.
    assert len(report["per_day"]) == 6
    assert all({"predicted_event", "realized_event"} <= set(d) for d in report["per_day"])


def test_counterfactual_sanity_holds():
    twin, ehr = _twin()
    state = twin.synchronize(10)
    baseline = personal_baseline(twin.stream.observations_upto(10))
    result = counterfactual_sanity(state, baseline, ehr)
    assert result["all_improve_or_equal"] is True


def test_missing_fields_degrade_monotonically():
    twin, ehr = _twin()
    state = twin.synchronize(10)
    baseline = personal_baseline(twin.stream.observations_upto(10))
    qualities, uncertainties = [], []
    current = state
    for field in ("hrv_rmssd", "sleep_hours", "activity_load"):
        current = R.degrade_missing(current, field)
        record = K.predict(current, baseline, ehr)
        qualities.append(K.input_quality(current))
        uncertainties.append(record["uncertainty"])
    assert qualities == sorted(qualities, reverse=True)
    assert uncertainties == sorted(uncertainties)
    assert qualities[-1] < 0.6  # visibly degraded, Guardian flags downstream


def test_guardian_adversarial_cases():
    twin, ehr = _twin()
    base_state = PatientState(day_index=1, resting_hr=70.0, hrv_rmssd=45.0,
                              sleep_hours=7.0, activity_load=40.0)
    base_risk = K.predict(base_state, personal_baseline(demo_stream().observations_upto(6)), ehr)
    # NaN is impossible, not missing.
    nan_state = PatientState(day_index=1, resting_hr=float("nan"), hrv_rmssd=45.0,
                             sleep_hours=7.0, activity_load=40.0)
    assert G.verdict(nan_state, base_risk)["display_allowed"] is False
    # Pediatric patient is out of the adult demo scope.
    child_ehr = EHRRecord(patient_id="demo-child", age=10.0)
    assert any("out-of-distribution" in f for f in G.verdict(base_state, base_risk, ehr=child_ehr)["flags"])
    assert G.verdict(base_state, base_risk, ehr=ehr)["display_allowed"] is True
    # Extreme staleness flags but a complete fresh state stays clean.
    ancient = PatientState(day_index=30, resting_hr=70.0, hrv_rmssd=45.0,
                           sleep_hours=7.0, activity_load=40.0, stale_days=30)
    assert G.verdict(ancient, base_risk)["flags"]
    # Negative HRV is impossible.
    negative = PatientState(day_index=1, resting_hr=70.0, hrv_rmssd=-5.0,
                            sleep_hours=7.0, activity_load=40.0)
    assert G.verdict(negative, base_risk)["display_allowed"] is False
