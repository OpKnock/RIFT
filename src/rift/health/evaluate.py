"""Phase-4 validation: independent outcomes, temporal splits, calibration.

SOFTWARE validation on synthetic demo data — NOT clinical validation.

The critical Phase-4 change vs Phase 3: realized outcomes come from an
INDEPENDENT labeling rule applied to observed vitals
(`realized_outcome`), never from the model's own risk function. The model
and the label can therefore disagree — and the metrics report that
honestly, including onset lag and misses.
"""
from __future__ import annotations

from .baseline import personal_baseline
from .ehr import EHRRecord
from .foresight import counterfactual_futures
from .models import PatientState, WearableObservation
from .risk import STRAIN_THRESHOLD, predict
from .robustness import degrade_noisy
from .transition import transition
from .twin import DigitalTwin
from .wearable import jitter_score

FIELDS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")

# Synthetic outcome definition v1 (independent of the risk weights and of
# any personal baseline): a high-strain day is OBSERVED tachycardia plus an
# OBSERVED recovery deficit. Absolute criteria, no model involved.
OUTCOME_RULE = {
    "description": "observed resting_hr >= 75 AND (sleep_hours <= 5.5 OR hrv_rmssd <= 35)",
    "resting_hr_min": 75.0,
    "sleep_max": 5.5,
    "hrv_max": 35.0,
}


def realized_outcome(obs: WearableObservation) -> tuple[bool, list[str]]:
    """Independent label from observed vitals. Returns (event, fired_criteria)."""
    if obs is None:
        return False, []
    hr = obs.resting_hr
    if hr is None or hr < OUTCOME_RULE["resting_hr_min"]:
        return False, []
    fired = [f"resting_hr {hr:.0f} >= {OUTCOME_RULE['resting_hr_min']:.0f}"]
    sleep_bad = obs.sleep_hours is not None and obs.sleep_hours <= OUTCOME_RULE["sleep_max"]
    hrv_bad = obs.hrv_rmssd is not None and obs.hrv_rmssd <= OUTCOME_RULE["hrv_max"]
    if sleep_bad:
        fired.append(f"sleep {obs.sleep_hours:.1f}h <= {OUTCOME_RULE['sleep_max']:.1f}h")
    if hrv_bad:
        fired.append(f"hrv {obs.hrv_rmssd:.0f}ms <= {OUTCOME_RULE['hrv_max']:.0f}ms")
    if not (sleep_bad or hrv_bad):
        return False, []
    return True, fired


def realized_label(state: PatientState, baseline, ehr: EHRRecord) -> tuple[bool, float]:
    """Legacy self-consistency label (model scored on observed vitals).

    Kept for regression continuity; Phase-4 metrics use realized_outcome.
    """
    record = predict(state, baseline, ehr)
    return record["risk"] >= STRAIN_THRESHOLD, record["risk"]


