"""Phase-4/7 validation: independent outcomes, temporal splits, calibration.

SOFTWARE validation on synthetic demo data — NOT clinical validation.

Realized outcomes come from an INDEPENDENT labeling rule applied to
observed vitals (`realized_outcome`), never from the model's own risk
function. Phase 7 adds a strict three-way separation — calibration data,
internal untouched test data, external validation data — with no refit,
no threshold tuning, and no weight tuning on the external set.
"""
from __future__ import annotations

import math

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


def _sigmoid(x: float) -> float:
    clamped = max(-500.0, min(500.0, x))
    return 1.0 / (1.0 + math.exp(-clamped))


def fit_platt_scaling(calibration_days: list[dict]) -> dict:
    """Fit p_cal = sigmoid(A * p_raw + B) on CALIBRATION days only.

    Coarse deterministic grid search minimizing log-loss (stdlib only, no
    optimizer dependency). Tie-breaks go to the first grid point in fixed
    order, so the fit is reproducible. Never fit on the test window —
    doing so would turn calibration repair into metric gaming.
    """
    a_grid = [i * 0.5 for i in range(0, 11)]  # A >= 0 only: the map must be
    b_grid = [i * 0.5 for i in range(-10, 11)]  # order-preserving, never invert risk
    best = None
    for a in a_grid:
        for b in b_grid:
            loss = 0.0
            for day in calibration_days:
                p = max(1e-6, min(1 - 1e-6, _sigmoid(a * day["predicted_risk"] + b)))
                y = 1.0 if day["realized_event"] else 0.0
                loss += -(y * math.log(p) + (1 - y) * math.log(1 - p))
            mean_loss = loss / len(calibration_days) if calibration_days else float("inf")
            if best is None or mean_loss < best[0]:
                best = (mean_loss, a, b)
    if best is None:  # unreachable with a non-empty grid; explicit instead of assert
        raise ValueError("calibration grid produced no candidate")
    return {"a": best[1], "b": best[2], "fit_days": len(calibration_days), "fit_logloss": best[0]}


def apply_platt(p_raw: float, params: dict) -> float:
    """Apply fitted Platt parameters to one raw probability."""
    return _sigmoid(params["a"] * p_raw + params["b"])


def _brier_of(per_day: list[dict], key: str = "predicted_risk") -> float | None:
    if not per_day:
        return None
    return sum((d[key] - (1.0 if d["realized_event"] else 0.0)) ** 2 for d in per_day) / len(per_day)


def calibration_report(
    calibration_days: list[dict],
    test_days: list[dict],
    bins: int = 5,
) -> dict:
    """Repair check: fit Platt scaling on calibration days, score untouched test days.

    Returns raw vs calibrated Brier/ECE/agreement on the TEST window only,
    plus the fitted parameters and both windows' sizes. The operating
    threshold and all model weights stay fixed — only the reported
    probability mapping is adjusted, and only from calibration data.
    """
    params = fit_platt_scaling(calibration_days)
    calibrated_test = [
        {**d, "predicted_risk": apply_platt(d["predicted_risk"], params)} for d in test_days
    ]
    raw_report = {"per_day": test_days}
    cal_report = {"per_day": calibrated_test}
    raw_rel = reliability(raw_report, bins)
    cal_rel = reliability(cal_report, bins)
    return {
        "params": params,
        "calibration_days": len(calibration_days),
        "test_days": len(test_days),
        "raw": {
            "brier": _brier_of(test_days),
            "ece": raw_rel["ece"],
            "reliability": raw_rel,
        },
        "calibrated": {
            "brier": _brier_of(calibrated_test),
            "ece": cal_rel["ece"],
            "reliability": cal_rel,
        },
    }


# External validation series: independent seed AND independent spell
# schedule from anything used in model development, calibration fitting,
# threshold selection, or reporting. Synthetic — an independence upgrade
# over reusing one series, not external real-world evidence.
EXTERNAL_SERIES_CONFIG = {
    "source_id": "synthetic-external-v1",
    "seed": 123,
    "days": 60,
    "spells": ((15, 2), (33, 2), (50, 1)),
}

MIN_EXTERNAL_DAYS = 10
MIN_EVENTS_FOR_RATES = 5
WILSON_Z = 1.96


def _wilson_interval(p_hat: float, n: int) -> tuple[float, float] | None:
    """Wilson 95% interval for a rate. Omitted (None) when n < 30."""
    if n < 30 or not 0.0 <= p_hat <= 1.0:
        return None
    z = WILSON_Z
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def calibration_slope_intercept(per_day: list[dict], bins: int = 5) -> dict:
    """WLS line through non-empty reliability bins: observed_freq ~ mean_predicted.

    Slope ≈ 1 and intercept ≈ 0 mean calibrated; deviations show systematic
    over/under-confidence. Unstable with < 3 populated bins — flagged, and
    the estimate is still reported (never hidden) with its bin count.
    """
    rel = reliability({"per_day": per_day}, bins)
    populated = [b for b in rel["bins"] if b["n"]]
    if len(populated) < 2:
        return {"slope": None, "intercept": None, "bins_used": len(populated),
                "warning": "fewer than 2 populated bins: slope/intercept not estimable"}
    sx = sum(b["n"] * b["mean_predicted"] for b in populated)
    sy = sum(b["n"] * b["observed_freq"] for b in populated)
    sw = sum(b["n"] for b in populated)
    mx, my = sx / sw, sy / sw
    denom = sum(b["n"] * (b["mean_predicted"] - mx) ** 2 for b in populated)
    if denom <= 0:
        return {"slope": None, "intercept": None, "bins_used": len(populated),
                "warning": "no spread in predicted probabilities: slope/intercept not estimable"}
    slope = sum(b["n"] * (b["mean_predicted"] - mx) * (b["observed_freq"] - my) for b in populated) / denom
    result: dict = {"slope": slope, "intercept": my - slope * mx, "bins_used": len(populated)}
    if len(populated) < 3:
        result["warning"] = "fewer than 3 populated bins: slope/intercept unstable"
    return result


