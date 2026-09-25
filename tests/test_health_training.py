"""Training framework, promotion lifecycle, and decision sensitivity tests.

The framework is real code with real guarantees (manifests, splits, seeds,
hashes, benchmarks); weight fitting is deliberately absent and asserted
absent — fitting on synthetic demo data would be metric gaming.
"""
from rift.health import training as TR
from rift.health.decision import sensitivity_analysis
from rift.health.demo_data import demo_stream
from rift.health.model_registry import (
    DEFAULT_MODEL_ID,
    REGISTRY,
    AUDIT_LOG,
    get_audit_log,
    promote,
    rollback,
)


def _obs():
    return demo_stream().observations_upto(13)


def test_dataset_manifest_hashes_and_splits():
    observations = _obs()
    manifest = TR.dataset_manifest(
        dataset_id="synthetic-14d-v1", source="demo-generator",
        observations=observations, day_ranges={"all": [0, 13]})
    assert manifest["n_observations"] == 14
    assert len(manifest["dataset_hash"]) == 64
    assert TR.dataset_manifest(
        dataset_id="synthetic-14d-v1", source="demo-generator",
        observations=observations, day_ranges={"all": [0, 13]}) == manifest
    past, future = TR.temporal_split(observations, cutoff_day=7)
    assert len(past) == 7 and len(future) == 7
    assert max(o.day_index for o in past) < min(o.day_index for o in future)
    try:
        TR.temporal_split(observations, cutoff_day=99)
        raise AssertionError("degenerate split must be rejected")
    except ValueError:
        pass


def test_patient_split_protection():
    class Named:
        def __init__(self, day_index, patient_id):
            self.day_index = day_index
            self.patient_id = patient_id

    observations = [Named(0, "a"), Named(1, "a"), Named(2, "b"), Named(0, None)]
    development, report = TR.patient_split(observations, held_out_patients=["b"])
    assert len(report["held_out"]) == 1
    assert report["unattributed_kept_in_development"] == 1
    assert all(getattr(o, "patient_id", None) != "b" for o in development)
    try:
        TR.patient_split(observations, held_out_patients=["nobody"])
        raise AssertionError("empty held-out must be rejected")
    except ValueError:
        pass


def test_experiment_record_success_and_failure():
    dataset = TR.dataset_manifest(
        dataset_id="d", source="s", observations=_obs(), day_ranges={"all": [0, 13]})
    config = {"seed": 7, "feature_schema": "patient-state-v1",
              "threshold": 0.6, "purpose": "unit test"}
    ok = TR.run_experiment(experiment_id="exp-1", dataset=dataset, config=config,
                           metrics_fn=lambda c, d: {"event_agreement": 0.9})
    assert ok["status"] == "succeeded" and ok["metrics"]["event_agreement"] == 0.9
    assert len(ok["artifact_hash"]) == 64
    assert TR.run_experiment(experiment_id="exp-1", dataset=dataset, config=config,
                             metrics_fn=lambda c, d: {"event_agreement": 0.9}) == ok
    bad = TR.run_experiment(experiment_id="exp-2", dataset=dataset,
                            config={"seed": 1}, metrics_fn=None)
    assert bad["status"] == "failed" and "missing config" in bad["error"]
    boom = TR.run_experiment(experiment_id="exp-3", dataset=dataset, config=config,
                             metrics_fn=lambda c, d: 1 / 0)
    assert boom["status"] == "failed" and "ZeroDivisionError" in boom["error"]
    assert "fit" not in dir(TR) and "train_weights" not in dir(TR)


def test_compare_to_baseline_no_auto_winners():
    result = TR.compare_to_baseline({"event_agreement": 0.9, "brier": 0.1},
                                    {"event_agreement": 0.8, "brier": 0.2})
    assert result["metrics"]["event_agreement"]["verdict"] == "better"
    assert result["metrics"]["brier"]["verdict"] == "better"
    assert result["summary"] == "better"
    result = TR.compare_to_baseline({"event_agreement": 0.9}, {"event_agreement": 0.9})
    assert result["summary"] == "mixed-or-tied"
    result = TR.compare_to_baseline({"a": 1.0}, {"b": 2.0})
    assert result["metrics"]["a"]["verdict"] == "incomparable"


