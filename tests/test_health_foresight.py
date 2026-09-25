"""FORESIGHT, robustness, Guardian, explainability, and predictive evaluation."""
from rift.health import guardian as G
from rift.health import robustness as R
from rift.health import ehr as E
from rift.health import risk as K
from rift.health.baseline import deviations, personal_baseline
from rift.health.demo_data import demo_stream
from rift.health.explain import build_reasons
from rift.health.foresight import counterfactual_futures, health_causal_graph, trajectories
from rift.health.models import PatientState
from rift.health.twin import DigitalTwin


def _setup(day=10):
    ehr, _ = E.normalize_ehr(E.demo_ehr())
    stream = demo_stream()
    twin = DigitalTwin(ehr, stream)
    state = twin.synchronize(day)
    baseline = personal_baseline(stream.observations_upto(day))
    return ehr, state, baseline


def test_foresight_futures_use_generic_engine():
    ehr, state, baseline = _setup()
    out = counterfactual_futures(state, baseline, ehr)
    assert len(out["policies"]) == 4  # 2 binary interventions
    assert len(out["robust_ranking"]) == 4
    assert {tuple(sorted(a["policy"].items())) for a in out["robust_ranking"]} == {
        tuple(sorted(p["policy"].items())) for p in out["policies"]}
    # What-if works: extra sleep never raises nominal risk vs doing nothing.
    by_policy = {tuple(sorted(p["policy"].items())): p["risk"] for p in out["policies"]}
    assert by_policy[(("exertion_cut", 0), ("sleep_plus", 1))] <= by_policy[(("exertion_cut", 0), ("sleep_plus", 0))]


def test_trajectories_horizon_and_monotone_shape():
    ehr, state, baseline = _setup(day=9)
    trajs = trajectories(state, baseline, ehr, horizon_days=3)
    assert len(trajs) == 4 and all(len(t["path"]) == 4 for t in trajs)
    assert all(t["path"][0]["day"] == 0 and t["path"][-1]["day"] == 3 for t in trajs)
    assert all(0.0 <= p["risk"] <= 1.0 for t in trajs for p in t["path"])


def test_robustness_spread_and_degradations():
    ehr, state, baseline = _setup()
    rep = R.robustness_report(state, baseline, ehr)
    assert rep["worst_case_spread"] >= 0.0
    assert len(rep["ranking"]) == 4
    dropped = R.degrade_missing(state, "resting_hr")
    assert dropped.resting_hr is None
    stale = R.degrade_stale(state)
    assert stale.stale_days == state.stale_days + 3 and stale.data_quality < state.data_quality
    noisy_a = R.degrade_noisy(state, seed=7)
    noisy_b = R.degrade_noisy(state, seed=7)
    assert noisy_a == noisy_b  # deterministic
    combined = R.combine_uncertainty(0.1, rep["worst_case_spread"])
    assert combined >= 0.1
    # Stale inputs widen predictive uncertainty end-to-end.
    stale_snap = DigitalTwin(ehr, demo_stream())
    stale_state = R.degrade_stale(stale_snap.synchronize(10), extra_days=5)
    assert K.input_quality(stale_state) < K.input_quality(state)


def test_guardian_rejects_impossible_and_flags_stale():
    ehr, state, baseline = _setup()
    risk_record = K.predict(state, baseline, ehr)
    ok = G.verdict(state, risk_record)
    assert ok["display_allowed"] is True
    bad = PatientState(day_index=1, resting_hr=400.0, hrv_rmssd=50.0, sleep_hours=7.0, activity_load=40.0)
    rejected = G.verdict(bad, risk_record)
    assert rejected["display_allowed"] is False and rejected["rejections"]
    stale = PatientState(day_index=9, resting_hr=70.0, hrv_rmssd=45.0, sleep_hours=7.0, activity_load=40.0, stale_days=5)
    flagged = G.verdict(stale, risk_record)
    assert flagged["display_allowed"] is True and flagged["flags"]
    uncertain = dict(risk_record, uncertainty=0.40)
    assert G.verdict(state, uncertain)["flags"]
    shifted = PatientState(day_index=2, resting_hr=state.resting_hr + 50 if state.resting_hr else 120.0,
                           hrv_rmssd=45.0, sleep_hours=7.0, activity_load=40.0)
    assert G.verdict(shifted, risk_record, previous=state)["display_allowed"] is False
    # Output schema allowlist: treatment keys can never pass.
    poisoned = dict(risk_record, prescription="take X")
    assert G.verdict(state, poisoned)["display_allowed"] is False