def external_validation(
    *,
    stream,
    ehr: EHRRecord,
    params: dict,
    source_id: str,
    day_start: int = 0,
    day_end: int | None = None,
) -> dict:
    """Validate the EXISTING pipeline on data used for nothing else.

    Applies the current risk model unchanged and the GIVEN Platt params
    unchanged (no refit — verified by tests that patch the fitter to raise).
    Operating threshold and weights are never touched. Event decisions use
    raw risk (the deployed rule); probabilities are reported raw and
    calibrated side by side.
    """
    last_day = stream.end_day if day_end is None else day_end
    days = list(range(day_start, last_day))  # need day+1 observations for labels
    warnings: list[str] = []
    if len(days) < MIN_EXTERNAL_DAYS:
        warnings.append(
            f"only {len(days)} evaluable days (< {MIN_EXTERNAL_DAYS}): "
            "metrics omitted, no confidence intervals manufactured"
        )
        return {
            "source_id": source_id,
            "status": "insufficient",
            "days_evaluated": len(days),
            "events": None,
            "params_used": params,
            "recalibrated": False,
            "sample_adequacy": None,
            "warnings": warnings,
        }
    twin = DigitalTwin(ehr, stream)
    per_day: list[dict] = []
    hits = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    covered = 0
    for day in days:
        snap = twin.update(day)
        actual = stream.latest_at(day + 1)
        if actual is None:
            continue
        realized, criteria = realized_outcome(actual)
        raw_risk = snap["risk"]["risk"]
        cal_risk = apply_platt(raw_risk, params)
        predicted = raw_risk >= STRAIN_THRESHOLD
        if predicted and realized:
            hits["tp"] += 1
        elif not predicted and not realized:
            hits["tn"] += 1
        elif predicted and not realized:
            hits["fp"] += 1
        else:
            hits["fn"] += 1
        lo, hi = snap["risk"]["interval"]
        _, realized_risk_legacy = realized_label(
            PatientState(
                day_index=day + 1,
                resting_hr=actual.resting_hr,
                hrv_rmssd=actual.hrv_rmssd,
                sleep_hours=actual.sleep_hours,
                activity_load=actual.activity_load,
            ),
            personal_baseline([o for o in stream.observations_upto(day) if o.day_index < day]),
            ehr,
        )
        covered += 1 if lo <= realized_risk_legacy <= hi else 0
        per_day.append({
            "day": day,
            "predicted_risk": raw_risk,
            "calibrated_risk": cal_risk,
            "realized_event": realized,
            "realized_criteria": criteria,
        })
    total = hits["tp"] + hits["tn"] + hits["fp"] + hits["fn"]
    agreement = (hits["tp"] + hits["tn"]) / total if total else None
    events = hits["tp"] + hits["fn"]
    non_events = hits["tn"] + hits["fp"]
    if events < MIN_EVENTS_FOR_RATES:
        warnings.append(
            f"only {events} positive events (< {MIN_EVENTS_FOR_RATES}): "
            "sensitivity/specificity are unstable"
        )
    # Sample-adequacy verdict against a CONSERVATIVE bar (not a law):
    # >=100 events and >=100 non-events. Required size truly depends on
    # precision targets, event prevalence, expected calibration, and risk
    # distribution — published guidance notes substantially more is
    # sometimes needed. Below the bar, calibration claims stay capped at
    # strong partial no matter how good the point metrics look.
    adequacy = {
        "events": events,
        "non_events": non_events,
        "events_required": 100,
        "non_events_required": 100,
        "bar": "conservative bar: >=100 events and >=100 non-events; "
               "larger samples may be needed depending on precision targets",
        "verdict": "adequate" if events >= 100 and non_events >= 100 else "limited",
    }
    if adequacy["verdict"] != "adequate":
        warnings.append(
            f"external sample below the 100-event/100-non-event adequacy bar "
            f"({events} events, {non_events} non-events): calibration remains "
            "strong partial, not complete"
        )
    cal_report_like = {"per_day": [
        {"predicted_risk": d["calibrated_risk"], "realized_event": d["realized_event"]} for d in per_day
    ]}
    raw_report_like = {"per_day": [
        {"predicted_risk": d["predicted_risk"], "realized_event": d["realized_event"]} for d in per_day
    ]}
    slope = calibration_slope_intercept(cal_report_like["per_day"])
    return {
        "source_id": source_id,
        "status": "complete",
        "days_evaluated": len(per_day),
        "events": events,
        "params_used": params,
        "recalibrated": False,
        "event_agreement": agreement,
        "agreement_ci95": _wilson_interval(agreement, len(per_day)) if agreement is not None else None,
        "sensitivity": hits["tp"] / (hits["tp"] + hits["fn"]) if (hits["tp"] + hits["fn"]) else None,
        "specificity": hits["tn"] / (hits["tn"] + hits["fp"]) if (hits["tn"] + hits["fp"]) else None,
        "brier_raw": _brier_of(raw_report_like["per_day"]),
        "brier_calibrated": _brier_of(cal_report_like["per_day"], key="predicted_risk"),
        "ece_raw": reliability(raw_report_like)["ece"],
        "ece_calibrated": reliability(cal_report_like)["ece"],
        "slope_intercept": slope,
        "interval_coverage": covered / len(per_day) if per_day else None,
        "sample_adequacy": adequacy,
        "confusion": hits,
        "warnings": warnings,
        "per_day": per_day,
    }