def _registry_guard():
    return dict(REGISTRY[DEFAULT_MODEL_ID]), list(AUDIT_LOG)


def _registry_restore(saved):
    saved_entry, saved_log = saved
    REGISTRY[DEFAULT_MODEL_ID].clear()
    REGISTRY[DEFAULT_MODEL_ID].update(saved_entry)
    AUDIT_LOG.clear()
    AUDIT_LOG.extend(saved_log)


def test_promotion_lifecycle_rules():
    from rift.health.model_registry import get_model

    saved = _registry_guard()
    try:
        evidence = {"events": 150, "non_events": 1200, "calibrated": True,
                    "clinical_review": True, "synthetic": False}
        try:
            promote(target="validated", evidence=evidence, approver="x", notes="skip")
            raise AssertionError("skipping research->validated must be rejected")
        except ValueError:
            pass
        first = promote(target="candidate", evidence={"source": "t"}, approver="", notes="initial review")
        assert first == {"model_id": DEFAULT_MODEL_ID, "from": "research", "to": "candidate"}
        try:
            promote(target="validated", evidence={"events": 5}, approver="x", notes="weak")
            raise AssertionError("weak evidence must be rejected")
        except ValueError:
            pass
        # Validation is an evidence gate (automatable): no approver needed,
        # but weak evidence and skipped steps are rejected.
        second = promote(target="validated", evidence=evidence, approver="",
                         notes="adequate independent evidence")
        assert second == {"model_id": DEFAULT_MODEL_ID, "from": "candidate", "to": "validated"}
        try:
            promote(target="approved", evidence=evidence, approver="", notes="no human?")
            raise AssertionError("approval without a human must be rejected")
        except ValueError:
            pass
        third = promote(target="approved", evidence=evidence, approver="reviewer-1",
                        notes="human approval recorded")
        assert third["to"] == "approved"
        assert get_model()["status"] == "approved"
        log = get_audit_log()
        assert [r["to"] for r in log] == ["candidate", "validated", "approved"]
    finally:
        _registry_restore(saved)


def test_rollback_requires_reason_and_history():
    saved = _registry_guard()
    try:
        evidence = {"events": 150, "non_events": 1200, "calibrated": True,
                    "clinical_review": True, "synthetic": False}
        promote(target="candidate", evidence={"source": "t"}, approver="", notes="r1")
        promote(target="validated", evidence=evidence, approver="r", notes="r2")
        promote(target="approved", evidence=evidence, approver="r", notes="r3")
        rolled = rollback(reason="calibration drift detected")
        assert rolled == {"model_id": DEFAULT_MODEL_ID, "from": "approved", "to": "validated"}
        try:
            rollback(reason="  ")
            raise AssertionError("reasonless rollback must be rejected")
        except ValueError:
            pass
    finally:
        _registry_restore(saved)


def test_sensitivity_analysis_reports_stability():
    state = {"resting_hr": 70.0, "hrv_rmssd": 45.0, "sleep_hours": 7.0, "activity_load": 40.0}

    def risk_fn(s):
        return 0.01 * s["resting_hr"] + 0.001 * s["activity_load"]

    report = sensitivity_analysis(state, risk_fn)
    assert abs(report["base_risk"] - 0.74) < 1e-9
    assert abs(report["fields"]["resting_hr"]["max_swing"] - 0.05) < 1e-9
    assert report["fields"]["sleep_hours"]["max_swing"] == 0.0
    missing = dict(state, hrv_rmssd=None)
    assert sensitivity_analysis(missing, risk_fn)["fields"]["hrv_rmssd"] == {"skipped": "missing baseline value"}
