"""Phase-3 validation: backtest, trajectory accuracy, calibration, sanity.

SOFTWARE validation on synthetic demo data — NOT clinical validation.
The "realized" labels below come from observed demo vitals scored with the
same transparent risk function, so these metrics measure pipeline
self-consistency, determinism, and honest uncertainty — never medical truth.
"""
from __future__ import annotations

from .baseline import personal_baseline
from .ehr import EHRRecord
from .foresight import counterfactual_futures
from .models import PatientState
from .risk import STRAIN_THRESHOLD, predict
from .transition import transition
from .twin import DigitalTwin
from .wearable import WearableStream

FIELDS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")


def realized_label(state: PatientState, baseline, ehr: EHRRecord) -> tuple[bool, float]:
    """Score OBSERVED vitals with the risk function: did a high-strain day occur?"""
    record = predict(state, baseline, ehr)
    return record["risk"] >= STRAIN_THRESHOLD, record["risk"]


def backtest(twin: DigitalTwin, start_day: int = 7, end_day: int = 12) -> dict:
    """Replay days [start_day, end_day]: 1-day-ahead vitals vs actuals.

    For each day t: transition(state_t) predicts vitals for t+1; compare
    against the observed day-(t+1) sample. Also compares the predicted event
    against the realized label, Brier score, and interval coverage.
    """
    stream = twin.stream
    ehr = twin.ehr
    mae = {f: [] for f in FIELDS}
    hits = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    brier_terms: list[float] = []
    covered = 0
    evaluated = 0
    per_day: list[dict] = []
    for day in range(start_day, end_day + 1):
        snap = twin.update(day)
        state = twin.synchronize(day)
        baseline = personal_baseline(stream.observations_upto(day))
        predicted = transition(
            {f: getattr(state, f) for f in FIELDS}, ehr, {}
        )
        actual_obs = stream.latest_at(day + 1)
        if actual_obs is None:
            continue
        day_mae = {}
        for field in FIELDS:
            pred, actual = predicted.get(field), getattr(actual_obs, field)
            if pred is not None and actual is not None:
                mae[field].append(abs(pred - actual))
                day_mae[field] = abs(pred - actual)
        actual_state = PatientState(
            day_index=day + 1,
            resting_hr=actual_obs.resting_hr,
            hrv_rmssd=actual_obs.hrv_rmssd,
            sleep_hours=actual_obs.sleep_hours,
            activity_load=actual_obs.activity_load,
        )
        realized_event, realized_risk = realized_label(actual_state, baseline, ehr)
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
            "mae": day_mae,
        })
    total = hits["tp"] + hits["tn"] + hits["fp"] + hits["fn"]
    return {
        "days_evaluated": evaluated,
        "mae": {f: (sum(v) / len(v) if v else None) for f, v in mae.items()},
        "event_agreement": (hits["tp"] + hits["tn"]) / total if total else None,
        "sensitivity": hits["tp"] / (hits["tp"] + hits["fn"]) if (hits["tp"] + hits["fn"]) else None,
        "specificity": hits["tn"] / (hits["tn"] + hits["fp"]) if (hits["tn"] + hits["fp"]) else None,
        "brier": sum(brier_terms) / len(brier_terms) if brier_terms else None,
        "interval_coverage": covered / evaluated if evaluated else None,
        "confusion": hits,
        "per_day": per_day,
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