def test_explainability_reasons_present():
    ehr, state, baseline = _setup()
    risk_record = K.predict(state, baseline, ehr)
    guard = G.verdict(state, risk_record)
    devs = deviations(state, baseline)
    reasons = build_reasons(state, baseline, devs, ehr, risk_record, guard, "note")
    text = " ".join(reasons)
    assert len(reasons) >= 4
    assert "note" in reasons
    assert any("baseline" in r.lower() or "contributor" in r.lower() for r in reasons)


def test_predictive_evaluation_spell_vs_calm():
    """Software validation (NOT clinical): event fires on spell days only."""
    ehr, _, _ = _setup()
    twin = DigitalTwin(ehr, demo_stream())
    events = {s["day_index"]: s["risk"]["event_predicted"] for s in twin.replay(0, 13)}
    assert events[10] is True
    calm_days = [d for d in range(8) if not events[d]]
    assert len(calm_days) >= 6  # specificity on calm days
    assert sum(events.values()) <= 4  # selective, not always-on
    graph = health_causal_graph()
    assert len(graph.edges) == 6 and "cardiac_strain" in graph.nodes


def test_guardian_findings_have_stable_rule_ids_and_stages():
    from rift.health.guardian import STAGES

    ehr, state, baseline = _setup()
    risk_record = K.predict(state, baseline, ehr)
    guard = G.verdict(state, risk_record, ehr=ehr)
    assert set(guard["stages"]) == set(STAGES)
    for finding in guard["findings"]:
        assert set(finding) == {"rule_id", "stage", "severity", "action", "message", "evidence"}
        assert finding["stage"] in STAGES
        assert finding["severity"] in ("HIGH", "MEDIUM", "LOW")
        assert finding["action"] in ("WITHHOLD", "WARN")
    # Every rejection/flag string comes from exactly one finding.
    assert sorted(guard["rejections"] + guard["flags"]) == sorted(
        f["message"] for f in guard["findings"])
    # Deterministic: no wall-clock anywhere in the verdict.
    assert G.verdict(state, risk_record, ehr=ehr) == guard


def test_guardian_action_mapping_and_stage_gates():
    ehr, state, baseline = _setup()
    risk_record = K.predict(state, baseline, ehr)
    calm = G.verdict(state, risk_record, ehr=ehr)
    assert calm["action"] in ("ALLOW", "WARN")
    assert calm["display_allowed"] is True
    bad = PatientState(day_index=1, resting_hr=400.0, hrv_rmssd=50.0,
                       sleep_hours=7.0, activity_load=40.0)
    rejected = G.verdict(bad, risk_record, ehr=ehr)
    assert rejected["action"] == "WITHHOLD"
    assert rejected["display_allowed"] is False
    assert rejected["stages"]["STATE"]["passed"] is False
    assert "G-001" in rejected["stages"]["STATE"]["rules"]
    # Stages without applicable rules pass vacuously and say so.
    assert calm["stages"]["COUNTERFACTUAL"] == {"passed": True, "rules": []}
    assert calm["stages"]["DEPLOYMENT"] == {"passed": True, "rules": []}
    # Unestimated metrics arrive as a rule, not a twin-side hack.
    flagged = G.verdict(state, risk_record, ehr=ehr, unestimated=("heart_rate",))
    assert any(f["rule_id"] == "G-011" for f in flagged["findings"])
    assert any("unestimated metrics" in f["message"] for f in flagged["findings"])


