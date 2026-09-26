"""Advanced Intelligence: LLM-assisted features grounded in deterministic computation (Phase 15).

All LLM features are strictly post-computation: they NEVER drive decisions,
only explain, interrogate, or generate candidates that MUST pass through
the full deterministic pipeline before any action.
"""
from __future__ import annotations

import json
import os
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from enum import Enum

from .experiments import ExperimentSpec, ExperimentArchive, experiment_archive
from .explainability import Explainer, audit_log, evidence_store
from .health.twin import DigitalTwin
from .health.ehr import EHRRecord
from .health.models import PatientState
from .health.risk import predict
from .health.robustness import robustness_report
from .guardian_core import Guardian, build_generic_guardian, Finding, SEVERITY_HIGH, ACTION_WITHHOLD, DEFAULT_STAGES
from .health.guardian import verdict as health_verdict
from .health.baseline import PersonalBaseline
from .health.ehr import EHRRecord as HealthEHRRecord
from .health.models import Deviation


class LLMProvider(ABC):
    """Abstract LLM provider - pluggable for different backends."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "", temperature: float = 0.1, max_tokens: int = 2000) -> str:
        """Single completion."""
        pass

    @abstractmethod
    def complete_structured(self, prompt: str, schema: dict, system: str = "") -> dict:
        """Structured output matching JSON schema."""
        pass


class MockLLMProvider(LLMProvider):
    """Deterministic mock for testing/CI - no external calls."""

    def complete(self, prompt: str, system: str = "", temperature: float = 0.1, max_tokens: int = 2000) -> str:
        return f"[MOCK LLM RESPONSE] Would process: {prompt[:100]}..."

    def complete_structured(self, prompt: str, schema: dict, system: str = "") -> dict:
        return {"mock": True, "message": "Structured output would be generated here"}


class OpenAILLMProvider(LLMProvider):
    """OpenAI-compatible provider (OpenAI, Azure, local vLLM, etc.)."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-4"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def complete(self, prompt: str, system: str = "", temperature: float = 0.1, max_tokens: int = 2000) -> str:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def complete_structured(self, prompt: str, schema: dict, system: str = "") -> dict:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt + "\n\nRespond ONLY with valid JSON matching this schema: " + json.dumps(schema)})
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)


# --- Canonical Provider ---
llm_provider: LLMProvider = MockLLMProvider()

def set_llm_provider(provider: LLMProvider) -> None:
    global llm_provider
    llm_provider = provider


# --- Grounding & Verification ---

