"""Digital Twin core loop: observe → synchronize → predict → update → recompute.

EHR + wearable observations → PatientState → synchronized twin →
future prediction → new observation → update state → recompute futures.
History is a JSON-safe append-only log, replayable by construction.
"""
from __future__ import annotations

from .baseline import deviations, personal_baseline
from .decision import decision_table
from .ehr import EHRRecord
from .explain import build_reasons
from .foresight import counterfactual_futures, trajectories
from .guardian import verdict
from .model_registry import DEFAULT_MODEL_ID, weights_digest
from .models import PatientState
from .risk import input_quality, predict
from .robustness import combine_uncertainty, robustness_report
from .sources import WearableSource
from .wearable import jitter_score, trend_terms


def prediction_provenance(patient_id: str, day_index: int, state_dict: dict) -> dict:
    """Deterministic audit identity for one prediction.

    prediction_id = SHA-256 over (patient, day, model, live weights digest,
    canonical input snapshot). Re-running the same inputs reproduces the
    same id; any weight or input change alters it. No randomness, no clock.
    """
    import hashlib as _hashlib
    import json as _json

    canonical = _json.dumps(
        {"patient_id": patient_id, "day_index": day_index,
         "model_id": DEFAULT_MODEL_ID, "weights": weights_digest(),
         "inputs": state_dict},
        sort_keys=True, separators=(",", ":"),
    )
    return {
        "prediction_id": _hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "model_id": DEFAULT_MODEL_ID,
        "weights_digest": weights_digest(),
        "engine": "rift",
    }


class DigitalTwin:
    """Synchronized patient twin over a replayable wearable stream."""

    def __init__(self, ehr: EHRRecord, stream: WearableSource, baseline_window: int = 7):
        self.ehr = ehr
        self.stream = stream
        self.baseline_window = baseline_window
        self.history: list[dict] = []
        self._previous_state: PatientState | None = None

    def synchronize(self, day_index: int) -> PatientState:
        """Fold all observations up to day_index into one PatientState."""
        latest = self.stream.latest_at(day_index)
        if latest is None:
            state = PatientState(day_index=day_index, data_quality=0.0, stale_days=day_index)
        else:
            state = PatientState(
                day_index=day_index,
                resting_hr=latest.resting_hr,
                hrv_rmssd=latest.hrv_rmssd,
                sleep_hours=latest.sleep_hours,
                activity_load=latest.activity_load,
                data_quality=self.stream.completeness_at(day_index),
                stale_days=self.stream.stale_days_at(day_index),
            )
        return state

    def update(self, day_index: int) -> dict:
        """One full loop step; appends the snapshot to history and returns it."""
        state = self.synchronize(day_index)
        history = self.stream.observations_upto(day_index)
        # No leakage: the baseline for day t uses only observations BEFORE t,
        # so an abnormal today can never redefine what "normal" means today.
        prior = [o for o in history if o.day_index < day_index]
        baseline = personal_baseline(prior, self.baseline_window)
        devs = deviations(state, baseline)
        latest = self.stream.latest_at(day_index)
        previous_obs = self.stream.latest_at(day_index - 1) if day_index > 0 else None
        jitter = jitter_score(latest, previous_obs, prior)
        trend = trend_terms(latest, previous_obs)
        risk_record = predict(state, baseline, self.ehr, measurement_jitter=jitter, trend=trend)
        robust = robustness_report(state, baseline, self.ehr)
        risk_record = dict(risk_record)
        risk_record["uncertainty"] = combine_uncertainty(risk_record["uncertainty"], robust["worst_case_spread"])
        lo, hi = risk_record["risk"] - risk_record["uncertainty"], risk_record["risk"] + risk_record["uncertainty"]
        risk_record["interval"] = [max(0.0, lo), min(1.0, hi)]
        risk_record["input_quality"] = input_quality(state)
        guard = verdict(state, risk_record, self._previous_state, self.ehr)
        futures = counterfactual_futures(state, baseline, self.ehr)
        trajs = trajectories(state, baseline, self.ehr)
        best_traj = min(trajs, key=lambda t: t["path"][-1]["risk"])
        note = (
            f"Best trajectory ends at risk {best_traj['path'][-1]['risk']:.2f} "
            f"under policy {best_traj['policy']} over {len(best_traj['path']) - 1} days."
        )
        reasons = build_reasons(state, baseline, devs, self.ehr, risk_record, guard, note)
        snapshot = {
            "day_index": day_index,
            "patient_id": self.ehr.patient_id,
            "ehr": self.ehr.to_dict(),
            "state": state.to_dict(),
            "baseline": baseline.to_dict(),
            "deviations": [d.to_dict() for d in devs],
            "risk": risk_record,
            "robustness": robust,
            "guardian": guard,
            "futures": futures,
            "trajectories": trajs,
            "decision_table": decision_table(futures["robust_ranking"], trajs),
            "reasons": reasons,
            "provenance": prediction_provenance(
                self.ehr.patient_id, day_index, state.to_dict()),
            "model_notes": "synthetic demo weights; decision support only, not validated care",
        }
        self.history.append(snapshot)
        self._previous_state = state
        return snapshot

    def replay(self, start_day: int, end_day: int) -> list[dict]:
        """Replay the loop across a day range; returns all snapshots."""
        return [self.update(day) for day in range(start_day, end_day + 1)]

    def to_dict(self) -> dict:
        return {
            "patient_id": self.ehr.patient_id,
            "ehr": self.ehr.to_dict(),
            "baseline_window": self.baseline_window,
            "history": self.history,
        }
