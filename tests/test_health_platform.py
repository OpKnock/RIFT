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
    assert index == {("p1", "2026-01-04"): 0, ("p1", "2026-01-05"): 1}
    assert rows[0].day_index == 0 and rows[0].resting_hr == 72.0
    assert rows[0].patient_id == "p1"
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
    assert index == {("demo-patient-01", "2026-01-04"): 0, ("demo-patient-01", "2026-01-05"): 1}
    assert all(r.patient_id == "demo-patient-01" for r in rows)
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
    # Component hashes are exposed, not just folded into the id.
    assert len(prov["ehr_hash"]) == 64
    assert len(prov["baseline_hash"]) == 64
    assert len(prov["input_hash"]) == 64
    assert other["provenance"]["ehr_hash"] != snap["provenance"]["ehr_hash"]


def test_observation_ids_and_revisions_are_immutable():
    from rift.health.observations import Revision, normalize_batch, observation_id

    accepted, _ = normalize_batch([_raw(), _raw(value=71.0)])
    first, second = accepted
    assert observation_id(first) == observation_id(first)
    assert len(observation_id(first)) == 64
    assert observation_id(first) != observation_id(second)
    rev = Revision(supersedes_id=observation_id(first), observation=second,
                   reason="recalibrated device", revised_at="2026-01-05T00:00:00+00:00")
    assert len(rev.revision_id) == 64
    twin_rev = Revision(supersedes_id=observation_id(first), observation=second,
                        reason="recalibrated device", revised_at="2026-01-05T00:00:00+00:00")
    assert twin_rev.revision_id == rev.revision_id  # revised_at excluded from id
    assert first.value == 70.0  # original untouched: corrections never mutate


def test_terminology_registry_is_versioned_and_reviewable():
    from rift.health import terminology as T

    assert T.TERMINOLOGY_VERSION.startswith("LOINC")
    assert T.mapping_status("8867-4")["metric"] == "heart_rate"
    assert T.mapping_status("8867-4")["status"] == "supported"
    assert T.mapping_status("80404-7")["metric"] == "rr_sd"
    assert T.mapping_status("99999-9")["status"] == "unmapped"
    assert "never guessed" in T.mapping_status(None)["reason"]


def test_timeline_coverage_reports_unestimated_metrics():
    from rift.health import timeline as T
    from rift.health.observations import normalize_batch

    accepted, issues = normalize_batch([
        _raw(metric="resting_hr", value=70.0),
        _raw(metric="heart_rate", value=72.0),
        _raw(metric="rr_sd", value=40.0, unit="ms"),
    ])
    assert not issues
    coverage = T.timeline_coverage(accepted)
    assert coverage["resting_hr"] == "estimated"
    assert coverage["heart_rate"].startswith("preserved-not-estimated")
    assert coverage["rr_sd"].startswith("preserved-not-estimated")


def test_twin_flags_unestimated_metrics_via_guardian():
    from rift.health import timeline as T
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr
    from rift.health.observations import normalize_batch

    accepted, _ = normalize_batch([
        _raw(timestamp="2026-01-04T08:00:00", metric="heart_rate", value=72.0),
    ])
    rows, _ = T.to_daily_rows(accepted)
    assert rows and rows[0].resting_hr is None  # generic HR never becomes resting_hr
    ehr, _ = normalize_ehr(demo_ehr())
    twin = DigitalTwin(ehr, demo_stream(), canonical_observations=accepted)
    snap = twin.update(10)
    assert any("unestimated metrics" in flag for flag in snap["guardian"]["flags"])
    assert "timeline_coverage" in snap
    assert snap["timeline_coverage"]["heart_rate"].startswith("preserved-not-estimated")


def test_issued_without_effective_is_rejected():
    from rift.health import adapters as A

    issued_only = {"resourceType": "Observation",
                   "code": {"coding": [{"code": "8867-4"}]},
                   "valueQuantity": {"value": 70.0, "unit": "/min"},
                   "issued": "2026-01-04T08:00:00+00:00",
                   "subject": {"reference": "Patient/p1"}}
    raw, issues = A.from_fhir([issued_only])
    assert raw == [] and any("issued is not a substitute" in i for i in issues)


def test_ingest_batch_decisions_and_dedup():
    from rift.health.observations import ingest_batch

    first = _raw()
    accepted, decisions = ingest_batch(
        [first, dict(first), _raw(metric="nope")],
        batch_id="b1", source_id="csv-test")
    assert len(accepted) == 1 and len(decisions) == 3
    assert [d["decision"] for d in decisions] == ["accepted", "rejected", "rejected"]
    assert all(d["batch_id"] == "b1" for d in decisions)
    assert decisions[0]["observation_id"] is not None
    assert decisions[1]["observation_id"] == decisions[0]["observation_id"]
    assert any("duplicate" in r for r in decisions[1]["reasons"])
    assert decisions[2]["observation_id"] is None
    empty, bad = ingest_batch("not-a-list", batch_id="b2", source_id="s")
    assert empty == [] and bad[0]["decision"] == "rejected"


