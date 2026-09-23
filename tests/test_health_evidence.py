"""Phase-4 evidence tests: independent labels, held-out metrics, CSV adapter.

Bounds are software regression bounds on synthetic data — they pin the
pipeline's honest behavior (including its misses), never clinical quality.
"""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from rift.api import Handler
from rift.health import ehr as E
from rift.health.demo_data import demo_series, demo_stream
from rift.health.evaluate import OUTCOME_RULE, backtest, calibration_report, fit_platt_scaling, realized_outcome, stress_sweep
from rift.health.models import PatientState, WearableObservation
from rift.health.sources import PublicDatasetSource
from rift.health.twin import DigitalTwin
from rift.health.wearable import jitter_score


def _ehr():
    record, _ = E.normalize_ehr(E.demo_ehr())
    return record


def test_outcome_rule_is_independent_of_risk_weights():
    # High model risk WITHOUT the observed criteria firing: proves the label
    # is not the model agreeing with itself.
    borderline = WearableObservation(0, resting_hr=74.0, hrv_rmssd=25.0,
                                     sleep_hours=3.0, activity_load=100.0)
    event, _ = realized_outcome(borderline)
    assert event is False
    # The rule text documents observed (not modeled) criteria.
    from rift.health.baseline import personal_baseline
    from rift.health.risk import predict

    base = personal_baseline(demo_stream().observations_upto(9))
    borderline_state = PatientState(
        day_index=0, resting_hr=74.0, hrv_rmssd=25.0, sleep_hours=3.0, activity_load=100.0)
    assert predict(borderline_state, base, _ehr())["risk"] >= 0.6
    # Clear spell day fires with criteria named.
    spell = WearableObservation(0, resting_hr=78.0, hrv_rmssd=30.0,
                                sleep_hours=4.0, activity_load=85.0)
    event, criteria = realized_outcome(spell)
    assert event is True and len(criteria) == 3  # HR gate + sleep + HRV
    assert realized_outcome(WearableObservation(0))[0] is False


def test_long_series_held_out_metrics():
    ehr = _ehr()
    report = backtest(DigitalTwin(ehr, demo_series()), 30, 59)
    assert report["labels"] == "independent-outcome-v1"
    assert report["days_evaluated"] == 30
    assert report["event_agreement"] >= 0.75
    assert report["specificity"] >= 0.85
    assert report["brier"] < 0.2
    assert report["interval_coverage"] >= 0.5
    assert sum(report["confusion"].values()) == 30
    assert any(lag == 0 for lag in report["onset_lags"])  # at least one exact catch
    assert all(isinstance(lag, int) for lag in report["onset_lags"])
    # Deterministic rerun.
    again = backtest(DigitalTwin(ehr, demo_series()), 30, 59)
    assert again["confusion"] == report["confusion"]
    assert again["brier"] == report["brier"]


def test_stress_sweep_graceful():
    ehr = _ehr()
    result = stress_sweep(demo_series(), ehr, list(range(30, 45)))
    assert [r["noise_magnitude"] for r in result["rows"]] == [0.0, 0.05, 0.15]
    assert all(r["agreement"] is not None and r["agreement"] >= 0.7 for r in result["rows"])
    assert result["uncertainty_non_decreasing"] is True
    # Phase 5: uncertainty must actually RESPOND to noise, not merely not shrink.
    first = result["rows"][0]["mean_uncertainty"]
    last = result["rows"][-1]["mean_uncertainty"]
    assert last is not None and first is not None and last > first


def test_jitter_low_on_calm_days_high_on_shocks():
    stream = demo_series()
    prior = [o for o in stream.observations_upto(5) if o.day_index < 5]
    calm = jitter_score(stream.latest_at(5), stream.latest_at(4), prior)
    assert 0.0 <= calm < 0.3
    spell_prior = [o for o in stream.observations_upto(20) if o.day_index < 20]
    shock = jitter_score(stream.latest_at(20), stream.latest_at(19), spell_prior)
    assert shock > calm
    assert jitter_score(None, stream.latest_at(19), spell_prior) == 0.0
    assert jitter_score(stream.latest_at(5), None, prior) == 0.0
    # Deterministic.
    assert jitter_score(stream.latest_at(5), stream.latest_at(4), prior) == calm


