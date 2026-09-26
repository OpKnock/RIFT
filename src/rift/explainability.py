"""Explainability + Trust: audit trail, evidence packages, provenance (Phase 8).

Provides:
- Decision reasoning records with full traceability
- Assumption explorer
- Provenance explorer
- Model/version explorer
- Evidence explorer
- Execution fingerprint viewer
- Guardian verification view
- Complete decision audit trail
- Immutable/append-only audit records
- Cryptographic evidence hashes
- Signed evidence packages
- Reproducible evidence from stored runs
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    """Immutable append-only audit record."""
    record_id: str
    timestamp: str
    record_type: str  # "decision", "prediction", "guardian", "model_change", "incident"
    actor: str
    payload: dict
    previous_hash: str | None
    hash: str

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "record_type": self.record_type,
            "actor": self.actor,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


@dataclass(frozen=True)
class EvidencePackage:
    """Signed evidence package for a decision/prediction."""
    package_id: str
    created_at: str
    created_by: str
    decision_id: str | None
    prediction_id: str | None
    contents: dict  # All evidence: inputs, model, guardian, reasoning
    signature: str | None = None  # Would be filled by external signing service
    public_key_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "decision_id": self.decision_id,
            "prediction_id": self.prediction_id,
            "contents": self.contents,
            "signature": self.signature,
            "public_key_id": self.public_key_id,
        }


class AuditLog:
    """Immutable append-only audit log with hash chaining."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[AuditRecord] = []
        self._last_hash: str | None = None

    def _compute_hash(self, record: AuditRecord) -> str:
        content = _json.dumps({
            "record_id": record.record_id,
            "timestamp": record.timestamp,
            "record_type": record.record_type,
            "actor": record.actor,
            "payload": record.payload,
            "previous_hash": record.previous_hash,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return _hashlib.sha256(content).hexdigest()

    def append(
        self,
        record_type: str,
        actor: str,
        payload: dict,
    ) -> AuditRecord:
        with self._lock:
            record_id = f"audit-{int(time.time() * 1000000)}"
            timestamp = datetime.now(timezone.utc).isoformat()
            record = AuditRecord(
                record_id=record_id,
                timestamp=timestamp,
                record_type=record_type,
                actor=actor,
                payload=payload,
                previous_hash=self._last_hash,
                hash="",  # placeholder
            )
            record_hash = self._compute_hash(record)
            # Create new record with computed hash (immutable)
            final_record = AuditRecord(
                record_id=record.record_id,
                timestamp=record.timestamp,
                record_type=record.record_type,
                actor=record.actor,
                payload=record.payload,
                previous_hash=record.previous_hash,
                hash=record_hash,
            )
            self._records.append(final_record)
            self._last_hash = record_hash
            return final_record

    def get(self, record_id: str) -> AuditRecord | None:
        with self._lock:
            for r in self._records:
                if r.record_id == record_id:
                    return r
            return None

    def query(
        self,
        record_type: str | None = None,
        actor: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        with self._lock:
            results = list(self._records)
            if record_type:
                results = [r for r in results if r.record_type == record_type]
            if actor:
                results = [r for r in results if r.actor == actor]
            if since:
                results = [r for r in results if r.timestamp >= since]
            if until:
                results = [r for r in results if r.timestamp <= until]
            results.sort(key=lambda r: r.timestamp, reverse=True)
            return results[:limit]

    def verify_chain(self) -> dict:
        """Verify the hash chain integrity."""
        with self._lock:
            if not self._records:
                return {"valid": True, "records": 0, "errors": []}
            errors = []
            for i, record in enumerate(self._records):
                expected = self._compute_hash(record)
                if record.hash != expected:
                    errors.append(f"Record {record.record_id} hash mismatch")
                if i > 0 and record.previous_hash != self._records[i-1].hash:
                    errors.append(f"Record {record.record_id} chain broken")
            return {
                "valid": len(errors) == 0,
                "records": len(self._records),
                "errors": errors,
            }

    def stats(self) -> dict:
        with self._lock:
            by_type = {}
            for r in self._records:
                by_type[r.record_type] = by_type.get(r.record_type, 0) + 1
            return {
                "total": len(self._records),
                "by_type": by_type,
                "chain_valid": self.verify_chain()["valid"],
            }


class EvidenceStore:
    """Store for evidence packages."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._packages: dict[str, EvidencePackage] = {}

    def create(
        self,
        created_by: str,
        contents: dict,
        decision_id: str | None = None,
        prediction_id: str | None = None,
    ) -> EvidencePackage:
        with self._lock:
            package_id = f"ev-{int(time.time() * 1000000)}"
            package = EvidencePackage(
                package_id=package_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by=created_by,
                decision_id=decision_id,
                prediction_id=prediction_id,
                contents=contents,
            )
            self._packages[package_id] = package
            return package

    def get(self, package_id: str) -> EvidencePackage | None:
        with self._lock:
            return self._packages.get(package_id)

    def by_decision(self, decision_id: str) -> list[EvidencePackage]:
        with self._lock:
            return [p for p in self._packages.values() if p.decision_id == decision_id]

    def by_prediction(self, prediction_id: str) -> list[EvidencePackage]:
        with self._lock:
            return [p for p in self._packages.values() if p.prediction_id == prediction_id]


class Explainer:
    """Build structured explanations from computation artifacts."""

    @staticmethod
    def build_decision_reasoning(
        decision: dict,
        guardian_verdict: dict,
        counterfactuals: dict,
        trajectories: list[dict],
        policy_assumptions: dict,
    ) -> dict:
        """Build a complete reasoning record for a decision."""
        robust_ranking = counterfactuals.get("robust_ranking", [])
        top_policy = robust_ranking[0] if robust_ranking else None
        
        return {
            "selected_policy": top_policy["policy"] if top_policy else None,
            "selection_reason": (
                f"Policy minimizes worst-case risk ({top_policy['worst_case_risk']:.3f}) "
                f"while feasible under all perturbations"
                if top_policy and top_policy.get("feasible_under_all")
                else "No policy feasible under all perturbations; top-ranked shown as rejected"
            ),
            "rejected_policies": [
                {
                    "policy": r["policy"],
                    "reason": (
                        f"Infeasible under perturbation (worst-case {r['worst_case_risk']:.3f})"
                        if not r.get("feasible_under_all")
                        else f"Higher worst-case risk ({r['worst_case_risk']:.3f})"
                    ),
                }
                for r in robust_ranking[1:]
            ],
            "guardian_verdict": {
                "action": guardian_verdict.get("action"),
                "rejections": guardian_verdict.get("rejections", []),
                "flags": guardian_verdict.get("flags", []),
                "stages": guardian_verdict.get("stages", {}),
            },
            "assumptions": top_policy.get("assumptions", {}) if top_policy else {},
            "trajectory_summary": [
                {"policy": t["policy"], "final_risk": t["path"][-1]["risk"] if t["path"] else None}
                for t in trajectories
            ],
            "sensitivity": Explainer._extract_sensitivity(counterfactuals),
        }

    @staticmethod
    def _extract_sensitivity(counterfactuals: dict) -> dict:
        ranking = counterfactuals.get("robust_ranking", [])
        if len(ranking) < 2:
            return {}
        top = ranking[0]
        second = ranking[1]
        return {
            "worst_case_gap": second["worst_case_risk"] - top["worst_case_risk"],
            "nominal_gap": second["nominal_risk"] - top["nominal_risk"],
            "top_feasible": top.get("feasible_under_all", True),
            "second_feasible": second.get("feasible_under_all", True),
        }

    @staticmethod
    def build_assumption_explorer(
        counterfactuals: dict,
        model_context: dict | None,
        deployment: dict | None,
    ) -> dict:
        """Build structured assumption explorer data."""
        ranking = counterfactuals.get("robust_ranking", [])
        return {
            "policies": [
                {
                    "policy": r["policy"],
                    "assumptions": r.get("assumptions", {}),
                    "feasible_under_all": r.get("feasible_under_all", True),
                }
                for r in ranking
            ],
            "model": model_context or {},
            "deployment": deployment or {},
            "imputed_fields": counterfactuals.get("imputed_fields", []),
        }

    @staticmethod
    def build_provenance_explorer(
        prediction_provenance: dict,
        source_ids: list[str],
    ) -> dict:
        """Build provenance explorer data."""
        return {
            "prediction_id": prediction_provenance.get("prediction_id"),
            "model_id": prediction_provenance.get("model_id"),
            "weights_digest": prediction_provenance.get("weights_digest"),
            "schema_version": prediction_provenance.get("schema_version"),
            "calibration_id": prediction_provenance.get("calibration_id"),
            "source_ids": source_ids,
            "input_hash": prediction_provenance.get("input_hash"),
            "ehr_hash": prediction_provenance.get("ehr_hash"),
            "baseline_hash": prediction_provenance.get("baseline_hash"),
            "engine": prediction_provenance.get("engine"),
        }

    @staticmethod
    def build_model_explorer(
        model_registry_entry: dict | None,
        weights_digest: str | None,
    ) -> dict:
        """Build model/version explorer data."""
        return {
            "model_id": model_registry_entry.get("model_id") if model_registry_entry else None,
            "status": model_registry_entry.get("status") if model_registry_entry else None,
            "weights_digest": weights_digest,
            "trained_at": model_registry_entry.get("trained_at") if model_registry_entry else None,
            "training_data_hash": model_registry_entry.get("training_data_hash") if model_registry_entry else None,
            "hyperparameters": model_registry_entry.get("hyperparameters") if model_registry_entry else None,
            "validation_metrics": model_registry_entry.get("validation_metrics") if model_registry_entry else None,
        }

    @staticmethod
    def build_evidence_explorer(
        evidence_bundle: dict,
        guardian_verdict: dict,
    ) -> dict:
        """Build evidence explorer data."""
        return {
            "risk_record": evidence_bundle.get("risk", {}),
            "robustness": evidence_bundle.get("robustness", {}),
            "guardian": {
                "action": guardian_verdict.get("action"),
                "findings": guardian_verdict.get("findings", []),
                "stages": guardian_verdict.get("stages", {}),
            },
            "counterfactuals": evidence_bundle.get("futures", {}),
            "trajectories": evidence_bundle.get("trajectories", []),
            "reasons": evidence_bundle.get("reasons", []),
            "decision_table": evidence_bundle.get("decision_table", {}),
            "provenance": evidence_bundle.get("provenance", {}),
        }

    @staticmethod
    def build_fingerprint_viewer(
        prediction_provenance: dict,
        execution_context: dict,
    ) -> dict:
        """Build execution fingerprint viewer data."""
        return {
            "prediction_id": prediction_provenance.get("prediction_id"),
            "input_hash": prediction_provenance.get("input_hash"),
            "model_id": prediction_provenance.get("model_id"),
            "weights_digest": prediction_provenance.get("weights_digest"),
            "schema_version": prediction_provenance.get("schema_version"),
            "calibration_id": prediction_provenance.get("calibration_id"),
            "engine_version": execution_context.get("engine_version"),
            "timestamp": execution_context.get("timestamp"),
            "random_seed": execution_context.get("random_seed"),
            "git_commit": execution_context.get("git_commit"),
        }

    @staticmethod
    def build_guardian_verification_view(guardian_verdict: dict) -> dict:
        """Build Guardian verification view."""
        return {
            "overall_action": guardian_verdict.get("action"),
            "display_allowed": guardian_verdict.get("display_allowed"),
            "rejections": guardian_verdict.get("rejections", []),
            "flags": guardian_verdict.get("flags", []),
            "stages": {
                stage: {
                    "passed": info.get("passed"),
                    "rules": info.get("rules", []),
                }
                for stage, info in guardian_verdict.get("stages", {}).items()
            },
            "findings": guardian_verdict.get("findings", []),
            "scope": guardian_verdict.get("scope"),
        }

    @staticmethod
    def distinguish_computation_type(record_type: str) -> str:
        """Clearly label the type of computation."""
        mapping = {
            "prediction": "PREDICTION — model output on observed state",
            "simulation": "SIMULATION — forward rollout under assumed policy",
            "optimization": "OPTIMIZATION — policy search under constraints",
            "observation": "OBSERVATION — raw sensor/clinical data",
            "counterfactual": "COUNTERFACTUAL — what-if under declared assumptions",
        }
        return mapping.get(record_type, f"UNKNOWN ({record_type})")

    @staticmethod
    def mark_llm_generated(content: str) -> dict:
        """Wrap LLM-generated content with clear labeling."""
        return {
            "content": content,
            "source": "llm-generated",
            "disclaimer": "This explanation was generated by an LLM grounded in the deterministic computation artifacts above. It may contain errors. Verify against the evidence explorer.",
        }


audit_log = AuditLog()
evidence_store = EvidenceStore()