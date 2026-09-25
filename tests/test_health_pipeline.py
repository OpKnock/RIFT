"""Healthcare pipeline tests: EHR, wearable replay, baseline, transition, twin."""
from rift.health import baseline as B
from rift.health import ehr as E
from rift.health import transition as T
from rift.health import wearable as W
from rift.health.demo_data import demo_stream
from rift.health.models import WearableObservation
from rift.health.twin import DigitalTwin


def _ehr():
    record, _ = E.normalize_ehr(E.demo_ehr())
    return record


def test_ehr_normalization_valid_and_invalid():
    record, issues = E.normalize_ehr(E.demo_ehr())
    assert record.age == 58.0 and "hypertension" in record.conditions and not issues
    record, issues = E.normalize_ehr({"age": "old", "conditions": ["unknown_x"]})
    assert record.age is None and len(issues) >= 2
    record, issues = E.normalize_ehr(None)
    assert issues and record.age is None


def test_wearable_replay_and_staleness():
    stream = demo_stream()
    assert stream.start_day == 0 and stream.end_day == 13
    assert len(stream.observations_upto(5)) == 6
    assert stream.latest_at(13).day_index == 13
    assert stream.stale_days_at(6) == 1  # partial sample: last fully-real sample is day 5
    assert 0.0 < stream.completeness_at(6) < 1.0  # HRV missing
    assert stream.completeness_at(5) == 1.0
    try:
        W.WearableStream([WearableObservation(day_index=1), WearableObservation(day_index=1)])
        raise AssertionError("duplicate days must be rejected")
    except ValueError:
        pass


def test_personal_baseline_excludes_stale_and_partials():
    obs = [
        WearableObservation(day_index=0, resting_hr=70.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0),
        WearableObservation(day_index=1, resting_hr=200.0, hrv_rmssd=5.0, sleep_hours=1.0, activity_load=190.0, stale=True),
        WearableObservation(day_index=2, resting_hr=72.0, hrv_rmssd=None, sleep_hours=7.5, activity_load=42.0),
    ]
    base = B.personal_baseline(obs, window=7)
    assert base.resting_hr == 71.0  # median of real samples only
    assert base.hrv_rmssd == 50.0  # partial sample's None excluded per-field
    assert base.window_days == 2  # stale sample excluded; partial counts as real


def test_personal_baseline_window_counts_real_samples():
    obs = [WearableObservation(day_index=d, resting_hr=70.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0) for d in range(5)]
    assert B.personal_baseline(obs, window=7).window_days == 5


def test_deviations_directions():
    from rift.health.models import PersonalBaseline

    base = PersonalBaseline(resting_hr=70.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0, window_days=5)
    cur = WearableObservation(day_index=9, resting_hr=75.0, hrv_rmssd=40.0, sleep_hours=5.0, activity_load=80.0)
    devs = {d.field: d for d in B.deviations(cur, base)}
    assert devs["resting_hr"].direction == "above" and devs["resting_hr"].delta == 5.0
    assert devs["hrv_rmssd"].direction == "below"
    assert B.deviations(None, base)[0].direction == "unknown"


def test_transition_bounded_and_explicit():
    ehr = _ehr()
    nxt = T.transition({"resting_hr": 70.0, "hrv_rmssd": 45.0, "sleep_hours": 4.0, "activity_load": 90.0}, ehr, {})
    assert 35.0 <= nxt["resting_hr"] <= 200.0
    assert nxt["resting_hr"] > 70.0  # sleep debt + exertion raise HR
    assert nxt["hrv_rmssd"] < 45.0
    calm = T.transition({"resting_hr": 70.0, "hrv_rmssd": 45.0, "sleep_hours": 8.0, "activity_load": 30.0}, ehr, {})
    assert calm["resting_hr"] <= 70.0
    helped = T.transition({"resting_hr": 70.0, "hrv_rmssd": 45.0, "sleep_hours": 8.0, "activity_load": 90.0}, ehr, {"sleep_plus": 0, "exertion_cut": 1})
    assert helped["activity_load"] == 55.0
    missing = T.transition({"resting_hr": None, "hrv_rmssd": 45.0, "sleep_hours": 7.0, "activity_load": 40.0}, ehr, {})
    assert missing["resting_hr"] is None and missing["hrv_rmssd"] is not None
    assert set(T.TRANSITION_WEIGHTS) and set(T.INTERVENTIONS) == {"sleep_plus", "exertion_cut"}


def test_twin_update_loop_and_replay():
    twin = DigitalTwin(_ehr(), demo_stream())
    snap = twin.update(10)
    assert snap["day_index"] == 10
    assert snap["risk"]["event_predicted"] is True  # demo spell peaks
    assert snap["guardian"]["display_allowed"] is True
    assert len(snap["reasons"]) >= 3
    assert len(snap["trajectories"]) == 4  # one per policy
    assert all(len(t["path"]) == 4 for t in snap["trajectories"])  # day0 + 3-day horizon
    assert twin.history and twin.history[-1]["day_index"] == 10
    fresh = DigitalTwin(_ehr(), demo_stream())
    assert len(fresh.replay(0, 3)) == 4
    # Deterministic: same day, fresh twin => identical risk/assignment core
    again = DigitalTwin(_ehr(), demo_stream()).update(10)
    assert again["risk"]["risk"] == snap["risk"]["risk"]
    assert again["state"] == snap["state"]


def test_baseline_excludes_current_day_no_leakage():
    """An abnormal today must not redefine today's baseline (forecasting hygiene)."""
    twin = DigitalTwin(_ehr(), demo_stream())
    snap = twin.update(10)
    assert snap["baseline"]["resting_hr"] != snap["state"]["resting_hr"]
    # Baseline for day 10 may only use days < 10.
    assert snap["baseline"]["window_days"] <= 7
    prior_only = [o for o in demo_stream().observations_upto(10) if o.day_index < 10]
    assert snap["baseline"]["window_days"] == min(7, len([o for o in prior_only if not o.stale]))
    # Day 0 cold start: empty baseline, documented fallback path.
    cold = DigitalTwin(_ehr(), demo_stream()).update(0)
    assert cold["baseline"]["resting_hr"] is None
    assert cold["risk"]["risk"] is not None


def test_live_ingest_source_same_pipeline():
    """LiveIngestSource feeds the identical twin pipeline as replay."""
    from rift.health.sources import LiveIngestSource, ReplaySource, WearableSource

    live = LiveIngestSource()
    assert isinstance(live, WearableSource)
    assert live.start_day is None
    for obs in demo_stream().observations_upto(5):
        live.ingest(obs)
    assert live.buffered_days == 6 and live.end_day == 5
    twin = DigitalTwin(_ehr(), live)
    snap = twin.update(5)
    replayed = DigitalTwin(_ehr(), ReplaySource(demo_stream().observations_upto(5))).update(5)
    assert snap["risk"]["risk"] == replayed["risk"]["risk"]
    assert snap["state"] == replayed["state"]
    try:
        live.ingest(demo_stream().observations_upto(3)[-1])
        raise AssertionError("time-travel ingest must be rejected")
    except ValueError:
        pass
    try:
        live.ingest(live.latest_at(5))
        raise AssertionError("duplicate-day ingest must be rejected")
    except ValueError:
        pass