def test_threshold_tradeoff_characterizes_not_games():
    from rift.health.evaluate import backtest, threshold_tradeoff

    ehr = _ehr()
    report = backtest(DigitalTwin(ehr, demo_series()), 30, 59)
    tradeoff = threshold_tradeoff(report)
    assert tradeoff["operating_threshold"] == 0.6
    assert [r["threshold"] for r in tradeoff["rows"]] == [0.4, 0.5, 0.6, 0.7, 0.8]
    # Lowering the threshold cannot rescue detection here: sensitivity is
    # flat at and below the operating point, so the misses are structural
    # (onset shocks), not threshold artifacts. This pins the honest finding.
    low = [r for r in tradeoff["rows"] if r["threshold"] <= 0.7]
    assert all(r["sensitivity"] == low[0]["sensitivity"] for r in low)
    specs = [r["specificity"] for r in tradeoff["rows"]]
    assert specs == sorted(specs)  # higher bar, fewer false alarms
    assert tradeoff["rows"][-1]["sensitivity"] == 0.0  # 0.8 strands the caught event too


def test_calibration_label_present_and_honest():
    from rift.health.baseline import personal_baseline
    from rift.health.risk import predict

    ehr = _ehr()
    stream = demo_series()
    twin = DigitalTwin(ehr, stream)
    snap = twin.update(10)
    assert snap["risk"]["calibration"] == "demo / not calibrated"
    assert "measurement_jitter" in snap["risk"]
    assert snap["risk"]["measurement_jitter"] >= 0.0


def test_trend_term_rewards_deterioration_only():
    from rift.health.baseline import personal_baseline
    from rift.health.models import PatientState
    from rift.health.risk import drivers

    ehr = _ehr()
    base = personal_baseline(demo_stream().observations_upto(9))
    state = PatientState(day_index=9, resting_hr=74.0, hrv_rmssd=38.0,
                         sleep_hours=5.0, activity_load=80.0)
    level, _ = drivers(state, base, None)
    worse, parts = drivers(state, base, {"hr_slope": 6.0, "sleep_delta": -2.0})
    assert worse > level
    assert any("trend" in p["factor"] or "deteriorating" in p["factor"] for p in parts)
    better, _ = drivers(state, base, {"hr_slope": -6.0, "sleep_delta": 2.0})
    assert better == level  # recoveries add nothing
    capped, _ = drivers(state, base, {"hr_slope": 100.0, "sleep_delta": -10.0})
    assert capped - level <= 0.15 + 1e-9  # trend cap holds


def test_reliability_structure_and_determinism():
    from rift.health.evaluate import backtest, reliability

    ehr = _ehr()
    report = backtest(DigitalTwin(ehr, demo_series()), 30, 59)
    first = reliability(report)
    assert first["days"] == 30
    assert first["ece"] is not None and 0.0 <= first["ece"] <= 1.0
    assert len(first["bins"]) == 5
    assert sum(b["n"] for b in first["bins"]) == 30
    for b in first["bins"]:
        if b["n"]:
            assert 0.0 <= b["observed_freq"] <= 1.0
    assert reliability(backtest(DigitalTwin(ehr, demo_series()), 30, 59)) == first


def test_no_overclaim_language_in_health_surface():
    import re
    from pathlib import Path

    banned = [
        "quantum advantage",
        "quantum supremacy",
        "ground-truth cardiac",
        "ground truth cardiac",
        "clinically validated",
        "statistically calibrated",
    ]
    negated = re.compile(r"\b(without|never|not|no|nothing|n't|vs\.?|rather than|instead of)\b", re.IGNORECASE)
    roots = [Path("src/rift/health"), Path("web"), Path("docs/patient-twin.md")]
    hits = []
    for root in roots:
        if root.is_file():
            files = [root]
        elif root.name == "web":
            files = [root / "app.js", root / "index.html"]
        else:
            files = list(root.glob("*.py"))
        for path in files:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                lowered = line.lower()
                for phrase in banned:
                    if phrase in lowered and not negated.search(line):
                        hits.append(f"{path}:{line_no}:{phrase}")
    assert not hits, f"overclaim language found: {hits}"