def backtest(
    twin: DigitalTwin,
    start_day: int = 7,
    end_day: int = 12,
    *,
    independent_labels: bool = True,
) -> dict:
    """Rolling-origin replay over days [start_day, end_day].

    For each day t: the twin predicts from state_t (baseline strictly
    before t); labels come from the INDEPENDENT outcome rule on day-(t+1)
    observations when independent_labels=True. Reports MAE, event metrics,
    Brier, interval coverage, onset lead/lag, and a per-day table.
    """
    stream = twin.stream
    ehr = twin.ehr
    mae = {f: [] for f in FIELDS}
    hits = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    brier_terms: list[float] = []
    covered = 0
    evaluated = 0
    lags: list[int] = []
    per_day: list[dict] = []
    for day in range(start_day, end_day + 1):
        snap = twin.update(day)
        state = twin.synchronize(day)
        baseline = personal_baseline([o for o in stream.observations_upto(day) if o.day_index < day])
        predicted = transition({f: getattr(state, f) for f in FIELDS}, ehr, {})
        actual_obs = stream.latest_at(day + 1)
        if actual_obs is None:
            continue
        day_mae = {}
        for field in FIELDS:
            pred, actual = predicted.get(field), getattr(actual_obs, field)
            if pred is not None and actual is not None:
                mae[field].append(abs(pred - actual))
                day_mae[field] = abs(pred - actual)
        if independent_labels:
            realized_event, criteria = realized_outcome(actual_obs)
            actual_state = PatientState(
                day_index=day + 1,
                resting_hr=actual_obs.resting_hr,
                hrv_rmssd=actual_obs.hrv_rmssd,
                sleep_hours=actual_obs.sleep_hours,
                activity_load=actual_obs.activity_load,
            )
            _, realized_risk = realized_label(actual_state, baseline, ehr)
        else:
            actual_state = PatientState(
                day_index=day + 1,
                resting_hr=actual_obs.resting_hr,
                hrv_rmssd=actual_obs.hrv_rmssd,
                sleep_hours=actual_obs.sleep_hours,
                activity_load=actual_obs.activity_load,
            )
            realized_event, realized_risk = realized_label(actual_state, baseline, ehr)
            criteria = ["legacy self-consistency label"]
        predicted_event = snap["risk"]["event_predicted"]
        predicted_risk = snap["risk"]["risk"]
        if predicted_event and realized_event:
            hits["tp"] += 1
        elif not predicted_event and not realized_event:
            hits["tn"] += 1
        elif predicted_event and not realized_event:
            hits["fp"] += 1
        else:
            hits["fn"] += 1
        brier_terms.append((predicted_risk - (1.0 if realized_event else 0.0)) ** 2)
        lo, hi = snap["risk"]["interval"]
        covered += 1 if lo <= realized_risk <= hi else 0
        evaluated += 1
        per_day.append({
            "day": day,
            "predicted_risk": predicted_risk,
            "realized_risk": realized_risk,
            "predicted_event": predicted_event,
            "realized_event": realized_event,
            "realized_criteria": criteria,
            "mae": day_mae,
        })
    # Onset lead/lag: for each realized event, offset of the first predicted
    # event within the two preceding days (negative = prediction came late).
    pred_days = {d["day"] for d in per_day if d["predicted_event"]}
    for d in per_day:
        if d["realized_event"]:
            earlier = [p for p in pred_days if d["day"] - 2 <= p <= d["day"]]
            lags.append(min(earlier) - d["day"] if earlier else -99)
    total = hits["tp"] + hits["tn"] + hits["fp"] + hits["fn"]
    return {
        "days_evaluated": evaluated,
        "labels": "independent-outcome-v1" if independent_labels else "legacy-self-consistency",
        "outcome_rule": OUTCOME_RULE["description"],
        "mae": {f: (sum(v) / len(v) if v else None) for f, v in mae.items()},
        "event_agreement": (hits["tp"] + hits["tn"]) / total if total else None,
        "sensitivity": hits["tp"] / (hits["tp"] + hits["fn"]) if (hits["tp"] + hits["fn"]) else None,
        "specificity": hits["tn"] / (hits["tn"] + hits["fp"]) if (hits["tn"] + hits["fp"]) else None,
        "brier": sum(brier_terms) / len(brier_terms) if brier_terms else None,
        "interval_coverage": covered / evaluated if evaluated else None,
        "onset_lags": lags,
        "mean_onset_lag": sum(lags) / len(lags) if lags else None,
        "confusion": hits,
        "per_day": per_day,
    }


def stress_sweep(
    stream,
    ehr: EHRRecord,
    days: list[int],
    magnitudes: tuple[float, ...] = (0.0, 0.05, 0.15),
    seed: int = 7,
) -> dict:
    """Robustness stress test: rising sensor noise vs agreement + uncertainty.

    Replays each day with noisy inputs; agreement must degrade gracefully
    (no crashes, no wild swings) while mean uncertainty is non-decreasing.
    """
    from .twin import DigitalTwin as _Twin

    rows = []
    for magnitude in magnitudes:
        agreements: list[bool] = []
        uncertainties: list[float] = []
        jitters: list[float] = []
        for day in days:
            twin = _Twin(ehr, stream)
            snap = twin.update(day)
            noisy_state = degrade_noisy(twin.synchronize(day), seed=seed, magnitude=magnitude)
            yesterday = stream.latest_at(day - 1) if day > 0 else None
            prior = [o for o in stream.observations_upto(day) if o.day_index < day]
            jitter = jitter_score(noisy_state, yesterday, prior)
            baseline = personal_baseline(prior)
            record = predict(noisy_state, baseline, ehr, measurement_jitter=jitter)
            actual = stream.latest_at(day + 1)
            if actual is None:
                continue
            realized, _ = realized_outcome(actual)
            agreements.append((record["risk"] >= STRAIN_THRESHOLD) == realized)
            uncertainties.append(record["uncertainty"])
            jitters.append(jitter)
        rows.append({
            "noise_magnitude": magnitude,
            "days": len(agreements),
            "agreement": sum(agreements) / len(agreements) if agreements else None,
            "mean_uncertainty": sum(uncertainties) / len(uncertainties) if uncertainties else None,
            "mean_jitter": sum(jitters) / len(jitters) if jitters else None,
        })
    mean_u = [r["mean_uncertainty"] for r in rows if r["mean_uncertainty"] is not None]
    return {
        "rows": rows,
        "uncertainty_non_decreasing": all(b >= a for a, b in zip(mean_u, mean_u[1:])),
        "severities": list(magnitudes),
    }


