"""Guardian Core: domain-agnostic staged verification framework (Phase 9).

This module provides the generic Guardian infrastructure that can be
instantiated for any domain. The healthcare-specific rules live in
`health.guardian`; other domains create their own rule sets.

Architecture:
- Stage gates: INPUT → STATE → MODEL → COUNTERFACTUAL → OPTIMIZATION → OUTPUT → DEPLOYMENT
- Each stage has rules with severity (HIGH/MEDIUM/LOW) and action (WITHHOLD/WARN)
- Rules carry metadata: owner, version, evidence
- Verdict combines all stages: display_allowed = no WITHHOLD findings
- Machine-readable failure reasons for every rule
"""
from __future__ import annotations

import json as _json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


# Severity and action constants
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

ACTION_WITHHOLD = "WITHHOLD"
ACTION_WARN = "WARN"
ACTION_ALLOW = "ALLOW"

# Standard stages - domain-agnostic
DEFAULT_STAGES = (
    "INPUT",
    "STATE",
    "MODEL",
    "COUNTERFACTUAL",
    "OPTIMIZATION",
    "OUTPUT",
    "DEPLOYMENT",
)


@dataclass(frozen=True)
class RuleMetadata:
    """Registry entry for a Guardian rule."""
    rule_id: str
    stage: str
    severity: str  # HIGH | MEDIUM | LOW
    action: str    # WITHHOLD | WARN
    summary: str
    owner: str
    version: str
    evidence: str
    domain: str = "generic"

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "stage": self.stage,
            "severity": self.severity,
            "action": self.action,
            "summary": self.summary,
            "owner": self.owner,
            "version": self.version,
            "evidence": self.evidence,
            "domain": self.domain,
        }


@dataclass(frozen=True)
class Finding:
    """A single Guardian finding (violation or warning)."""
    rule_id: str
    stage: str
    severity: str
    action: str
    message: str
    evidence: dict
    domain: str = "generic"

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "stage": self.stage,
            "severity": self.severity,
            "action": self.action,
            "message": self.message,
            "evidence": self.evidence,
            "domain": self.domain,
        }


class Rule(ABC):
    """Abstract base for a Guardian rule."""

    def __init__(self, metadata: RuleMetadata):
        self.metadata = metadata

    @abstractmethod
    def check(self, context: dict) -> list[Finding]:
        """Evaluate the rule against the provided context.
        
        Args:
            context: Domain-specific context dictionary containing all
                     data needed for this rule's evaluation.
                     
        Returns:
            List of Finding objects (empty if rule passes).
        """
        pass

    def create_finding(
        self,
        message: str,
        evidence: dict,
        override_severity: str | None = None,
        override_action: str | None = None,
    ) -> Finding:
        """Create a finding with this rule's metadata."""
        return Finding(
            rule_id=self.metadata.rule_id,
            stage=self.metadata.stage,
            severity=override_severity or self.metadata.severity,
            action=override_action or self.metadata.action,
            message=message,
            evidence=evidence,
            domain=self.metadata.domain,
        )


class StageGate:
    """A single verification stage containing multiple rules."""

    def __init__(self, name: str, rules: list[Rule]):
        self.name = name
        self.rules = rules

    def evaluate(self, context: dict) -> dict:
        """Run all rules in this stage."""
        findings: list[Finding] = []
        for rule in self.rules:
            findings.extend(rule.check(context))
        
        withheld = any(f.action == ACTION_WITHHOLD for f in findings)
        return {
            "stage": self.name,
            "passed": not withheld,
            "rules": [f.rule_id for f in findings],
            "findings": [f.to_dict() for f in findings],
        }