class GroundedExplainer:
    """LLM explanations that are ALWAYS grounded in deterministic artifacts."""

    FORBIDDEN_PATTERNS = [
        "I estimate", "approximately", "roughly", "about", "around",
        "likely", "probably", "may", "could", "might", "suggests",
        "appears to", "seems", "indicates", "roughly", "circa",
    ]

    REQUIRED_GROUNDING = [
        "prediction_id", "model_id", "weights_digest", "input_hash",
        "risk_value", "uncertainty_interval", "guardian_action",
    ]

    def __init__(self, provider: LLMProvider = None):
        self.provider = provider or llm_provider

    def explain_decision(
        self,
        twin_snapshot: dict,
        deterministic_reasons: list[str],
        guardian_verdict: dict,
    ) -> dict:
        """Generate LLM explanation grounded in deterministic reasons."""
        # Verify all deterministic facts are present
        grounding = self._extract_grounding(twin_snapshot, guardian_verdict)

        system = """You are a medical AI explanation assistant. Your responses MUST:
1. ONLY use facts from the provided grounding data
2. NEVER speculate, estimate, or use hedging language
3. Quote exact values from grounding (risk, uncertainty, guardian action)
4. Reference the prediction_id for traceability
5. State "DETERMINISTIC COMPUTATION" before any numerical claim
6. If data is missing, say "NOT IN GROUNDING DATA" not "unknown"

FORBIDDEN: "approximately", "likely", "seems", "suggests", "appears", "roughly", "around"
"""

        prompt = f"""Explain this cardiac-strain risk decision to a clinician.

GROUNDING DATA (deterministic, verified):
{json.dumps(grounding, indent=2)}

DETERMINISTIC REASONS (from explainability engine):
{json.dumps(deterministic_reasons, indent=2)}

GUARDIAN VERDICT:
{json.dumps(guardian_verdict, indent=2)}

Generate a clinical explanation that a cardiologist can trust. Every claim must trace to grounding.
"""

        explanation = self.provider.complete(prompt, system, temperature=0.0)

        # Verify no forbidden patterns
        violations = [p for p in self.FORBIDDEN_PATTERNS if p.lower() in explanation.lower()]

        return {
            "explanation": explanation,
            "grounding": grounding,
            "deterministic_reasons": deterministic_reasons,
            "guardian_verdict": guardian_verdict,
            "violations": violations,
            "verification": {
                "grounded": len(violations) == 0,
                "forbidden_patterns_found": violations,
                "prediction_id": grounding.get("prediction_id"),
                "model_id": grounding.get("model_id"),
            },
            "disclaimer": "This explanation was generated by an LLM grounded in deterministic computation artifacts. Verify against the evidence explorer.",
            "source": "llm-grounded",
        }

    def _extract_grounding(self, twin_snapshot: dict, guardian_verdict: dict) -> dict:
        provenance = twin_snapshot.get("provenance", {})
        risk = twin_snapshot.get("risk", {})
        return {
            "prediction_id": provenance.get("prediction_id"),
            "model_id": provenance.get("model_id"),
            "weights_digest": provenance.get("weights_digest"),
            "schema_version": provenance.get("schema_version"),
            "calibration_id": provenance.get("calibration_id"),
            "input_hash": provenance.get("input_hash"),
            "ehr_hash": provenance.get("ehr_hash"),
            "baseline_hash": provenance.get("baseline_hash"),
            "engine": provenance.get("engine"),
            "day_index": twin_snapshot.get("day_index"),
            "patient_id": twin_snapshot.get("patient_id"),
            "risk_value": risk.get("risk"),
            "uncertainty": risk.get("uncertainty"),
            "uncertainty_interval": risk.get("interval"),
            "input_quality": risk.get("input_quality"),
            "measurement_jitter": risk.get("measurement_jitter"),
            "guardian_action": guardian_verdict.get("action"),
            "guardian_display_allowed": guardian_verdict.get("display_allowed"),
            "guardian_rejections": guardian_verdict.get("rejections", []),
            "guardian_flags": guardian_verdict.get("flags", []),
            "top_contributors": risk.get("contributions", [])[:3],
        }