def counterfactual_sanity(state: PatientState, baseline, ehr: EHRRecord) -> dict:
    """Interventions must not worsen nominal risk vs doing nothing (monotone weights)."""
    out = counterfactual_futures(state, baseline, ehr)
    risks = {tuple(sorted(p["policy"].items())): p["risk"] for p in out["policies"]}
    none_key = (("exertion_cut", 0), ("sleep_plus", 0))
    checks = {}
    for key, risk in risks.items():
        if key == none_key:
            continue
        checks["-".join(f"{k}={v}" for k, v in key)] = risk <= risks[none_key] + 1e-9
    return {"nominal_risks": {str(k): v for k, v in risks.items()}, "all_improve_or_equal": all(checks.values()), "checks": checks}


def threshold_tradeoff(
    backtest_report: dict,
    thresholds: tuple[float, ...] = (0.4, 0.5, 0.6, 0.7, 0.8),
) -> dict:
    """Sensitivity/specificity across operating thresholds from one backtest.

    Characterization, NOT tuning: the deployed threshold stays
    STRAIN_THRESHOLD. Lowering it to chase sensitivity would trade certain
    specificity for uncertain gains — this table makes that tradeoff
    explicit instead of hiding it behind a single operating point.
    """
    rows = []
    for threshold in thresholds:
        tp = tn = fp = fn = 0
        for day in backtest_report.get("per_day", []):
            predicted = day["predicted_risk"] >= threshold
            realized = day["realized_event"]
            if predicted and realized:
                tp += 1
            elif not predicted and not realized:
                tn += 1
            elif predicted and not realized:
                fp += 1
            else:
                fn += 1
        total = tp + tn + fp + fn
        rows.append({
            "threshold": threshold,
            "sensitivity": tp / (tp + fn) if (tp + fn) else None,
            "specificity": tn / (tn + fp) if (tn + fp) else None,
            "agreement": (tp + tn) / total if total else None,
        })
    return {"operating_threshold": STRAIN_THRESHOLD, "rows": rows}


def reliability(backtest_report: dict, bins: int = 5) -> dict:
    """Empirical calibration: predicted risk vs observed event frequency.

    Equal-width bins over predicted probability; per bin the mean prediction
    and the realized frequency, plus the expected calibration error (ECE).
    On synthetic held-out data this measures whether the probability output
    behaves like a probability — a calibration mechanism check, not a
    clinical calibration claim.
    """
    days = backtest_report.get("per_day", [])
    edges = [i / bins for i in range(bins + 1)]
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        in_bin = [d for d in days if lo <= d["predicted_risk"] < hi or (hi == 1.0 and d["predicted_risk"] == 1.0)]
        if not in_bin:
            rows.append({"bin": [lo, hi], "n": 0, "mean_predicted": None, "observed_freq": None})
            continue
        mean_pred = sum(d["predicted_risk"] for d in in_bin) / len(in_bin)
        freq = sum(1 for d in in_bin if d["realized_event"]) / len(in_bin)
        rows.append({"bin": [lo, hi], "n": len(in_bin), "mean_predicted": mean_pred, "observed_freq": freq})
    total = sum(r["n"] for r in rows)
    ece = (
        sum(r["n"] / total * abs(r["mean_predicted"] - r["observed_freq"]) for r in rows if r["n"])
        if total else None
    )
    return {"bins": rows, "ece": ece, "days": total}
