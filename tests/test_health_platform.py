"""v1 data platform + registry + decision tests: adapters, timeline, provenance, gates.

Bounds pin honest behavior (validation, determinism, no invention), never
clinical quality. Unit conversions and registry pins are exact by design.
"""
from rift.health import adapters as A
from rift.health import timeline as T
from rift.health.decision import decision_table
from rift.health.model_registry import (
    DEFAULT_MODEL_ID,
    deployment_gate,
    get_model,
    verify_weights,
    weights_digest,
)
from rift.health.models import WearableObservation
from rift.health.observations import normalize_batch, validate_observation
from rift.health.sources import LiveIngestSource
from rift.health.twin import DigitalTwin, prediction_provenance


def _raw(patient="p1", patient_id=None, metric="resting_hr", value=70.0, unit="bpm",
         timestamp="2026-01-04T08:04:00", source="test", quality=1.0):
    return {"patient_id": patient if patient_id is None else patient_id, "timestamp": timestamp, "source": source,
            "metric": metric, "value": value, "unit": unit, "quality": quality,
            "provenance": "unit-test"}


def test_observation_validation_and_unit_conversion():
    obs, issues = validate_observation(_raw())
    assert obs is not None and not issues
    assert obs.value == 70.0 and obs.unit == "bpm"
    obs, _ = validate_observation(_raw(metric="hrv_rmssd", value=0.045, unit="s"))
    assert obs.value == 45.0 and obs.unit == "ms"
    obs, _ = validate_observation(_raw(metric="sleep_hours", value=30.0, unit="min"))
    assert abs(obs.value - 0.5) < 1e-9 and obs.unit == "h"
    assert validate_observation(_raw(metric="glucose"))[0] is None
    assert validate_observation(_raw(unit="furlongs"))[0] is None
    assert validate_observation(_raw(timestamp="yesterday"))[0] is None
    assert validate_observation(_raw(value="fast"))[0] is None
    assert validate_observation(_raw(patient_id="  "))[0] is None
    assert validate_observation("nope")[0] is None
    accepted, issues = normalize_batch([_raw(), _raw(metric="nope"), "junk"])
    assert len(accepted) == 1 and len(issues) == 2


def test_timeline_buckets_median_and_index():
    obs, _ = normalize_batch([
        _raw(timestamp="2026-01-04T08:04:00", metric="resting_hr", value=70.0),
        _raw(timestamp="2026-01-04T18:00:00", metric="resting_hr", value=74.0),
        _raw(timestamp="2026-01-05T08:00:00", metric="resting_hr", value=72.0),
    ])
    buckets = T.bucket_by_day(obs)
    assert sorted(buckets) == ["2026-01-04", "2026-01-05"]
    assert T.estimate_day(buckets["2026-01-04"])["resting_hr"] == 72.0
    assert T.estimate_day(buckets["2026-01-04"])["hrv_rmssd"] is None
    rows, index = T.to_daily_rows(obs)
    assert index == {"2026-01-04": 0, "2026-01-05": 1}
    assert rows[0].day_index == 0 and rows[0].resting_hr == 72.0
    assert T.day_quality([]) == 0.0


def test_timeline_feeds_twin_unchanged():
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr
    from rift.health.sources import ReplaySource

    raw = [{"patient_id": "demo-patient-01", "timestamp": f"2026-01-{d:02d}T08:00:00",
            "source": "csv", "metric": f, "value": v, "unit": u, "quality": 1.0, "provenance": "t"}
           for d, (hr, hrv, sl, ac) in {
               4: (70.0, 50.0, 7.0, 40.0), 5: (71.0, 49.0, 7.1, 42.0),
           }.items()
           for f, v, u in (("resting_hr", hr, "bpm"), ("hrv_rmssd", hrv, "ms"),
                           ("sleep_hours", sl, "h"), ("activity_load", ac, "index"))]
    accepted, issues = normalize_batch(raw)
    assert not issues and len(accepted) == 8
    rows, index = T.to_daily_rows(accepted)
    assert index == {"2026-01-04": 0, "2026-01-05": 1}
    ehr, _ = normalize_ehr(demo_ehr())
    snap = DigitalTwin(ehr, ReplaySource(rows)).update(1)
    assert snap["day_index"] == 1
    assert snap["state"]["resting_hr"] == 71.0