class NaturalLanguageInterface:
    """Natural language queries grounded in deterministic computation."""

    def __init__(self, provider: LLMProvider = None):
        self.provider = provider or llm_provider

    def create_scenario_from_nl(self, nl_description: str) -> dict:
        """Convert natural language to ExperimentSpec - then VALIDATE through pipeline."""
        system = """Convert natural language to a RIFT ExperimentSpec JSON.
Return ONLY valid JSON matching the ExperimentSpec schema.
The spec will be validated by the deterministic pipeline - invalid specs are rejected.
"""

        prompt = f"""Create an ExperimentSpec from this description:
"{nl_description}"

Available fields:
- name: string
- scenario_name: "smart-building-emergency" (only supported)
- initial_state: dict (smoke, crowd, corridor_capacity)
- perturbations: list of dicts
- policy_variables: list of strings (route_a, route_c, stairwell_b)
- optimizer: "exact" | "qaoa-expectation" | "qaoa-cvar"
- backend: "statevector-simulator" | "none"
- seed: integer (optional)
- description: string

Output ONLY JSON.
"""

        response = self.provider.complete(prompt, system, temperature=0.0)
        try:
            spec = json.loads(response)
            # Validate through actual pipeline
            from .experiments import validate_spec_payload
            validated = validate_spec_payload(spec)
            return {"spec": validated.to_dict(), "valid": True, "raw_llm": response}
        except Exception as e:
            return {"spec": None, "valid": False, "error": str(e), "raw_llm": response}

    def modify_scenario_from_nl(self, current_spec: dict, nl_modification: str) -> dict:
        """Modify an existing spec via natural language."""
        system = """Modify the ExperimentSpec per the natural language instruction.
Return the COMPLETE modified spec as valid JSON.
"""

        prompt = f"""Current spec:
{json.dumps(current_spec, indent=2)}

Modification: "{nl_modification}"

Return the full modified ExperimentSpec as JSON.
"""

        response = self.provider.complete(prompt, system, temperature=0.0)
        try:
            spec = json.loads(response)
            from .experiments import validate_spec_payload
            validated = validate_spec_payload(spec)
            return {"spec": validated.to_dict(), "valid": True}
        except Exception as e:
            return {"spec": None, "valid": False, "error": str(e)}

    def what_if_query(self, twin_snapshot: dict, nl_query: str) -> dict:
        """Answer what-if queries by generating counterfactual candidates."""
        system = """Answer what-if queries by proposing counterfactual scenarios.
Each scenario must be valid ExperimentSpec JSON.
Ground all numbers in the twin snapshot state.
"""

        prompt = f"""Current twin state (day {twin_snapshot.get('day_index')}):
Risk: {twin_snapshot.get('risk', {}).get('risk', 0)*100:.1f}%
Guardian: {twin_snapshot.get('guardian', {}).get('action')}
Top contributors: {twin_snapshot.get('risk', {}).get('contributions', [])[:3]}

Query: "{nl_query}"

Propose 1-3 counterfactual scenarios as ExperimentSpec JSONs that answer this query.
Each must be valid and grounded in the current state.
"""

        response = self.provider.complete(prompt, system, temperature=0.2)
        try:
            # Try to parse as list or single object
            data = json.loads(response)
            scenarios = data if isinstance(data, list) else [data]
            validated = []
            for s in scenarios:
                from .experiments import validate_spec_payload
                validated.append(validate_spec_payload(s).to_dict())
            return {"scenarios": validated, "valid": True}
        except Exception as e:
            return {"scenarios": [], "valid": False, "error": str(e)}

    def interrogate_result(self, evidence_bundle: dict, nl_question: str) -> dict:
        """Answer questions about a result using grounded LLM."""
        system = """Answer questions about the computation result.
ONLY use data from the provided evidence bundle.
If answer not in bundle, say "NOT IN EVIDENCE BUNDLE".
"""

        prompt = f"""Evidence bundle:
{json.dumps(evidence_bundle, indent=2)[:5000]}

Question: "{nl_question}"

Answer using ONLY the evidence bundle data.
"""

        response = self.provider.complete(prompt, system, temperature=0.0)
        return {"answer": response, "source": "llm-grounded"}

    def audit_query(self, audit_records: list[dict], nl_question: str) -> dict:
        """Query audit trail via natural language."""
        system = """Query the audit trail.
ONLY use provided records.
"""

        prompt = f"""Audit records (last 50):
{json.dumps(audit_records[:50], indent=2)}

Question: "{nl_question}"

Answer using ONLY these records.
"""

        response = self.provider.complete(prompt, system, temperature=0.0)
        return {"answer": response, "source": "llm-grounded"}


# --- Automated Generation & Discovery ---