class Guardian:
    """Domain-agnostic Guardian orchestrator."""

    def __init__(
        self,
        stages: list[StageGate],
        rule_registry: dict[str, RuleMetadata] | None = None,
    ):
        self.stages = stages
        self.rule_registry = rule_registry or {}

    def register_rule(self, metadata: RuleMetadata) -> None:
        """Register a rule in the global registry (fail-closed on duplicate)."""
        if metadata.rule_id in self.rule_registry:
            raise ValueError(f"Rule {metadata.rule_id} already registered")
        self.rule_registry[metadata.rule_id] = metadata

    def get_rule_metadata(self, rule_id: str) -> RuleMetadata:
        """Retrieve rule metadata (fail-closed on unknown)."""
        if rule_id not in self.rule_registry:
            raise KeyError(f"Unknown rule: {rule_id}")
        return self.rule_registry[rule_id]

    def evaluate(self, context: dict) -> dict:
        """Run all stage gates against the context."""
        all_findings: list[Finding] = []
        stage_results: dict[str, dict] = {}

        for gate in self.stages:
            result = gate.evaluate(context)
            stage_results[gate.name] = result
            for f_dict in result["findings"]:
                all_findings.append(Finding(**f_dict))

        # Determine overall action
        if any(f.action == ACTION_WITHHOLD for f in all_findings):
            action = ACTION_WITHHOLD
        elif all_findings:
            action = ACTION_WARN
        else:
            action = ACTION_ALLOW

        rejections = [f.message for f in all_findings if f.action == ACTION_WITHHOLD]
        flags = [f.message for f in all_findings if f.action == ACTION_WARN]

        return {
            "display_allowed": action != ACTION_WITHHOLD,
            "action": action,
            "rejections": rejections,
            "flags": flags,
            "findings": [f.to_dict() for f in all_findings],
            "stages": stage_results,
            "scope": "domain-agnostic display-safety; not a domain authority",
        }


# --- Standard threshold rules (domain-agnostic) ---

class ThresholdRule(Rule):
    """Generic threshold rule: value must be within bounds."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        field: str,
        min_val: float | None,
        max_val: float | None,
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary=f"{field} within [{min_val}, {max_val}]",
            owner=owner,
            version=version,
            evidence=f"threshold check on {field}",
            domain=domain,
        )
        super().__init__(metadata)
        self.field = field
        self.min_val = min_val
        self.max_val = max_val

    def check(self, context: dict) -> list[Finding]:
        value = context.get(self.field)
        if value is None:
            return []
        violations = []
        if self.min_val is not None and value < self.min_val:
            violations.append(f"{self.field}={value} below minimum {self.min_val}")
        if self.max_val is not None and value > self.max_val:
            violations.append(f"{self.field}={value} above maximum {self.max_val}")
        if violations:
            return [self.create_finding(
                message="; ".join(violations),
                evidence={"field": self.field, "value": value,
                          "min": self.min_val, "max": self.max_val},
            )]
        return []


class RequiredFieldsRule(Rule):
    """Generic rule: required fields must be present and non-null."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        required_fields: list[str],
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary=f"required fields present: {', '.join(required_fields)}",
            owner=owner,
            version=version,
            evidence="required field presence check",
            domain=domain,
        )
        super().__init__(metadata)
        self.required_fields = required_fields

    def check(self, context: dict) -> list[Finding]:
        missing = [f for f in self.required_fields if context.get(f) is None]
        if missing:
            return [self.create_finding(
                message=f"missing required fields: {', '.join(missing)}",
                evidence={"missing": missing, "required": self.required_fields},
            )]
        return []


class SchemaDriftRule(Rule):
    """Generic rule: detect schema drift against expected fields."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        expected_fields: set[str],
        severity_missing: str = SEVERITY_HIGH,
        severity_extra: str = SEVERITY_LOW,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity_missing,
            action=ACTION_WITHHOLD,
            summary=f"schema conformance against {len(expected_fields)} expected fields",
            owner=owner,
            version=version,
            evidence="schema drift detection",
            domain=domain,
        )
        super().__init__(metadata)
        self.expected_fields = expected_fields
        self.severity_missing = severity_missing
        self.severity_extra = severity_extra

    def check(self, context: dict) -> list[Finding]:
        actual = set(context.keys()) if isinstance(context, dict) else set()
        missing = self.expected_fields - actual
        extra = actual - self.expected_fields
        findings = []
        if missing:
            findings.append(self.create_finding(
                message=f"schema drift: missing required fields={sorted(missing)}",
                evidence={"missing": sorted(missing), "unexpected": []},
                override_severity=self.severity_missing,
                override_action=ACTION_WITHHOLD,
            ))
        if extra:
            findings.append(self.create_finding(
                message=f"schema extension: new fields={sorted(extra)} (additive)",
                evidence={"missing": [], "unexpected": sorted(extra)},
                override_severity=self.severity_extra,
                override_action=ACTION_WARN,
            ))
        return findings


class StalenessRule(Rule):
    """Generic rule: data freshness check."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        staleness_field: str,
        threshold: int,
        severity: str = SEVERITY_MEDIUM,
        action: str = ACTION_WARN,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary=f"{staleness_field} <= {threshold}",
            owner=owner,
            version=version,
            evidence="staleness threshold check",
            domain=domain,
        )
        super().__init__(metadata)
        self.staleness_field = staleness_field
        self.threshold = threshold

    def check(self, context: dict) -> list[Finding]:
        value = context.get(self.staleness_field)
        if value is None:
            return []
        if value >= self.threshold:
            return [self.create_finding(
                message=f"{self.staleness_field} {value} exceeds threshold {self.threshold}: treat as stale",
                evidence={"field": self.staleness_field, "value": value, "threshold": self.threshold},
            )]
        return []


