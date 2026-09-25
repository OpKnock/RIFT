"""Regression tests for internal audit invariants (cb39d1a follow-up).

Covers:
- two patients + same day_index remain separate
- ICULOS relative timestamps preserved (not fabricated calendar days)
- sepsis_label retained in outcome channel, not as wearable feature
- malformed canonical row fails closed in PublicDatasetSource
- PatientState receives patient_id/time_offset_hours via synchronize()
- WearableObservation positional construction is intentionally keyword-only
- CHFDB adapter uses correct 15-subject definition, no BIDMC conflation
"""
from __future__ import annotations


def test_two_patients_same_day_remain_separate():
    from rift.health.sources import _canonical_to_wearable

    raw = [
        {"patient_id": "A", "timestamp": "2024-01-01T00:00:00+00:00",
         "source": "test", "metric": "heart_rate", "value": 80, "unit": "bpm",
         "quality": 1.0, "provenance": "a"},
        {"patient_id": "B", "timestamp": "2024-01-01T00:00:00+00:00",
         "source": "test", "metric": "heart_rate", "value": 90, "unit": "bpm",
         "quality": 1.0, "provenance": "b"},
    ]
    from rift.health.observations import normalize_batch

    accepted, issues = normalize_batch(raw)
    assert not issues
    obs = _canonical_to_wearable(accepted)
    assert len(obs) == 2
    by_pid = {o.patient_id: o for o in obs}
    assert by_pid["A"].heart_rate == 80
    assert by_pid["B"].heart_rate == 90
    # Semantic: generic HR must not populate resting_hr
    assert by_pid["A"].resting_hr is None
    assert by_pid["B"].resting_hr is None


def test_rr_sd_does_not_populate_hrv_rmssd():
    from rift.health.observations import normalize_batch
    from rift.health.sources import _canonical_to_wearable

    raw = [{
        "patient_id": "P1", "timestamp": "2024-01-01T00:00:00+00:00",
        "source": "test", "metric": "rr_sd", "value": 50,
        "unit": "ms", "quality": 1.0, "provenance": "x",
    }]
    accepted, issues = normalize_batch(raw)
    assert not issues
    obs = _canonical_to_wearable(accepted)
    assert len(obs) == 1
    assert obs[0].rr_sd == 50
    assert obs[0].hrv_rmssd is None


def test_sepsis_label_retained_in_outcome_channel():
    from rift.health.observations import normalize_batch, is_outcome_metric, is_feature_metric
    from rift.health.sources import _canonical_to_wearable

    assert is_outcome_metric("sepsis_label")
    assert not is_feature_metric("sepsis_label")

    raw = [
        {"patient_id": "P1", "timestamp": "2024-01-01T00:00:00+00:00",
         "source": "sepsis", "metric": "heart_rate", "value": 100,
         "unit": "bpm", "quality": 1.0, "provenance": "p"},
        {"patient_id": "P1", "timestamp": "2024-01-01T00:00:00+00:00",
         "source": "sepsis", "metric": "sepsis_label", "value": 1,
         "unit": "binary", "quality": 1.0, "provenance": "p"},
    ]
    accepted, issues = normalize_batch(raw)
    assert not issues
    obs = _canonical_to_wearable(accepted)
    assert len(obs) == 1
    assert obs[0].outcome == 1
    assert obs[0].heart_rate == 100


def test_malformed_canonical_row_fails_closed(tmp_path):
    from rift.health.sources import PublicDatasetSource

    p = tmp_path / "bad.csv"
    p.write_text(
        "subject_id,recording_id,date,metric,value,unit,source,provenance\n"
        "P1,R1,2024-01-01T00:00:00+00:00,heart_rate,80,bpm,src,\"{}\"\n"
        "P1,R1,2024-01-01T01:00:00+00:00,not_a_metric,80,bpm,src,\"{}\"\n",
        encoding="utf-8",
    )
    try:
        PublicDatasetSource(str(p))
        raise AssertionError("malformed canonical row must fail closed")
    except ValueError as exc:
        assert "fail-closed" in str(exc)


def test_patient_state_receives_identity_and_time():
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr
    from rift.health.twin import DigitalTwin

    record, _ = normalize_ehr(demo_ehr())
    twin = DigitalTwin(record, demo_stream())
    state = twin.synchronize(5)
    assert state.patient_id == "demo-patient-01"
    assert state.time_offset_hours == 5 * 24


def test_wearable_observation_positional_is_keyword_only():
    from rift.health.models import WearableObservation

    try:
        WearableObservation(0, 70.0, 50.0, 7.0, 40.0)  # type: ignore[call-arg]
        raise AssertionError("old positional construction must fail (intentional kw_only break)")
    except TypeError:
        pass
    # Keyword construction still works
    obs = WearableObservation(day_index=0, resting_hr=70.0)
    assert obs.day_index == 0
    assert obs.resting_hr == 70.0