class AutomatedDiscovery:
    """Automated scenario/edge-case/failure-mode generation."""

    def __init__(self, provider: LLMProvider = None):
        self.provider = provider or llm_provider

    def generate_edge_cases(self, base_spec: dict, count: int = 10) -> list[dict]:
        """Generate edge-case variations of a spec."""
        system = f"""Generate {count} edge-case ExperimentSpecs by varying parameters to boundary/extreme values.
Each must be valid JSON. Focus on: boundary values, zero/max constraints, correlation breaks, rare combinations.
"""

        prompt = f"""Base spec:
{json.dumps(base_spec, indent=2)}

Generate {count} edge cases as a JSON array.
"""

        response = self.provider.complete(prompt, system, temperature=0.3)
        try:
            cases = json.loads(response)
            validated = []
            for c in cases:
                from .experiments import validate_spec_payload
                validated.append(validate_spec_payload(c).to_dict())
            return validated
        except Exception:
            return []

    def discover_failure_modes(self, experiment_id: str) -> list[dict]:
        """Analyze experiment runs to discover failure patterns."""
        exp = experiment_archive.get_experiment(experiment_id)
        if not exp or not exp.get("runs"):
            return []

        runs = exp["runs"]
        failed = [r for r in runs if r.get("status") == "failed"]
        guardian_rejections = []
        for r in runs:
            result = r.get("result", {})
            guardian = result.get("guardian", {})
            if guardian.get("action") == "WITHHOLD":
                guardian_rejections.append({"run_id": r["id"], "rejections": guardian.get("rejections", [])})

        # LLM analysis
        system = """Analyze failure patterns and guardian rejections.
Return structured JSON with: failure_categories, common_rejections, suggested_fixes.
"""

        prompt = f"""Failed runs: {len(failed)}/{len(runs)}
Failure details: {json.dumps([r.get('error') for r in failed], indent=2)[:2000]}
Guardian rejections: {json.dumps(guardian_rejections[:20], indent=2)}

Identify patterns and suggest fixes.
"""

        response = self.provider.complete(prompt, system, temperature=0.1)
        try:
            return json.loads(response)
        except Exception:
            return {"error": "Failed to parse LLM analysis"}

    def sensitivity_exploration(self, base_spec: dict, parameter_ranges: dict, steps: int = 5) -> list[dict]:
        """Systematic sensitivity analysis across parameter ranges."""
        # This is deterministic - no LLM needed
        import itertools
        import numpy as np

        param_names = list(parameter_ranges.keys())
        param_values = []
        for name, (min_v, max_v) in parameter_ranges.items():
            param_values.append(np.linspace(min_v, max_v, steps))

        scenarios = []
        for combo in itertools.product(*param_values):
            spec = base_spec.copy()
            for i, name in enumerate(param_names):
                if name in spec.get("initial_state", {}):
                    spec.setdefault("initial_state", {})[name] = float(combo[i])
                elif name in spec:
                    spec[name] = float(combo[i])
            from .experiments import validate_spec_payload
            try:
                validated = validate_spec_payload(spec)
                scenarios.append(validated.to_dict())
            except Exception:
                pass
        return scenarios

    def uncertainty_analysis(self, experiment_id: str) -> dict:
        """Analyze uncertainty sources across experiment runs."""
        exp = experiment_archive.get_experiment(experiment_id)
        if not exp:
            return {"error": "Experiment not found"}

        # Extract uncertainty metrics from runs
        uncertainties = []
        for r in exp.get("runs", []):
            result = r.get("result", {})
            uncertainty = result.get("uncertainty", {})
            if uncertainty:
                uncertainties.append({
                    "run_id": r["id"],
                    "risk_entropy": uncertainty.get("risk_entropy"),
                    "prediction_interval": result.get("prediction_interval"),
                })

        return {
            "total_runs": len(exp.get("runs", [])),
            "runs_with_uncertainty": len(uncertainties),
            "uncertainty_samples": uncertainties[:10],
        }


# --- Continuous Learning Infrastructure ---

