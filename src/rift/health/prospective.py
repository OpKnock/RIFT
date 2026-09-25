"""Prospective evaluation manager: locked predictions, no retro-refit (Phase 16).

Predictions are frozen at issuance time; outcomes are reconciled only
when they arrive later. Re-evaluating a past prediction never revises it
— it only records the realized label. This prevents future-label leakage
that retrospective backtests risk.
"""
from __future__ import annotations

import hashlib
import json
import time


class ProspectiveManager:
    """In-memory prospective ledger. Deterministic, no clock leakage.

    Each prediction is stored with its issuance day and input hash;
    outcome arrival is a separate step that records (not mutates) the
    locked prediction.
    """

    def __init__(self) -> None:
        self._predictions: dict[str, dict] = {}
        self._outcomes: dict[str, dict] = {}

    @staticmethod
    def _lock_id(patient_id: str, day: int, predicted_risk: float,
                 predicted_event: bool, input_hash: str) -> str:
        canonical = json.dumps(
            {"patient_id": patient_id, "day": day, "predicted_risk": predicted_risk,
             "predicted_event": bool(predicted_event), "input_hash": input_hash},
            sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def lock_prediction(self, patient_id: str, day: int, predicted_risk: float,
                        predicted_event: bool, input_hash: str) -> dict:
        """Freeze a prediction. Idempotent on same inputs; new id on any change."""
        lock_id = self._lock_id(patient_id, day, predicted_risk, predicted_event, input_hash)
        if lock_id not in self._predictions:
            self._predictions[lock_id] = {
                "lock_id": lock_id, "patient_id": patient_id, "day": day,
                "predicted_risk": predicted_risk, "predicted_event": predicted_event,
                "input_hash": input_hash, "issued_at": time.time(),
            }
        return dict(self._predictions[lock_id])

    def reconcile_outcome(self, lock_id: str, realized_event: bool) -> dict:
        """Attach the observed outcome to a locked prediction."""
        if lock_id not in self._predictions:
            raise KeyError(f"unknown lock_id {lock_id!r}")
        if lock_id in self._outcomes:
            return dict(self._outcomes[lock_id])
        pred = self._predictions[lock_id]
        correct = pred["predicted_event"] == realized_event
        record = {"lock_id": lock_id, "realized_event": realized_event, "correct": correct,
                  "reconciled_at": time.time()}
        self._outcomes[lock_id] = record
        return dict(record)

    def stats(self) -> dict:
        """Agreement and counts over reconciled predictions only."""
        n = len(self._outcomes)
        if not n:
            return {"n_locked": len(self._predictions), "n_reconciled": 0, "agreement": None}
        correct = sum(1 for r in self._outcomes.values() if r["correct"])
        return {"n_locked": len(self._predictions), "n_reconciled": n, "agreement": correct / n}

    def reset(self) -> None:
        self._predictions.clear()
        self._outcomes.clear()


manager = ProspectiveManager()