def test_guardian_schema_drift_withholds():
    ehr, state, baseline = _setup()
    risk_record = K.predict(state, baseline, ehr)
    # Valid state with new additive fields should only produce WARN, not WITHHOLD
    result = G.check_schema(state)
    assert not result["rejections"]  # No rejections for additive fields
    # New additive fields (patient_id, time_offset_hours) should produce WARN
    warn_findings = [f for f in result["findings"] if f.action == "WARN"]
    assert any(f.rule_id == "G-012" for f in warn_findings)
    # Dict-form states are checked identically (same contract, both shapes).
    drifted = dict(state.to_dict())
    drifted.pop("sleep_hours")
    drifted["mystery_field"] = 1.0
    result = G.check_schema(drifted)
    assert any(f.rule_id == "G-012" for f in result["findings"])
    assert result["rejections"]  # Missing required field + unexpected = WITHHOLD


def test_guardian_counterfactual_ledger_and_ordering():
    from rift.health.foresight import counterfactual_futures, policy_assumptions

    ehr, state, baseline = _setup()
    futures = counterfactual_futures(state, baseline, ehr)
    for item in futures["robust_ranking"]:
        assert set(item["assumptions"]) >= {
            "policy", "transition_model", "model_id", "weights_digest",
            "horizon_days", "perturbation_set", "causal_scope", "claim"}
    assert G.check_counterfactuals(futures)["findings"] == []
    stripped = {"robust_ranking": [{**item, "assumptions": {}} for item in futures["robust_ranking"]]}
    missing = G.check_counterfactuals(stripped)
    assert any(f.rule_id == "G-013" for f in missing["findings"])
    assert missing["rejections"]
    assert G.check_counterfactuals(None) == {"rejections": [], "flags": [], "findings": []}
    assert policy_assumptions({"sleep_plus": 1, "exertion_cut": 0}, 3)["horizon_days"] == 3


def test_guardian_model_identity_and_deployment():
    from rift.health import guardian as G2

    ehr, state, baseline = _setup()
    risk_record = K.predict(state, baseline, ehr)
    assert G.check_model(None) == {"rejections": [], "flags": [], "findings": []}
    assert G.check_model({"model_id": "nope"})["rejections"]
    from rift.health.model_registry import weights_digest

    ok = G.check_model({"model_id": "cardiac-strain-v1", "weights_digest": weights_digest()})
    assert ok["findings"] == []
    # Tamper with LIVE weights: the check compares registry pin vs live, so
    # a forged context digest alone changes nothing — only real drift fires.
    from rift.health import risk as RISK

    original = dict(RISK.RISK_WEIGHTS)
    try:
        RISK.RISK_WEIGHTS["base"] = 0.99
        tampered = G.check_model({"model_id": "cardiac-strain-v1",
                                  "weights_digest": weights_digest()})
        assert any(f.rule_id == "G-015" for f in tampered["findings"])
        assert tampered["rejections"]
    finally:
        RISK.RISK_WEIGHTS.clear()
        RISK.RISK_WEIGHTS.update(original)
    assert G.check_deployment(None) == {"rejections": [], "flags": [], "findings": []}
    assert G.check_deployment({"clinical_use": "closed"})["findings"] == []
    inverted = G.check_deployment({"clinical_use": "open", "model_id": "cardiac-strain-v1"})
    assert any(f.rule_id == "G-016" for f in inverted["findings"])
    assert inverted["rejections"]
    # Full verdict wires all three new contexts.
    full = G.verdict(state, risk_record, ehr=ehr,
                     counterfactuals={"robust_ranking": []},
                     model_context={"model_id": "cardiac-strain-v1",
                                    "weights_digest": weights_digest()},
                     deployment={"clinical_use": "closed"})
    assert full["display_allowed"] is True
    assert full["stages"]["COUNTERFACTUAL"] == {"passed": True, "rules": []}


def test_twin_snapshot_carries_counterfactual_model_deployment_gates():
    from rift.health.demo_data import demo_stream
    from rift.health.ehr import demo_ehr, normalize_ehr

    ehr, _ = normalize_ehr(demo_ehr())
    snap = DigitalTwin(ehr, demo_stream()).update(10)
    rules = {f["rule_id"] for f in snap["guardian"]["findings"]}
    assert snap["guardian"]["stages"]["MODEL"]["passed"] is True  # G-015 verified live
    assert snap["guardian"]["stages"]["DEPLOYMENT"]["passed"] is True  # closed gate, no findings
    assert "G-015" not in rules  # verified silently: no news is good news