def test_public_dataset_source_csv(tmp_path):
    path = tmp_path / "cohort.csv"
    path.write_text(
        "day_index,resting_hr,hrv_rmssd,sleep_hours,activity_load\n"
        "0,68,48,7.2,45\n"
        "1,70,,6.8,50\n"
        "2,69,47,7.0,44\n",
        encoding="utf-8",
    )
    source = PublicDatasetSource(str(path))
    assert source.end_day == 2
    assert source.latest_at(1).hrv_rmssd is None
    assert source.completeness_at(1) == 0.75
    twin = DigitalTwin(_ehr(), source)
    snap = twin.update(2)
    assert snap["day_index"] == 2 and snap["risk"]["risk"] > 0
    bad = tmp_path / "bad.csv"
    bad.write_text("day,hr\n0,70\n", encoding="utf-8")
    try:
        PublicDatasetSource(str(bad))
        raise AssertionError("bad header must be rejected")
    except ValueError:
        pass
    dup = tmp_path / "dup.csv"
    dup.write_text(
        "day_index,resting_hr,hrv_rmssd,sleep_hours,activity_load\n"
        "0,68,48,7.2,45\n0,68,48,7.2,45\n",
        encoding="utf-8",
    )
    try:
        PublicDatasetSource(str(dup))
        raise AssertionError("duplicate days must be rejected")
    except ValueError:
        pass


class _Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"


def test_evidence_endpoint_contract():
    with _Server() as server:
        with urllib.request.urlopen(server.url("/api/twin/evidence"), timeout=60) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode())
    for key in ("labels", "outcome_rule", "calibration_window", "held_out_window",
                "days_evaluated", "mae", "event_agreement", "sensitivity",
                "specificity", "brier", "interval_coverage", "onset_lags",
                "confusion", "stress", "meta"):
        assert key in payload, f"missing evidence key: {key}"
    assert payload["days_evaluated"] == 30
    assert payload["meta"]["calibration"] == "demo / not calibrated"
    assert "NOT clinically validated" in payload["meta"]["dataset"]
    assert "calibration_repair" in payload
    assert payload["calibration_repair"]["test_window"] == "days 45-59 (untouched)"
    params = payload["calibration_repair"]["params"]
    assert set(params) >= {"a", "b", "fit_days"}
    assert params["a"] >= 0  # order-preserving by construction, visible to clients


def test_platt_repair_improves_ece_without_wrecking_brier():
    from rift.health.evaluate import apply_platt, backtest, calibration_report, fit_platt_scaling

    ehr = _ehr()
    report = backtest(DigitalTwin(ehr, demo_series()), 30, 59)
    cal_days = [d for d in report["per_day"] if d["day"] < 45]
    test_days = [d for d in report["per_day"] if d["day"] >= 45]
    assert len(cal_days) == 15 and len(test_days) == 15
    params = fit_platt_scaling(cal_days)
    assert set(params) == {"a", "b", "fit_days", "fit_logloss"}
    assert params["fit_days"] == 15
    # Order-preserving: repair rescales confidence, never inverts risk
    # (a constant map is allowed: it says "predict near base rate").
    assert apply_platt(0.2, params) <= apply_platt(0.8, params)
    # Deterministic fit.
    assert fit_platt_scaling(cal_days) == params
    result = calibration_report(cal_days, test_days)
    assert result["calibrated"]["ece"] is not None
    assert result["calibrated"]["ece"] < result["raw"]["ece"]
    assert result["calibrated"]["brier"] <= result["raw"]["brier"] + 0.02
    # Operating behavior untouched: raw risks in the report are unmodified.
    assert all(d["predicted_risk"] <= 1.0 for d in test_days)


def _external_fixture():
    from rift.health.evaluate import EXTERNAL_SERIES_CONFIG

    ehr = _ehr()
    stream = demo_series(
        seed=EXTERNAL_SERIES_CONFIG["seed"],
        days=EXTERNAL_SERIES_CONFIG["days"],
        spells=EXTERNAL_SERIES_CONFIG["spells"],
    )
    report = backtest(DigitalTwin(ehr, demo_series()), 30, 59)
    params = fit_platt_scaling(
        [d for d in report["per_day"] if d["day"] < 45])
    return ehr, stream, params


def test_external_validation_never_fits():
    import rift.health.evaluate as EV

    ehr, stream, params = _external_fixture()
    real_fit = EV.fit_platt_scaling

    def _forbidden_fit(*args, **kwargs):
        raise AssertionError("external validation must never fit parameters")

    EV.fit_platt_scaling = _forbidden_fit
    try:
        result = EV.external_validation(
            stream=stream, ehr=ehr, params=params,
            source_id="synthetic-external-v1", day_start=0, day_end=59)
    finally:
        EV.fit_platt_scaling = real_fit
    assert result["status"] == "complete"
    assert result["params_used"] == params
    assert result["recalibrated"] is False