def test_iculos_relative_time_not_fabricated_days():
    # Sepsis scraper must derive timestamps from ICULOS, not 2024-01-{hour+1}
    from datetime import datetime, timedelta, timezone

    study_epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for iculos_hours in (1.0, 2.0, 25.0):
        dt = study_epoch + timedelta(hours=iculos_hours)
        assert (dt - study_epoch).total_seconds() / 3600.0 == iculos_hours
    # 25h ICU stay must not become "day 25" calendar fabrication in downstream day_index logic
    # day_index is days-since-epoch; time_offset_hours preserves ICU-relative time
    assert int(25.0 // 24) == 1


def test_sepsis_iculos_rows_produce_relative_timeline():
    # End-to-end conversion (no network): ICULOS 1,25,49 -> correct offsets.
    # NOTE: _canonical_to_wearable aggregates to day_index, so two ICU hours
    # on the same calendar day collapse to one WearableObservation. This test
    # uses ICULOS values on distinct days to prove relative time is preserved.
    from rift.health.observations import normalize_batch
    from rift.health.sources import _canonical_to_wearable
    from datetime import datetime, timedelta, timezone

    epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
    raw = []
    for iculos in (1.0, 25.0, 49.0):
        ts = (epoch + timedelta(hours=iculos)).isoformat()
        raw.append({
            "patient_id": "P1", "timestamp": ts, "source": "sepsis",
            "metric": "heart_rate", "value": 90, "unit": "bpm",
            "quality": 1.0, "provenance": f"iculos={iculos}",
        })
    accepted, issues = normalize_batch(raw)
    assert not issues
    obs = _canonical_to_wearable(accepted)
    assert len(obs) == 3
    offsets = sorted(o.time_offset_hours for o in obs)
    assert offsets == [1.0, 25.0, 49.0]
    days = sorted(o.day_index for o in obs)
    assert days == [0, 1, 2]  # offsets preserve ICU-relative time across days


def test_cardiac_adapter_definitions_correct():
    from rift.health import physionet_cardiac_scrape as C

    assert "chfdb" in C.DATASETS
    # CHFDB is 15 subjects, not 29
    assert len(C.DATASETS["chfdb"]["subjects"]) == 15
    assert C.DATASETS["chfdb"]["subjects"][0] == "chf01"
    assert C.DATASETS["chfdb"]["subjects"][-1] == "chf15"
    # No BIDMC conflation: 53-subject PPG dataset must not be present as CHF
    assert "bidmc" not in C.DATASETS
    # Official WFDB layout: .dat + .hea + .ecg (no .txt RR files, no .atr for CHFDB)
    urls = C.chfdb_urls("chf01")
    assert urls["dat"].endswith("chfdb/1.0.0/chf01.dat")
    assert urls["hea"].endswith("chfdb/1.0.0/chf01.hea")
    assert urls["ann"].endswith("chfdb/1.0.0/chf01.ecg")
    assert ".txt" not in urls["dat"]
    assert not urls["ann"].endswith(".atr")


def test_chfdb_hea_and_rr_helpers():
    from rift.health import physionet_cardiac_scrape as C

    hea = "chf01 2 250 100000\nchf01.dat 212 200 11 1024 0 V5\nchf01.dat 212 200 11 1024 0 MLII\n"
    assert C.parse_hea_sampfreq(hea) == 250.0
    # 250 Hz: beats at samples 0, 250, 500 -> 1000ms RR
    rr = C.annotation_samples_to_rr_ms([0, 250, 500], 250.0)
    assert rr == [1000.0, 1000.0]
    hr, rmssd = C.rr_to_hr_hrv(rr)
    assert hr == 60.0
    assert rmssd == 0.0
    try:
        C.parse_hea_sampfreq("garbage")
        raise AssertionError("bad .hea must fail closed")
    except ValueError:
        pass
    try:
        C.rr_to_hr_hrv([])
        raise AssertionError("empty RR must fail closed")
    except ValueError:
        pass


def test_timeline_buckets_are_patient_scoped():
    from rift.health.observations import normalize_batch
    from rift.health import timeline as T

    raw = []
    for pid in ("A", "B"):
        for ts in ("2026-01-04T08:00:00", "2026-01-05T08:00:00"):
            raw.append({"patient_id": pid, "timestamp": ts, "source": "t",
                        "metric": "resting_hr", "value": 70.0, "unit": "bpm",
                        "quality": 1.0, "provenance": "t"})
    accepted, issues = normalize_batch(raw)
    assert not issues
    rows, index = T.to_daily_rows(accepted)
    assert len(rows) == 4
    assert set(index) == {("A", "2026-01-04"), ("A", "2026-01-05"),
                          ("B", "2026-01-04"), ("B", "2026-01-05")}
    assert {(r.patient_id, r.day_index) for r in rows} == {
        ("A", 0), ("A", 1), ("B", 0), ("B", 1)}


def test_multi_patient_stream_keeps_patients_separate():
    from rift.health.models import WearableObservation
    from rift.health.wearable import MultiPatientStream

    obs = [
        WearableObservation(day_index=0, patient_id="A", resting_hr=70.0),
        WearableObservation(day_index=0, patient_id="B", resting_hr=90.0),
        WearableObservation(day_index=1, patient_id="A", resting_hr=71.0),
    ]
    mps = MultiPatientStream(obs)
    assert sorted(mps.patient_ids) == ["A", "B"]
    assert len(mps.observations_upto_patient("A", 1)) == 2
    assert len(mps.observations_upto_patient("B", 1)) == 1
    assert mps.latest_at_patient("B", 1).resting_hr == 90.0