def test_fhir_subset_parsing():
    def _res(code, value, unit, dt="2026-01-04T08:04:00"):
        return {"resourceType": "Observation",
                "code": {"coding": [{"code": code}]},
                "valueQuantity": {"value": value, "unit": unit},
                "effectiveDateTime": dt,
                "subject": {"reference": "Patient/demo-01"}}

    resources = [
        _res("8867-4", 72.0, "/min"),
        _res("80404-7", 48.0, "ms"),
        _res("99999-9", 1.0, "x"),
        {"resourceType": "Patient"},
        _res("8867-4", "fast", "/min"),
    ]
    raw, issues = A.from_fhir(resources)
    assert len(raw) == 2 and len(issues) == 3
    # 8867-4 is generic heart rate: never silently relabeled resting_hr.
    assert raw[0]["metric"] == "heart_rate" and raw[0]["value"] == 72.0
    assert raw[0]["patient_id"] == "demo-01"
    # 80404-7 is R-R interval SD, not RMSSD.
    assert raw[1]["metric"] == "rr_sd" and raw[1]["value"] == 48.0
    # Explicit resting context on the resource DOES justify resting_hr.
    resting = dict(_res("8867-4", 68.0, "/min"))
    resting["bodyPosition"] = {"coding": [{"code": "lying", "display": "Lying"}]}
    resting["id"] = "obs-resting-1"
    raw_rest, _ = A.from_fhir([resting])
    assert len(raw_rest) == 1 and raw_rest[0]["metric"] == "resting_hr"
    import json as _json

    prov = _json.loads(raw_rest[0]["provenance"])
    assert prov["loinc"] == "8867-4" and prov["resource_id"] == "obs-resting-1"
    assert prov["terminology"].startswith("LOINC")
    accepted, problems = A.from_fhir_normalized(resources)
    assert len(accepted) == 2 and len(problems) == 3  # skips propagate, valid rows validate
    bundle = {"resourceType": "Bundle", "entry": [{"resource": _res("8867-4", 70.0, "bpm")}]}
    raw, _ = A.from_fhir(bundle)
    assert len(raw) == 1
    empty, problems = A.from_fhir({"resourceType": "Observation"})
    assert empty == [] and problems


def test_csv_json_adapters(tmp_path):
    path = tmp_path / "obs.csv"
    path.write_text(
        "patient_id,timestamp,source,metric,value,unit,quality,provenance\n"
        "p1,2026-01-04T08:00:00,csv,resting_hr,70,bpm,1.0,f\n"
        "p1,2026-01-04T08:00:00,csv,hrv_rmssd,50,ms,1.0,f\n"
        "p1,2026-01-04T08:00:00,csv,bogus,1,x,1.0,f\n",
        encoding="utf-8",
    )
    accepted, issues = A.from_csv_rows(str(path))
    assert len(accepted) == 2 and len(issues) == 1
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    try:
        A.from_csv_rows(str(bad))
        raise AssertionError("missing columns must be rejected")
    except ValueError:
        pass
    accepted, issues = A.from_json_batch([_raw(), {"metric": "nope"}])
    assert len(accepted) == 1 and len(issues) == 1
    try:
        A.from_csv_rows(str(tmp_path / "missing.csv"))
        raise AssertionError("missing file must be rejected")
    except ValueError:
        pass


def test_registry_pins_and_gate():
    entry = get_model()
    assert entry["model_id"] == DEFAULT_MODEL_ID
    assert entry["status"] == "research" and entry["deployment_gate"] == "closed"
    assert weights_digest() and len(weights_digest()) == 64
    assert verify_weights()["match"] in (True, False)
    gate = deployment_gate()
    assert gate["clinical_use"] == "closed" and gate["reasons"]
    try:
        get_model("nope")
        raise AssertionError("unknown models must be rejected")
    except KeyError:
        pass


def test_provenance_deterministic_and_sensitive():
    from rift.health import risk as K
    from rift.health.baseline import personal_baseline
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr

    ehr, _ = normalize_ehr(demo_ehr())
    stream = demo_stream()
    twin = DigitalTwin(ehr, stream)
    snap = twin.update(10)
    prov = snap["provenance"]
    assert prov["model_id"] == DEFAULT_MODEL_ID
    assert len(prov["prediction_id"]) == 64
    assert prov["weights_digest"] == weights_digest()
    assert DigitalTwin(ehr, stream).update(10)["provenance"] == prov
    assert prediction_provenance("p", 1, {"resting_hr": 70.0}) != prediction_provenance("p", 1, {"resting_hr": 71.0})


def test_decision_table_mirrors_ranking():
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr

    ehr, _ = normalize_ehr(demo_ehr())
    snap = DigitalTwin(ehr, demo_stream()).update(10)
    table = snap["decision_table"]
    assert len(table) == 4
    assert {tuple(sorted(r["policy"].items())) for r in table} == {
        tuple(sorted(r["policy"].items())) for r in snap["futures"]["robust_ranking"]}
    for row in table:
        for key in ("policy", "nominal_risk", "worst_case_risk", "trajectory_end_risk",
                    "feasible_under_all", "guardian_scope"):
            assert key in row