class OutputContractRule(Rule):
    """Generic rule: output must only contain allowed fields."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        allowed_fields: set[str],
        forbidden_substrings: list[str] | None = None,
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary=f"output contract: allowed fields only",
            owner=owner,
            version=version,
            evidence="output field validation",
            domain=domain,
        )
        super().__init__(metadata)
        self.allowed_fields = allowed_fields
        self.forbidden_substrings = forbidden_substrings or []

    def check(self, context: dict) -> list[Finding]:
        findings = []
        output = context.get("output", {})
        if not isinstance(output, dict):
            return []
        
        unexpected = set(output.keys()) - self.allowed_fields
        if unexpected:
            findings.append(self.create_finding(
                message=f"output carries unsupported fields: {sorted(unexpected)}",
                evidence={"fields": sorted(str(f) for f in unexpected)},
            ))
        
        # Check forbidden substrings (e.g., "prescription", "dosage")
        json_text = _json.dumps(output).lower()
        for sub in self.forbidden_substrings:
            if sub.lower() in json_text:
                findings.append(self.create_finding(
                    message=f"output must not contain '{sub}'",
                    evidence={"forbidden": sub},
                ))
        return findings


class CounterfactualLedgerRule(Rule):
    """Generic rule: every counterfactual must have a complete assumption ledger."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        required_ledger_keys: set[str],
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary="counterfactual assumption ledger complete",
            owner=owner,
            version=version,
            evidence="ledger completeness check",
            domain=domain,
        )
        super().__init__(metadata)
        self.required_ledger_keys = required_ledger_keys

    def check(self, context: dict) -> list[Finding]:
        findings = []
        counterfactuals = context.get("counterfactuals", {})
        ranking = counterfactuals.get("robust_ranking") or []
        for item in ranking:
            policy = item.get("policy")
            ledger = item.get("assumptions") or {}
            missing = sorted(self.required_ledger_keys - set(ledger))
            if missing:
                findings.append(self.create_finding(
                    message=f"policy {policy} lacks complete assumption ledger (missing: {', '.join(missing)})",
                    evidence={"policy": policy, "missing": missing},
                ))
        return findings


class RankingIntegrityRule(Rule):
    """Generic rule: robust ranking must honor engine ordering."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary="robust ranking integrity",
            owner=owner,
            version=version,
            evidence="ranking order validation",
            domain=domain,
        )
        super().__init__(metadata)

    def check(self, context: dict) -> list[Finding]:
        counterfactuals = context.get("counterfactuals", {})
        ranking = counterfactuals.get("robust_ranking") or []
        order = [(not r.get("feasible_under_all", True),
                  r.get("worst_case_risk", float("inf")),
                  r.get("nominal_risk", float("inf"))) for r in ranking]
        if order != sorted(order):
            return [self.create_finding(
                message="robust ranking violates engine ordering: output not independently verifiable",
                evidence={},
            )]
        top = ranking[0] if ranking else None
        if top is not None and not top.get("feasible_under_all", True):
            return [self.create_finding(
                message=f"top-ranked policy {top.get('policy')} infeasible under perturbation: shown as rejected",
                evidence={"policy": top.get("policy")},
                override_severity=SEVERITY_MEDIUM,
                override_action=ACTION_WARN,
            )]
        return []


class ModelIdentityRule(Rule):
    """Generic rule: model identity and weights digest must match registry."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        get_model_fn: Any,
        get_weights_digest_fn: Any,
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary="model identity / weights-digest match",
            owner=owner,
            version=version,
            evidence="model registry verification",
            domain=domain,
        )
        super().__init__(metadata)
        self.get_model_fn = get_model_fn
        self.get_weights_digest_fn = get_weights_digest_fn

    def check(self, context: dict) -> list[Finding]:
        model_context = context.get("model_context")
        if not model_context:
            return []
        model_id = model_context.get("model_id")
        if not model_id:
            return []
        try:
            entry = self.get_model_fn(model_id)
        except KeyError:
            return [self.create_finding(
                message=f"unregistered model_id {model_id!r}: prediction not traceable",
                evidence={"model_id": model_id},
            )]
        live = self.get_weights_digest_fn()
        pinned = entry.get("weights_digest")
        if pinned is None or pinned != live:
            return [self.create_finding(
                message="model weights do not match registry pin: possible tampering or unreviewed change",
                evidence={"model_id": model_id, "pinned": bool(pinned)},
            )]
        return []