def test_uncertainty_breakdown_sums_and_labels():
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr

    ehr, _ = normalize_ehr(demo_ehr())
    breakdown = DigitalTwin(ehr, demo_stream()).update(10)["risk"]["uncertainty_breakdown"]
    assert breakdown["grade"] == "heuristic-demo"
    parts = (breakdown["base_component"] + breakdown["quality_component"]
             + breakdown["jitter_component"] + breakdown["robustness_spread"])
    # Components are rounded to 4dp, so allow rounding slack — not exactness theater.
    assert abs(min(0.45, parts) - breakdown["total"]) < 1e-3
    assert breakdown["jitter_component"] >= 0.0


def test_fhir_clinical_resources():
    from rift.health import fhir_clinical as F

    patient = {"resourceType": "Patient", "id": "p1",
               "birthDate": "1968-03-22", "gender": "male"}
    demo, issues = F.parse_patient(patient)
    assert demo["patient_id"] == "p1" and demo["age"] == 58.0 and demo["sex"] == "M"
    assert F.parse_patient({"resourceType": "Patient"})[0].get("age") is None
    assert F.parse_patient({}) == ({}, ["not a Patient resource"])
    cond = {"resourceType": "Condition",
            "code": {"coding": [{"display": "Hypertension"}]},
            "clinicalStatus": {"coding": [{"code": "active"}]}}
    assert F.parse_condition(cond)[0] == "hypertension"
    assert F.parse_condition({"resourceType": "Condition",
                              "code": {"coding": [{"display": "Martian flu"}]}})[0] is None
    resolved = {"resourceType": "Condition",
                "code": {"coding": [{"display": "Hypertension"}]},
                "clinicalStatus": {"coding": [{"code": "resolved"}]}}
    assert F.parse_condition(resolved)[0] is None  # inactive excluded
    med = {"resourceType": "MedicationStatement",
           "medicationCodeableConcept": {"coding": [{"display": "Metformin"}]},
           "status": "active"}
    assert F.parse_medication(med)[0] == "metformin"
    assert F.parse_medication({"resourceType": "Observation"})[0] is None
    enc, _ = F.parse_encounter({"resourceType": "Encounter", "id": "e1",
                                "period": {"start": "2026-01-04T08:00:00+00:00"},
                                "status": "finished"})
    assert enc["id"] == "e1"
    assert F.parse_encounter({"resourceType": "Encounter"})[0] is None
    dev, _ = F.parse_device({"resourceType": "Device", "id": "d1",
                             "type": {"coding": [{"display": "watch"}]},
                             "status": "active",
                             "patient": {"reference": "Patient/p1"}})
    assert dev["patient_id"] == "p1"
    bundle = {"resourceType": "Bundle", "entry": [
        {"resource": patient}, {"resource": cond}, {"resource": med}]}
    raw, issues = F.bundle_to_ehr(bundle)
    assert raw["patient_id"] == "p1" and "hypertension" in raw["conditions"]
    assert "metformin" in raw["medications"]
    assert F.bundle_to_ehr({})[0]["conditions"] == []
    from rift.health.ehr import normalize_ehr

    record, problems = normalize_ehr(raw)
    assert record.age == 58.0 and "hypertension" in record.conditions


def test_fhir_pagination_auth_retry_manifest(monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from rift.health import fhir_clinical as F

    monkeypatch.setenv("RIFT_ALLOW_PRIVATE_FETCH", "true")
    monkeypatch.setenv("RIFT_ALLOW_HTTP", "true")

    calls = {"n": 0, "auth": []}

    class FHIRHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls["n"] += 1
            calls["auth"].append(self.headers.get("Authorization"))
            if self.headers.get("Authorization") != "Bearer good-token":
                self.send_response(401)
                self.end_headers()
                return
            if self.path == "/page1" and calls["n"] in (2, 3):
                self.send_response(503)  # transient: must be retried
                self.end_headers()
                return
            import json as _json

            if self.path == "/page1":
                body = {"resourceType": "Bundle", "entry": [
                    {"resource": {"resourceType": "Observation"}}],
                    "link": [{"relation": "next", "url": f"http://127.0.0.1:{port}/page2"}]}
            else:
                body = {"resourceType": "Bundle", "entry": []}
            raw = _json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/fhir+json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), FHIRHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            F.fetch_bundle(f"http://127.0.0.1:{port}/page1", token="bad-token", timeout_s=5)
            raise AssertionError("bad credentials must raise auth error")
        except F.FhirError as exc:
            assert "auth" in str(exc)
        resources, manifest = F.fetch_all_pages(
            f"http://127.0.0.1:{port}/page1", token="good-token", timeout_s=5)
        assert len(resources) == 1
        assert manifest["total_resources"] == 1 and len(manifest["pages"]) == 2
        assert manifest["truncated"] is False
        assert calls["n"] >= 4  # initial + auth-fail + retries + page2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_fhir_ssrf_private_targets_refused_by_default(monkeypatch):
    from rift.health import fhir_clinical as F

    monkeypatch.delenv("RIFT_ALLOW_PRIVATE_FETCH", raising=False)
    for url in ("http://169.254.169.254/latest/meta-data/",
                "http://127.0.0.1:9/fhir",
                "file:///etc/passwd",
                "gopher://example.com/"):
        try:
            F.fetch_bundle(url, token="t", timeout_s=2, max_retries=0)
            raise AssertionError(f"{url} must be refused")
        except F.FhirError as exc:
            assert "security" in str(exc), str(exc)