def test_live_ingest_feeds_timeline():
    from rift.health.models import WearableObservation

    live = LiveIngestSource()
    live.ingest(WearableObservation(day_index=0, resting_hr=70.0, hrv_rmssd=50.0,
                                    sleep_hours=7.0, activity_load=40.0))
    live.ingest(WearableObservation(day_index=1, resting_hr=72.0, hrv_rmssd=49.0,
                                    sleep_hours=7.1, activity_load=42.0))
    assert live.buffered_days == 2
    assert live.latest_at(1).resting_hr == 72.0
    # Same pipeline as replay: the twin cannot tell the source apart.
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr

    ehr, _ = normalize_ehr(demo_ehr())
    snap = DigitalTwin(ehr, live).update(1)
    assert snap["day_index"] == 1 and snap["state"]["resting_hr"] == 72.0


def test_nonfinite_values_rejected_not_normalized():
    for bad in (float("nan"), float("inf"), float("-inf")):
        assert validate_observation(_raw(value=bad))[0] is None
    for bad_q in (-0.5, 1.5, float("nan"), "high"):
        obs, _ = validate_observation(_raw(quality=bad_q))
        assert obs is None


def test_strict_timestamps_and_timezone_buckets():
    from rift.health.observations import normalize_timestamp

    assert normalize_timestamp("2026-01-04T08:04:00") == "2026-01-04T08:04:00+00:00"
    # Same instant in different zones buckets to the same UTC day.
    assert normalize_timestamp("2026-01-05T00:30+05:30")[:10] == "2026-01-04"
    assert normalize_timestamp("2026-01-04T19:00Z")[:10] == "2026-01-04"
    # Date-only is accepted explicitly as midnight UTC.
    assert normalize_timestamp("2026-01-04") == "2026-01-04T00:00:00+00:00"
    for bad in ("2026-99-99Tgarbage", "yesterday", "", None, {"period": True}):
        try:
            normalize_timestamp(bad)
            raise AssertionError(f"{bad!r} must be rejected")
        except ValueError:
            pass
    assert validate_observation(_raw(timestamp="2026-99-99T00:00:00"))[0] is None


def test_source_required_and_missing_subject_rejected():
    no_source = _raw()
    del no_source["source"]
    assert validate_observation(no_source)[0] is None
    blank = _raw()
    blank["source"] = "  "
    assert validate_observation(blank)[0] is None
    from rift.health import adapters as A

    nosubj = {"resourceType": "Observation",
              "code": {"coding": [{"code": "8867-4"}]},
              "valueQuantity": {"value": 70.0, "unit": "/min"},
              "effectiveDateTime": "2026-01-04T08:00:00"}
    raw, issues = A.from_fhir([nosubj])
    assert raw == [] and any("subject" in i for i in issues)


def test_weights_digest_genuinely_pinned():
    from rift.health import risk as RISK
    from rift.health.model_registry import get_model, verify_weights

    assert get_model()["weights_digest"] is not None
    assert len(get_model()["weights_digest"]) == 64
    assert verify_weights()["match"] is True
    assert verify_weights()["unpinned"] is False
    original = dict(RISK.RISK_WEIGHTS)
    try:
        RISK.RISK_WEIGHTS["base"] = 0.99
        assert verify_weights()["match"] is False
    finally:
        RISK.RISK_WEIGHTS.clear()
        RISK.RISK_WEIGHTS.update(original)
    assert verify_weights()["match"] is True


def test_gate_consumes_evidence_not_hardcoded_numbers():
    from rift.health.model_registry import deployment_gate

    default = deployment_gate()
    assert default["clinical_use"] == "closed"
    assert default["evidence_source"].startswith("bundled")
    strong = deployment_gate(evidence={
        "source": "hypothetical-adequate-trial",
        "events": 150, "non_events": 1200,
        "calibrated": True, "clinical_review": False, "synthetic": False,
    })
    # Still closed: no clinical review recorded. Evidence moves the verdict,
    # never the code path — one missing pillar keeps the gate shut.
    assert strong["clinical_use"] == "closed"
    assert not any("100-event" in r and "5 events" in r for r in strong["reasons"])


def test_provenance_envelope_is_complete():
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr

    ehr, _ = normalize_ehr(demo_ehr())
    snap = DigitalTwin(ehr, demo_stream()).update(10)
    prov = snap["provenance"]
    for key in ("prediction_id", "model_id", "weights_digest", "schema_version",
                "calibration_id", "source_ids", "engine"):
        assert key in prov, f"provenance missing {key}"
    assert len(prov["prediction_id"]) == 64
    assert prov["source_ids"] == ["synthetic-demo-generator"]
    assert snap["state"]["provenance"] == "synthetic-demo-generator"
    # EHR change alters the id: context is complete, not state-only.
    from rift.health.ehr import EHRRecord

    other_ehr = EHRRecord(patient_id="demo-patient-01", age=99.0)
    other = DigitalTwin(other_ehr, demo_stream()).update(10)
    assert other["provenance"]["prediction_id"] != snap["provenance"]["prediction_id"]
