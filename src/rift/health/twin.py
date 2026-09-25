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
from .model_registry import DEFAULT_MODEL_ID, deployment_gate, weights_digest
from .models import PatientState
from .risk import input_quality, predict
from .robustness import combine_uncertainty, robustness_report
from .sources import WearableSource
from .timeline import timeline_coverage
from .wearable import jitter_score, trend_terms


def prediction_provenance(
    patient_id: str,
    day_index: int,
    state_dict: dict,
    *,
    ehr_dict: dict | None = None,
    baseline_dict: dict | None = None,
    calibration_id: str = "platt/demo-fit-days-30-44",
    source_ids: list[str] | None = None,
) -> dict:
    """Deterministic audit identity for one prediction.

    prediction_id = SHA-256 over the COMPLETE prediction context: patient,
    day, model, live weights digest, synchronized inputs, EHR snapshot,
    baseline snapshot, calibration id, and source observation ids. Any
    change in any input alters the id; re-running identical inputs
    reproduces it. No randomness, no clock.
    """
    import hashlib as _hashlib
    import json as _json

    context = {
        "patient_id": patient_id,
        "day_index": day_index,
        "model_id": DEFAULT_MODEL_ID,
        "weights": weights_digest(),
        "schema_version": "patient-state-v1",
        "inputs": state_dict,
        "ehr": ehr_dict or {},
        "baseline": baseline_dict or {},
        "calibration": calibration_id,
        "source_ids": sorted(source_ids or []),
    }
    canonical = _json.dumps(context, sort_keys=True, separators=(",", ":"))
    return {
        "prediction_id": _hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "model_id": DEFAULT_MODEL_ID,
        "weights_digest": weights_digest(),
        "schema_version": "patient-state-v1",
        "calibration_id": calibration_id,
        "source_ids": sorted(source_ids or []),
        "ehr_hash": _hashlib.sha256(_json.dumps(
            ehr_dict or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "baseline_hash": _hashlib.sha256(_json.dumps(
            baseline_dict or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "input_hash": _hashlib.sha256(_json.dumps(
            state_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "engine": "rift",
    }


class DigitalTwin:
    """Synchronized patient twin over a replayable wearable stream."""

    def __init__(self, ehr: EHRRecord, stream: WearableSource, baseline_window: int = 7,
                 canonical_observations: list | None = None):
        self.ehr = ehr
        self.stream = stream
        self.baseline_window = baseline_window
        self._canonical = list(canonical_observations) if canonical_observations else []
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
                patient_id=latest.patient_id,
                time_offset_hours=latest.time_offset_hours,
                resting_hr=latest.resting_hr,
                hrv_rmssd=latest.hrv_rmssd,
                sleep_hours=latest.sleep_hours,
                activity_load=latest.activity_load,
                heart_rate=latest.heart_rate,
                rr_sd=latest.rr_sd,
                data_quality=self.stream.completeness_at(day_index),
                stale_days=self.stream.stale_days_at(day_index),
                provenance=latest.provenance,
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
        # Decomposition (all heuristic/demo-grade, labeled as such): which
        # uncertainty comes from where, so "the model is uncertain" is never
        # conflated with "the sensor is noisy" or "the input is stale".
        # Components sum to the reported total unless the 0.45 cap binds.
        _qc = 0.30 * (1.0 - input_quality(state))
        _jc = 0.15 * risk_record["measurement_jitter"]
        _sc = robust["worst_case_spread"] / 2
        risk_record["uncertainty_breakdown"] = {
            "base_component": 0.05,
            "quality_component": round(_qc, 4),
            "jitter_component": round(_jc, 4),
            "robustness_spread": round(_sc, 4),
            "cap": 0.45,
            "total": risk_record["uncertainty"],
            "grade": "heuristic-demo",
        }
        lo, hi = risk_record["risk"] - risk_record["uncertainty"], risk_record["risk"] + risk_record["uncertainty"]
        risk_record["interval"] = [max(0.0, lo), min(1.0, hi)]
        risk_record["input_quality"] = input_quality(state)
        coverage = timeline_coverage(self._canonical)
        unestimated = sorted(m for m, status in coverage.items() if status != "estimated")
        futures = counterfactual_futures(state, baseline, self.ehr)
        trajs = trajectories(state, baseline, self.ehr)
        guard = verdict(state, risk_record, self._previous_state, self.ehr,
                        unestimated=tuple(unestimated),
                        counterfactuals=futures,
                        model_context={"model_id": DEFAULT_MODEL_ID,
                                       "weights_digest": weights_digest()},
                        deployment=deployment_gate())
        # Operational telemetry: every produced prediction feeds the
        # in-process collector so /metrics reflects real prediction flow.
        try:
            from .monitoring import collector as _ops_collector

            _ops_collector.record_prediction(
                float(risk_record.get("risk", 0.0) or 0.0),
                str(guard.get("action", "ALLOW") or "ALLOW"),
                1.0 - float(risk_record.get("input_quality", 1.0) or 1.0),
            )
        except Exception:  # nosec B110 -- telemetry must never break the clinical path
            pass
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
            "timeline_coverage": coverage,
            "provenance": prediction_provenance(
                self.ehr.patient_id, day_index, state.to_dict(),
                ehr_dict=self.ehr.to_dict(),
                baseline_dict=baseline.to_dict(),
                source_ids=[latest.provenance] if latest and latest.provenance else [],
            ),
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