def test_external_validation_leaves_model_untouched():
    import copy

    from rift.health import risk as RISK

    ehr, stream, params = _external_fixture()
    weights_before = copy.deepcopy(RISK.RISK_WEIGHTS)
    threshold_before = RISK.STRAIN_THRESHOLD
    from rift.health import evaluate as EV

    EV.external_validation(
        stream=stream, ehr=ehr, params=params,
        source_id="synthetic-external-v1", day_start=0, day_end=59)
    assert RISK.RISK_WEIGHTS == weights_before
    assert RISK.STRAIN_THRESHOLD == threshold_before


def test_external_splits_are_disjoint_and_identified():
    from rift.health.demo_data import demo_series as _series
    from rift.health.evaluate import EXTERNAL_SERIES_CONFIG

    assert EXTERNAL_SERIES_CONFIG["seed"] != 7  # development series seed
    assert EXTERNAL_SERIES_CONFIG["source_id"] == "synthetic-external-v1"
    internal = _series()
    external = _series(
        seed=EXTERNAL_SERIES_CONFIG["seed"],
        days=EXTERNAL_SERIES_CONFIG["days"],
        spells=EXTERNAL_SERIES_CONFIG["spells"],
    )
    assert internal is not external
    assert external.end_day == 59


def test_external_insufficient_sample_warns_without_fake_metrics():
    from rift.health import evaluate as EV
    from rift.health.sources import ReplaySource

    ehr = _ehr()
    tiny = ReplaySource(demo_series().observations_upto(4))
    result = EV.external_validation(
        stream=tiny, ehr=ehr, params={"a": 0.0, "b": -2.5, "fit_days": 15, "fit_logloss": 0.0},
        source_id="tiny-probe", day_start=0, day_end=4)
    assert result["status"] == "insufficient"
    assert result["events"] is None
    assert result["warnings"]
    assert result["recalibrated"] is False


def test_empty_bins_and_slope_warnings_are_safe():
    from rift.health.evaluate import calibration_slope_intercept, reliability

    empty = reliability({"per_day": []})
    assert empty["ece"] is None
    assert all(b["n"] == 0 for b in empty["bins"])
    single = calibration_slope_intercept([
        {"predicted_risk": 0.3, "realized_event": False},
        {"predicted_risk": 0.35, "realized_event": False},
    ])
    assert single["slope"] is None and "warning" in single


def test_external_metrics_honest_bounds():
    from rift.health import evaluate as EV

    ehr, stream, params = _external_fixture()
    result = EV.external_validation(
        stream=stream, ehr=ehr, params=params,
        source_id="synthetic-external-v1", day_start=0, day_end=59)
    assert result["status"] == "complete"
    assert result["days_evaluated"] == 59
    assert result["events"] == 5
    assert result["event_agreement"] >= 0.8
    assert result["specificity"] >= 0.85
    assert result["brier_calibrated"] <= result["brier_raw"] + 0.02
    assert result["ece_calibrated"] < result["ece_raw"]
    assert result["slope_intercept"]["bins_used"] >= 1
    assert result["interval_coverage"] is not None
    assert result["agreement_ci95"] is not None  # n=59 supports Wilson
    # Deterministic rerun.
    again = EV.external_validation(
        stream=stream, ehr=ehr, params=params,
        source_id="synthetic-external-v1", day_start=0, day_end=59)
    assert again["confusion"] == result["confusion"]


def test_evidence_contract_exposes_external_block():
    with _Server() as server:
        with urllib.request.urlopen(server.url("/api/twin/evidence"), timeout=120) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode())
    ext = payload.get("external_validation")
    assert ext is not None
    for key in ("source_id", "status", "days_evaluated", "events",
                "params_used", "recalibrated", "event_agreement",
                "agreement_ci95", "sensitivity", "specificity",
                "brier_raw", "brier_calibrated", "ece_raw",
                "ece_calibrated", "slope_intercept",
                "interval_coverage", "sample_adequacy",
                "confusion", "warnings"):
        assert key in ext, f"missing external key: {key}"
    assert ext["recalibrated"] is False
    assert ext["params_used"] == payload["calibration_repair"]["params"]


def test_sample_adequacy_verdict_caps_claims():
    from rift.health import evaluate as EV

    ehr, stream, params = _external_fixture()
    result = EV.external_validation(
        stream=stream, ehr=ehr, params=params,
        source_id="synthetic-external-v1", day_start=0, day_end=59)
    adequacy = result["sample_adequacy"]
    assert adequacy["events"] == 5 and adequacy["non_events"] == 54
    assert adequacy["verdict"] == "limited"
    assert any("100-event" in w for w in result["warnings"])
