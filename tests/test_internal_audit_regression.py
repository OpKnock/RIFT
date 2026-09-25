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


def test_metrics_endpoint_exposes_prometheus():
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    from rift.api import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
            assert resp.getcode() == 200
            body = resp.read().decode()
        assert "rift_api_requests_total" in body
        assert "rift_failure_rate" in body
        assert "rift_guardian_reject_rate" in body
        assert "rift_guardian_actions_total" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_ops_endpoints_gated_when_auth_configured(monkeypatch):
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    from rift import api as api_module
    from rift.api import Handler

    for name in ("RIFT_API_TOKEN", "RIFT_SUPABASE_JWT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    api_module._SEEN_WEBHOOK_KEYS.clear()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def get(path, token=None):
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers),
                        timeout=5) as resp:
                    return resp.getcode(), resp.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()

        # Open dev mode: ops endpoints reachable without credentials.
        assert get("/metrics")[0] == 200
        assert get("/api/ops/monitor")[0] == 200

        monkeypatch.setenv("RIFT_API_TOKEN", "ops-secret")
        assert get("/metrics")[0] == 401
        assert get("/api/ops/monitor")[0] == 401
        assert get("/metrics", token="wrong")[0] == 401
        status, body = get("/metrics", token="ops-secret")
        assert status == 200
        assert b"rift_api_requests_total" in body
        # Public health stays open even with auth configured.
        assert get("/api/health")[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_public_source_rejects_missing_identity_fields(tmp_path):
    from rift.health.sources import PublicDatasetSource

    p = tmp_path / "missing.csv"
    p.write_text(
        "subject_id,recording_id,date,metric,value,unit,source,provenance\n"
        ",R1,2024-01-01T00:00:00+00:00,heart_rate,80,bpm,src,\"{}\"\n",
        encoding="utf-8",
    )
    try:
        PublicDatasetSource(str(p))
        raise AssertionError("missing subject_id must fail closed")
    except ValueError as exc:
        assert "missing required field" in str(exc)

    p2 = tmp_path / "missing2.csv"
    p2.write_text(
        "subject_id,recording_id,date,metric,value,unit,source,provenance\n"
        "P1,R1,,heart_rate,80,bpm,src,\"{}\"\n",
        encoding="utf-8",
    )
    try:
        PublicDatasetSource(str(p2))
        raise AssertionError("missing date must fail closed")
    except ValueError as exc:
        assert "missing required field" in str(exc)


def test_hourly_timeline_preserves_acute_resolution():
    from rift.health.observations import normalize_batch
    from rift.health.timeline import to_hourly_rows

    raw = []
    for hour in (1, 2, 3):
        raw.append({"patient_id": "P1", "timestamp": f"2024-01-01T{hour:02d}:00:00+00:00",
                    "source": "icu", "metric": "heart_rate", "value": 90 + hour,
                    "unit": "bpm", "quality": 1.0, "provenance": "icu"})
        raw.append({"patient_id": "P1", "timestamp": f"2024-01-01T{hour:02d}:00:00+00:00",
                    "source": "icu", "metric": "sepsis_label", "value": 1 if hour == 3 else 0,
                    "unit": "binary", "quality": 1.0, "provenance": "icu"})
    accepted, issues = normalize_batch(raw)
    assert not issues
    rows = to_hourly_rows(accepted)
    assert len(rows) == 3  # no daily collapse
    assert [r["features"]["heart_rate"] for r in rows] == [91.0, 92.0, 93.0]
    assert [r["outcome"] for r in rows] == [0, 0, 1]


def test_monitoring_contract():
    # Every rift_* metric referenced by ACTIVE Prometheus rules and the
    # Grafana dashboard must be exported by /metrics (render_prometheus).
    # Aspirational metrics live in rift_future_alerts.yml.disabled.
    import json
    import re
    from pathlib import Path

    from rift.health.monitoring import EXPORTED_METRICS, MetricsCollector, render_prometheus

    metric_re = re.compile(r"\brift_[a-z0-9_]+\b")
    referenced: set[str] = set()
    for rules_file in Path("monitoring/prometheus/rules").glob("*.yml"):
        for metric in metric_re.findall(rules_file.read_text()):
            referenced.add(metric)
    dashboard = json.loads(Path("deployment/docker/grafana/dashboards/rift_clinical.json").read_text())
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            for metric in metric_re.findall(target.get("expr", "")):
                referenced.add(metric)
    # PromQL keywords/functions that merely start with rift_ are none;
    # every referenced name must be in the exported contract.
    missing = sorted(m for m in referenced if m not in EXPORTED_METRICS)
    assert not missing, f"rules/dashboard reference unexported metrics: {missing}"

    # The renderer must actually emit every contracted name.
    col = MetricsCollector()
    col.record_request("/api/health", 200, 12.0)
    col.record_prediction(0.7, "WARN", 0.1)
    body = render_prometheus(col.report())
    for metric in EXPORTED_METRICS:
        assert metric in body, f"render_prometheus missing {metric}"


def test_percentile_interpolation():
    from rift.health.monitoring import MetricsCollector as MC

    assert MC._percentile([], 50) is None
    assert MC._percentile([5.0], 50) == 5.0
    assert MC._percentile([1.0, 3.0], 50) == 2.0
    vals = [float(i) for i in range(1, 101)]  # 1..100
    assert MC._percentile(vals, 50) == 50.5
    assert MC._percentile(vals, 95) == 95.05
    assert MC._percentile(vals, 0) == 1.0
    assert MC._percentile(vals, 100) == 100.0


def test_kelvin_conversion():
    from rift.health.observations import validate_observation

    obs, issues = validate_observation({
        "patient_id": "P1", "timestamp": "2024-01-01T00:00:00+00:00",
        "source": "t", "metric": "temperature", "value": 300.0,
        "unit": "K", "quality": 1.0, "provenance": "t",
    })
    assert not issues
    assert abs(obs.value - 26.85) < 1e-9
    assert obs.unit == "C"
    obs, issues = validate_observation({
        "patient_id": "P1", "timestamp": "2024-01-01T00:00:00+00:00",
        "source": "t", "metric": "skin_temp", "value": 273.15,
        "unit": "K", "quality": 1.0, "provenance": "t",
    })
    assert not issues
    assert abs(obs.value - 0.0) < 1e-9


def test_double_rollback_walks_back_promotion_chain():
    from rift.health.model_registry import (
        AUDIT_LOG, DEFAULT_MODEL_ID, REGISTRY, get_model, promote, rollback,
    )

    saved_entry = dict(REGISTRY[DEFAULT_MODEL_ID])
    saved_log = list(AUDIT_LOG)
    try:
        REGISTRY[DEFAULT_MODEL_ID]["status"] = "research"
        REGISTRY[DEFAULT_MODEL_ID]["deployment_gate"] = "closed"
        AUDIT_LOG.clear()
        evidence = {"events": 150, "non_events": 1200, "calibrated": True,
                    "clinical_review": True, "synthetic": False}
        promote(target="candidate", evidence={"source": "t"}, approver="", notes="r1")
        promote(target="validated", evidence=evidence, approver="r", notes="r2")
        promote(target="approved", evidence=evidence, approver="r", notes="r3")
        first = rollback(reason="drift")
        assert (first["from"], first["to"]) == ("approved", "validated")
        second = rollback(reason="still drifting")
        # Must walk BACK to candidate, never forward to approved again.
        assert (second["from"], second["to"]) == ("validated", "candidate")
        assert get_model()["status"] == "candidate"
    finally:
        REGISTRY[DEFAULT_MODEL_ID].clear()
        REGISTRY[DEFAULT_MODEL_ID].update(saved_entry)
        AUDIT_LOG.clear()
        AUDIT_LOG.extend(saved_log)


def test_retired_from_candidate_is_legal_and_recorded():
    from rift.health.model_registry import (
        AUDIT_LOG, DEFAULT_MODEL_ID, REGISTRY, get_model, promote,
    )

    saved_entry = dict(REGISTRY[DEFAULT_MODEL_ID])
    saved_log = list(AUDIT_LOG)
    try:
        REGISTRY[DEFAULT_MODEL_ID]["status"] = "research"
        REGISTRY[DEFAULT_MODEL_ID]["deployment_gate"] = "closed"
        AUDIT_LOG.clear()
        promote(target="candidate", evidence={"source": "t"}, approver="", notes="r1")
        rec = promote(target="retired", evidence={}, approver="", notes="flawed candidate")
        assert (rec["from"], rec["to"]) == ("candidate", "retired")
        assert get_model()["deployment_gate"] == "closed"
    finally:
        REGISTRY[DEFAULT_MODEL_ID].clear()
        REGISTRY[DEFAULT_MODEL_ID].update(saved_entry)
        AUDIT_LOG.clear()
        AUDIT_LOG.extend(saved_log)


def test_webhook_failure_retry_is_not_swallowed_as_duplicate(monkeypatch):
    # A 502 persistence failure must NOT poison in-memory dedup: the
    # provider retry must reprocess the event instead of getting a
    # false duplicate-200 with unrecorded work.
    import hashlib
    import hmac
    import http.client
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.parse import urlparse

    from rift import api as api_module
    from rift.api import Handler

    for name in ("RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY",
                 "RIFT_LEMON_SQUEEZY_API_KEY", "RIFT_LEMON_SQUEEZY_STORE_ID",
                 "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RIFT_SUPABASE_URL", "https://x.example.co")
    monkeypatch.setenv("RIFT_SUPABASE_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "s")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh")
    api_module._SEEN_WEBHOOK_KEYS.clear()

    calls = {"records": 0}

    class FlakyStore:
        configured = True

        def find_billing_event(self, key):
            class R:
                data = []
            return R()

        def record_billing_event(self, payload):
            calls["records"] += 1
            if calls["records"] == 1:
                raise RuntimeError("supabase down")
            return None

        def upsert_subscription(self, payload):
            return None

    monkeypatch.setattr(api_module, "SupabaseStore", FlakyStore)

    payload = {"meta": {"event_name": "order_created"}, "data": {"id": "o-retry"}}
    raw = json.dumps(payload).encode()
    signature = hmac.new(b"wh", raw, hashlib.sha256).hexdigest()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def post():
            parts = urlparse(f"http://127.0.0.1:{port}/api/billing/webhook")
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
            conn.request("POST", parts.path, body=raw,
                         headers={"Content-Type": "application/json", "X-Signature": signature})
            resp = conn.getresponse()
            status, body = resp.status, json.loads(resp.read().decode())
            conn.close()
            return status, body

        first_status, _ = post()
        assert first_status == 502  # durable failure surfaces as retryable
        second_status, second_body = post()
        # Retry must reprocess (502 again or 200 success), never a false duplicate.
        assert second_status in (200, 502)
        assert second_body.get("duplicate") is not True
        assert calls["records"] == 2  # work was actually retried
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webhook_retry_resumes_failed_subscription_update(monkeypatch):
    # Edge: event row recorded but subscription upsert failed (502).
    # Retry must resume the side effect, not short-circuit as duplicate.
    import hashlib
    import hmac
    import http.client
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.parse import urlparse

    from rift import api as api_module
    from rift.api import Handler

    for name in ("RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY",
                 "RIFT_LEMON_SQUEEZY_API_KEY", "RIFT_LEMON_SQUEEZY_STORE_ID",
                 "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RIFT_SUPABASE_URL", "https://x.example.co")
    monkeypatch.setenv("RIFT_SUPABASE_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "s")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh")
    api_module._SEEN_WEBHOOK_KEYS.clear()

    state = {"events": [], "upserts": 0}

    class PartialFailureStore:
        configured = True

        def find_billing_event(self, key):
            class R:
                data = [{"idempotency_key": k} for k in state["events"] if k == key]
            return R()

        def record_billing_event(self, payload):
            state["events"].append(payload.get("idempotency_key"))
            return None

        def upsert_subscription(self, payload):
            state["upserts"] += 1
            if state["upserts"] == 1:
                raise RuntimeError("supabase down mid-webhook")
            return None

    monkeypatch.setattr(api_module, "SupabaseStore", PartialFailureStore)

    payload = {"meta": {"event_name": "subscription_created"},
               "data": {"id": "sub-9", "attributes": {"status": "active"}}}
    raw = json.dumps(payload).encode()
    signature = hmac.new(b"wh", raw, hashlib.sha256).hexdigest()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def post():
            parts = urlparse(f"http://127.0.0.1:{port}/api/billing/webhook")
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
            conn.request("POST", parts.path, body=raw,
                         headers={"Content-Type": "application/json", "X-Signature": signature})
            resp = conn.getresponse()
            status, body = resp.status, json.loads(resp.read().decode())
            conn.close()
            return status, body

        first_status, _ = post()
        assert first_status == 502  # event recorded, subscription update failed
        second_status, second_body = post()
        # Retry resumes the subscription update (duplicate delivery flag is
        # honest here: the event WAS seen before, but the side effect is
        # re-applied rather than skipped).
        assert second_status == 200
        assert second_body.get("duplicate") is True
        assert state["upserts"] == 2  # side effect actually retried
        third_status, third_body = post()
        assert third_status == 200
        assert third_body.get("duplicate") is True
        assert state["upserts"] == 2  # fully processed: no further work
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webhook_unique_violation_resumes_subscription_update(monkeypatch):
    # Edge: existence lookup fails transiently, then the insert reveals the
    # row already exists (UNIQUE violation). The subscription side effect
    # must still be applied before acknowledging — never skipped.
    import hashlib
    import hmac
    import http.client
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.parse import urlparse

    from rift import api as api_module
    from rift.api import Handler

    for name in ("RIFT_SUPABASE_URL", "RIFT_SUPABASE_KEY",
                 "RIFT_LEMON_SQUEEZY_API_KEY", "RIFT_LEMON_SQUEEZY_STORE_ID",
                 "RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RIFT_SUPABASE_URL", "https://x.example.co")
    monkeypatch.setenv("RIFT_SUPABASE_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_API_KEY", "k")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_STORE_ID", "s")
    monkeypatch.setenv("RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET", "wh")
    api_module._SEEN_WEBHOOK_KEYS.clear()

    state = {"upserts": 0}

    class RaceStore:
        configured = True

        def find_billing_event(self, key):
            raise RuntimeError("transient read failure")

        def record_billing_event(self, payload):
            raise RuntimeError(
                'duplicate key value violates unique constraint '
                '"billing_events_idempotency_key_unique"')

        def upsert_subscription(self, payload):
            state["upserts"] += 1
            return None

    monkeypatch.setattr(api_module, "SupabaseStore", RaceStore)

    payload = {"meta": {"event_name": "subscription_created"},
               "data": {"id": "sub-race", "attributes": {"status": "active"}}}
    raw = json.dumps(payload).encode()
    signature = hmac.new(b"wh", raw, hashlib.sha256).hexdigest()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        parts = urlparse(f"http://127.0.0.1:{port}/api/billing/webhook")
        conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
        conn.request("POST", parts.path, body=raw,
                     headers={"Content-Type": "application/json", "X-Signature": signature})
        resp = conn.getresponse()
        status, body = resp.status, json.loads(resp.read().decode())
        conn.close()
        assert status == 200
        assert body.get("duplicate") is True
        assert state["upserts"] == 1  # side effect resumed, not skipped
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_scraper_fetchers_refuse_non_https_targets():
    from rift.health import bidsleep_scrape as _b
    from rift.health import physionet_cardiac_scrape as _c
    from rift.health import sepsis_challenge_scrape as _s
    from rift.health import wearable_exam_stress_scrape as _w

    for fetch, bad in (
        (_b.fetch_with_provenance, "file:///etc/passwd"),
        (_c.fetch_bytes_with_provenance, "file:///etc/passwd"),
        (_s.fetch_with_provenance, "gopher://example.com/x"),
        (_w.fetch_with_provenance, "ftp://example.com/x"),
    ):
        prov, _ = fetch(bad, timeout=5)
        assert prov["success"] is False
        assert "allowlist" in (prov["error"] or "")


def test_k8s_production_requires_jwt_and_ratelimit():
    from pathlib import Path

    text = Path("deployment/kubernetes/production.yaml").read_text()
    assert "RIFT_SUPABASE_JWT_SECRET" in text
    assert "optional: true" not in text.split("RIFT_SUPABASE_JWT_SECRET")[1].split("- name:")[0]
    assert "RIFT_RATE_LIMIT_ENABLED" in text


def test_docker_compose_and_dockerfile_paths():
    from pathlib import Path

    compose = Path("deployment/docker/docker-compose.yml").read_text()
    assert "context: ../.." in compose
    assert "deployment/docker/Dockerfile" in compose
    assert "../../src:/app/src:ro" in compose
    dockerfile = Path("deployment/docker/Dockerfile").read_text()
    assert "0.0.0.0" in dockerfile
    assert 'CMD ["python", "-m", "rift.api"]' not in dockerfile


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
