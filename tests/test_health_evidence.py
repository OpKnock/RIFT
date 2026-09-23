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
from rift.health.evaluate import OUTCOME_RULE, backtest, realized_outcome, stress_sweep
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