def test_fhir_private_fetch_opt_in_is_explicit(monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from rift.health import fhir_clinical as F

    class OKHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            raw = b'{"resourceType": "Bundle", "entry": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), OKHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.delenv("RIFT_ALLOW_PRIVATE_FETCH", raising=False)
        monkeypatch.delenv("RIFT_ALLOW_HTTP", raising=False)
        try:
            F.fetch_bundle(f"http://127.0.0.1:{port}/x", timeout_s=5, max_retries=0)
            raise AssertionError("loopback must be refused by default")
        except F.FhirError:
            pass
        monkeypatch.setenv("RIFT_ALLOW_PRIVATE_FETCH", "true")
        monkeypatch.setenv("RIFT_ALLOW_HTTP", "true")
        assert F.fetch_bundle(f"http://127.0.0.1:{port}/x", timeout_s=5)["resourceType"] == "Bundle"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_multiresolution_buckets_and_weighted_estimation():
    from rift.health import timeline as T
    from rift.health.observations import normalize_batch

    accepted, issues = normalize_batch([
        _raw(timestamp="2026-01-04T08:04:00", metric="resting_hr", value=70.0),
        _raw(timestamp="2026-01-04T18:00:00", metric="resting_hr", value=74.0),
        _raw(timestamp="2026-01-05T08:00:00", metric="resting_hr", value=72.0),
    ])
    assert not issues
    hours = T.bucket_by_resolution(accepted, "hour")
    assert sorted(hours) == ["2026-01-04T08", "2026-01-04T18", "2026-01-05T08"]
    weeks = T.bucket_by_resolution(accepted, "week")
    # 2026-01-04 is a Sunday, 2026-01-05 a Monday: ISO weeks split here,
    # which is exactly the boundary behavior week buckets must have.
    assert sorted(weeks) == ["2026-W01", "2026-W02"]
    try:
        T.bucket_by_resolution(accepted, "fortnight")
        raise AssertionError("unknown resolution must be rejected")
    except ValueError:
        pass
    day_obs = [o for o in accepted if o.timestamp.startswith("2026-01-04")]
    assert T.estimate_day(day_obs)["resting_hr"] == 72.0  # median default unchanged
    weighted = T.estimate_day(
        [dict(o.to_dict(), quality=q) for o in []], weight_by_quality=True) if False else None
    import dataclasses

    low_first = [dataclasses.replace(day_obs[0], quality=0.0),
                 dataclasses.replace(day_obs[1], quality=1.0)]
    assert T.estimate_day(low_first, weight_by_quality=True)["resting_hr"] == 74.0
    assert T.estimate_day(low_first)["resting_hr"] == 72.0  # median ignores quality


def test_estimator_comparison_reports_disagreement():
    from rift.health import estimation as E

    values = [70.0, 71.0, 72.0, 90.0]
    assert E.median_estimate(values) == 71.5
    assert E.median_estimate([]) is None
    assert E.weighted_mean_estimate(values, [1, 1, 1, 0]) == 71.0
    assert E.ewm_estimate([70.0, 70.0, 70.0]) == 70.0
    try:
        E.ewm_estimate(values, alpha=0.0)
        raise AssertionError("bad alpha must be rejected")
    except ValueError:
        pass
    report = E.compare_estimators({"hr": values})
    assert report["production"] == "median"
    assert set(report["estimators"]) == {"median", "weighted_mean", "ewm"}
    assert report["max_disagreement"]["hr"] > 0  # outlier moves mean/ewm off median


def test_drift_detection_events_and_insufficient_data():
    from rift.health import drift as D
    from rift.health.models import WearableObservation as W

    ref = [W(day_index=i, resting_hr=70.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0)
           for i in range(7)]
    same = [W(day_index=7 + i, resting_hr=70.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0)
            for i in range(3)]
    calm = D.detect_drift(ref, same)
    assert calm["drifted"] is False and calm["events"] == []
    shifted = [W(day_index=7 + i, resting_hr=85.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0)
               for i in range(3)]
    hot = D.detect_drift(ref, shifted)
    assert hot["drifted"] is True
    assert any(e["field"] == "resting_hr" for e in hot["events"])
    gappy = [W(day_index=7 + i, resting_hr=None, hrv_rmssd=None, sleep_hours=None, activity_load=None)
             for i in range(3)]
    missing = D.detect_drift(ref, gappy)
    assert missing["drifted"] is True
    assert any(e["kind"] == "missingness" for e in missing["events"])
    empty = D.detect_drift([], same)
    assert empty["drifted"] is False
    assert any("unassessable" in e["message"] for e in empty["events"])