class DeploymentGateRule(Rule):
    """Generic rule: deployment gate must not report open for unvalidated models."""

    def __init__(
        self,
        rule_id: str,
        stage: str,
        get_model_fn: Any,
        severity: str = SEVERITY_HIGH,
        action: str = ACTION_WITHHOLD,
        domain: str = "generic",
        owner: str = "UNASSIGNED",
        version: str = "1.0",
    ):
        metadata = RuleMetadata(
            rule_id=rule_id,
            stage=stage,
            severity=severity,
            action=action,
            summary="deployment inversion protection",
            owner=owner,
            version=version,
            evidence="deployment gate validation",
            domain=domain,
        )
        super().__init__(metadata)
        self.get_model_fn = get_model_fn

    def check(self, context: dict) -> list[Finding]:
        deployment = context.get("deployment")
        if not deployment:
            return []
        if deployment.get("clinical_use") == "open" or deployment.get("production") == "open":
            model_id = deployment.get("model_id", "")
            try:
                status = self.get_model_fn(model_id)["status"]
            except KeyError:
                status = "unknown"
            if status != "validated":
                return [self.create_finding(
                    message=f"deployment gate reports open for model without validated status ({status})",
                    evidence={"model_id": model_id, "status": status},
                )]
        return []


def build_generic_guardian(
    stages: tuple[str, ...] = DEFAULT_STAGES,
    domain: str = "generic",
    custom_rules: list[Rule] | None = None,
) -> Guardian:
    """Build a Guardian with standard generic rules plus custom ones."""
    stage_rules: dict[str, list[Rule]] = {s: [] for s in stages}
    
    if custom_rules:
        for rule in custom_rules:
            stage_rules.setdefault(rule.metadata.stage, []).append(rule)
    
    stage_gates = [StageGate(name, stage_rules[name]) for name in stages]
    registry = {}
    for gate in stage_gates:
        for rule in gate.rules:
            registry[rule.metadata.rule_id] = rule.metadata
    
    return Guardian(stage_gates, registry)


# --- Regression test helpers ---

def run_guardian_regression(guardian: Guardian, test_cases: list[dict]) -> dict:
    """Run a suite of regression test cases against a Guardian.
    
    Each test case: {"name": str, "context": dict, "expected_action": str,
                     "expected_rejections_contains": list[str] | None,
                     "expected_flags_contains": list[str] | None}
    """
    results = []
    for tc in test_cases:
        verdict = guardian.evaluate(tc["context"])
        passed = verdict["action"] == tc["expected_action"]
        rejection_ok = True
        if tc.get("expected_rejections_contains"):
            rejection_ok = all(any(exp in r for r in verdict["rejections"])
                              for exp in tc["expected_rejections_contains"])
        flag_ok = True
        if tc.get("expected_flags_contains"):
            flag_ok = all(any(exp in f for f in verdict["flags"])
                         for exp in tc["expected_flags_contains"])
        results.append({
            "name": tc["name"],
            "passed": passed and rejection_ok and flag_ok,
            "action": verdict["action"],
            "expected_action": tc["expected_action"],
            "rejections": verdict["rejections"],
            "flags": verdict["flags"],
        })
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "results": results,
    }