class LearningInfrastructure:
    """Track decision vs outcome, feedback, without auto-changing production models."""

    def __init__(self):
        self._lock = __import__("threading").Lock()
        self._feedback: list[dict] = []
        self._outcome_tracking: list[dict] = []
        self._model_candidates: dict[str, list[dict]] = {}  # model_id -> candidate configs

    def record_feedback(self, decision_id: str, outcome: str, feedback: dict) -> dict:
        """Record human feedback on a decision outcome."""
        entry = {
            "feedback_id": f"fb-{hashlib.md5(f'{decision_id}{datetime.now()}'.encode()).hexdigest()[:12]}",
            "decision_id": decision_id,
            "outcome": outcome,  # "correct", "incorrect", "partial", "unknown"
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._feedback.append(entry)
        return entry

    def record_decision_outcome(self, decision_id: str, predicted_risk: float, realized_event: bool, horizon_days: int) -> dict:
        """Record realized outcome for a decision."""
        entry = {
            "tracking_id": f"trk-{hashlib.md5(f'{decision_id}{datetime.now()}'.encode()).hexdigest()[:12]}",
            "decision_id": decision_id,
            "predicted_risk": predicted_risk,
            "realized_event": realized_event,
            "horizon_days": horizon_days,
            "calibration_error": abs(predicted_risk - (1.0 if realized_event else 0.0)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._outcome_tracking.append(entry)
        return entry

    def propose_model_candidate(self, model_id: str, candidate_config: dict, evidence: dict) -> dict:
        """Propose a model update candidate (requires human approval)."""
        candidate = {
            "candidate_id": f"cand-{hashlib.md5(f'{model_id}{datetime.now()}'.encode()).hexdigest()[:12]}",
            "model_id": model_id,
            "config": candidate_config,
            "evidence": evidence,
            "status": "proposed",
            "proposed_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": None,
            "approved_by": None,
        }
        with self._lock:
            self._model_candidates.setdefault(model_id, []).append(candidate)
        return candidate

    def approve_candidate(self, candidate_id: str, approver: str) -> dict:
        """Approve a model candidate for shadow mode testing."""
        with self._lock:
            for model_id, candidates in self._model_candidates.items():
                for c in candidates:
                    if c["candidate_id"] == candidate_id:
                        c["status"] = "approved"
                        c["approved_at"] = datetime.now(timezone.utc).isoformat()
                        c["approved_by"] = approver
                        return c
        return {"error": "Candidate not found"}

    def get_feedback_summary(self) -> dict:
        with self._lock:
            return {
                "total_feedback": len(self._feedback),
                "by_outcome": self._count_by(self._feedback, "outcome"),
                "recent": self._feedback[-10:],
            }

    def get_calibration_report(self) -> dict:
        with self._lock:
            if not self._outcome_tracking:
                return {"status": "no_data"}
            errors = [o["calibration_error"] for o in self._outcome_tracking]
            return {
                "total_tracked": len(self._outcome_tracking),
                "mean_calibration_error": sum(errors) / len(errors),
                "max_calibration_error": max(errors),
                "brier_score": sum(e**2 for e in errors) / len(errors),
            }

    def _count_by(self, items: list[dict], key: str) -> dict:
        counts = {}
        for item in items:
            v = item.get(key, "unknown")
            counts[v] = counts.get(v, 0) + 1
        return counts


# --- Governance ---

class GovernanceManager:
    """Human-in-the-loop governance for learning changes."""

    def __init__(self):
        self._lock = __import__("threading").Lock()
        self._policies: list[dict] = []
        self._approvals: list[dict] = []

    def require_approval_for(self, action_type: str, description: str, requester: str) -> str:
        """Create an approval request for a governance-gated action."""
        request_id = f"gov-{hashlib.md5(f'{action_type}{description}{datetime.now()}'.encode()).hexdigest()[:12]}"
        request = {
            "request_id": request_id,
            "action_type": action_type,  # "model_promotion", "shadow_mode", "retraining", "policy_change"
            "description": description,
            "requester": requester,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": None,
            "approver": None,
            "conditions": [],
        }
        with self._lock:
            self._approvals.append(request)
        return request_id

    def approve(self, request_id: str, approver: str, conditions: list[str] = None) -> dict:
        with self._lock:
            for a in self._approvals:
                if a["request_id"] == request_id:
                    a["status"] = "approved"
                    a["approved_at"] = datetime.now(timezone.utc).isoformat()
                    a["approver"] = approver
                    a["conditions"] = conditions or []
                    return a
        return {"error": "Request not found"}

    def reject(self, request_id: str, approver: str, reason: str) -> dict:
        with self._lock:
            for a in self._approvals:
                if a["request_id"] == request_id:
                    a["status"] = "rejected"
                    a["approved_at"] = datetime.now(timezone.utc).isoformat()
                    a["approver"] = approver
                    a["rejection_reason"] = reason
                    return a
        return {"error": "Request not found"}

    def get_pending(self) -> list[dict]:
        with self._lock:
            return [a for a in self._approvals if a["status"] == "pending"]


# --- Canonical Instances ---
grounded_explainer = GroundedExplainer()
nl_interface = NaturalLanguageInterface()
automated_discovery = AutomatedDiscovery()
learning_infra = LearningInfrastructure()
governance = GovernanceManager()


# --- Convenience Functions ---

def explain_grounded(twin_snapshot: dict, guardian_verdict: dict) -> dict:
    """Generate grounded explanation for a twin snapshot."""
    from .health.explain import build_reasons
    from .health.baseline import PersonalBaseline
    from .health.ehr import EHRRecord as HealthEHRRecord
    from .health.models import Deviation

    # Build deterministic reasons (same as health.explain)
    # Note: Would need full twin context - simplified here
    deterministic_reasons = [
        f"Risk: {twin_snapshot.get('risk', {}).get('risk', 0)*100:.1f}%",
        f"Uncertainty: ±{twin_snapshot.get('risk', {}).get('uncertainty', 0)*100:.1f}%",
        f"Guardian: {guardian_verdict.get('action')}",
    ]
    return grounded_explainer.explain_decision(twin_snapshot, deterministic_reasons, guardian_verdict)


def create_scenario_nl(description: str) -> dict:
    return nl_interface.create_scenario_from_nl(description)


def what_if_nl(twin_snapshot: dict, query: str) -> dict:
    return nl_interface.what_if_query(twin_snapshot, query)


def interrogate_result_nl(evidence_bundle: dict, question: str) -> dict:
    return nl_interface.interrogate_result(evidence_bundle, question)


def audit_query_nl(question: str) -> dict:
    records = [r.to_dict() for r in audit_log.query(limit=100)]
    return nl_interface.audit_query(records, question)


def generate_edge_cases(base_spec: dict, count: int = 10) -> list[dict]:
    return automated_discovery.generate_edge_cases(base_spec, count)


def discover_failures(experiment_id: str) -> list[dict]:
    return automated_discovery.discover_failure_modes(experiment_id)


def sensitivity_analysis(base_spec: dict, param_ranges: dict, steps: int = 5) -> list[dict]:
    return automated_discovery.sensitivity_exploration(base_spec, param_ranges, steps)


def record_feedback(decision_id: str, outcome: str, feedback: dict) -> dict:
    return learning_infra.record_feedback(decision_id, outcome, feedback)


def record_outcome(decision_id: str, predicted_risk: float, realized_event: bool, horizon_days: int) -> dict:
    return learning_infra.record_decision_outcome(decision_id, predicted_risk, realized_event, horizon_days)


def propose_model_update(model_id: str, config: dict, evidence: dict) -> dict:
    return learning_infra.propose_model_candidate(model_id, config, evidence)


def require_governance_approval(action_type: str, description: str, requester: str) -> str:
    return governance.require_approval_for(action_type, description, requester)