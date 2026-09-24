"""Healthcare Guardian 2.0: staged policy enforcement for display safety.

Guardian never diagnoses, never treats, never overrides a clinician. Every
check emits a structured Finding (rule_id, stage, severity, action,
message, evidence) through stage gates:

    INPUT → STATE → MODEL → COUNTERFACTUAL → OUTPUT → DEPLOYMENT

A WITHHOLD finding withholds the result (display_allowed=False); WARN
findings travel with it as explicit warnings. verdict() keeps its
historical shape (display_allowed/rejections/flags/scope) and adds
findings/stages/action, so existing consumers keep working.

Findings carry day_index from the checked state — never wall-clock time —
so verdicts stay fully deterministic.
"""
from __future__ import annotations

import json as _json
from dataclasses import dataclass

from .models import PHYSIOLOGICAL_BOUNDS, PatientState

MAX_PLAUSIBLE_DAILY_HR_SHIFT = 30.0  # bpm/day beyond which a transition is rejected
STALE_FLAG_DAYS = 3
UNCERTAINTY_FLAG = 0.35
ALLOWED_OUTPUT_KEYS = {
    "target", "horizon", "risk", "event_predicted", "threshold",
    "contributions", "input_quality", "measurement_jitter", "trend_terms",
    "uncertainty", "uncertainty_breakdown", "interval", "model", "calibration",
}

STAGES = ("INPUT", "STATE", "MODEL", "COUNTERFACTUAL", "OUTPUT", "DEPLOYMENT")

IMPOSSIBLE_MESSAGES = {
    "resting_hr": "resting HR outside plausible human range",
    "hrv_rmssd": "HRV outside plausible human range",
    "sleep_hours": "sleep hours outside 0-24 h",
    "activity_load": "activity load outside demo index range",
    "age": "age outside plausible human range",
}

# PatientState v1 feature schema: exact field set the twin, risk, and
# Guardian code was built against. Drift here breaks downstream
# assumptions, so it withholds rather than warns.
STATE_SCHEMA_FIELDS = frozenset({
    "day_index", "resting_hr", "hrv_rmssd", "sleep_hours", "activity_load",
    "data_quality", "stale_days", "provenance",
})

LEDGER_REQUIRED_KEYS = frozenset({
    "policy", "transition_model", "model_id", "weights_digest",
    "horizon_days", "perturbation_set", "causal_scope", "claim",
})

# Action semantics: WITHHOLD blocks display; WARN travels as a warning.
# Severity ranks triage priority and never overrides the action.
WITHHOLD = "WITHHOLD"
WARN = "WARN"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    stage: str
    severity: str  # HIGH | MEDIUM | LOW
    action: str    # WITHHOLD | WARN
    message: str
    evidence: dict

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "stage": self.stage,
            "severity": self.severity,
            "action": self.action,
            "message": self.message,
            "evidence": self.evidence,
        }


def check_state(state: PatientState, previous: PatientState | None = None,
                unestimated: tuple[str, ...] = ()) -> dict:
    """Display-safety verdict for one synchronized twin state."""
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []
    day = getattr(state, "day_index", None)

    def _add(finding: Finding):
        findings.append(finding)
        if finding.action == WITHHOLD:
            rejections.append(finding.message)
        else:
            flags.append(finding.message)

    for field, message in IMPOSSIBLE_MESSAGES.items():
        if field == "age":
            continue
        value = getattr(state, field, None)
        if value is None:
            continue
        lo, hi = PHYSIOLOGICAL_BOUNDS[field]
        if not (lo <= value <= hi):
            _add(Finding("G-001", "STATE", "HIGH", WITHHOLD,
                         f"{message}: {value}",
                         {"field": field, "value": value, "bounds": [lo, hi],
                          "day_index": day}))
    missing = [f for f in ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")
               if getattr(state, f) is None]
    if missing:
        _add(Finding("G-002", "INPUT", "MEDIUM", WARN,
                     f"missing wearable fields: {', '.join(missing)} (baseline-imputed downstream)",
                     {"fields": missing, "day_index": day}))
    if state.stale_days >= STALE_FLAG_DAYS:
        _add(Finding("G-003", "INPUT", "MEDIUM", WARN,
                     f"wearable data stale by {state.stale_days} days: treat trend as uncertain",
                     {"stale_days": state.stale_days, "day_index": day}))
    if not getattr(state, "provenance", ""):
        _add(Finding("G-004", "INPUT", "LOW", WARN,
                     "unrecorded observation origin: provenance missing, treat as unverified",
                     {"day_index": day}))
    if previous is not None and state.resting_hr is not None and previous.resting_hr is not None:
        shift = abs(state.resting_hr - previous.resting_hr)
        if shift > MAX_PLAUSIBLE_DAILY_HR_SHIFT:
            _add(Finding("G-005", "STATE", "HIGH", WITHHOLD,
                         f"resting HR shifted {shift:.1f} bpm in one day: implausible transition",
                         {"shift_bpm": shift, "day_index": day}))
    for metric in unestimated:
        _add(Finding("G-011", "INPUT", "LOW", WARN,
                     f"accepted but unestimated metrics (preserved, not consumed by twin v1): {metric}",
                     {"metric": metric, "day_index": day}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def check_prediction(risk_record: dict) -> dict:
    """Display-safety verdict for one risk prediction."""
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []

    def _add(finding: Finding):
        findings.append(finding)
        if finding.action == WITHHOLD:
            rejections.append(finding.message)
        else:
            flags.append(finding.message)

    unexpected = set(risk_record) - ALLOWED_OUTPUT_KEYS
    if unexpected:
        _add(Finding("G-006", "OUTPUT", "HIGH", WITHHOLD,
                     f"prediction carries unsupported output fields: {sorted(unexpected)}",
                     {"fields": sorted(str(f) for f in unexpected)}))
    if "prescription" in json_text(risk_record).lower() or "dosage" in json_text(risk_record).lower():
        _add(Finding("G-007", "OUTPUT", "HIGH", WITHHOLD,
                     "prediction output must never contain treatment instructions",
                     {}))
    uncertainty = risk_record.get("uncertainty", 0.0) or 0.0
    if uncertainty > UNCERTAINTY_FLAG:
        _add(Finding("G-008", "OUTPUT", "MEDIUM", WARN,
                     f"uncertainty {uncertainty:.2f} exceeds display threshold: show interval, not a point estimate",
                     {"uncertainty": uncertainty, "threshold": UNCERTAINTY_FLAG}))
    if risk_record.get("input_quality", 1.0) < 0.5:
        _add(Finding("G-009", "OUTPUT", "MEDIUM", WARN,
                     "input quality below 0.5: prediction is indicative only",
                     {"input_quality": risk_record.get("input_quality")}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def json_text(record: dict) -> str:
    try:
        return _json.dumps(record, sort_keys=True)
    except (TypeError, ValueError):
        return ""


def check_population(ehr) -> dict:
    """Out-of-distribution scope check. The demo weights assume adults."""
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []
    age = getattr(ehr, "age", None) if ehr is not None else None
    if age is not None and (age < 18 or age > 90):
        message = f"age {age:.0f} is outside the adult demo scope (18-90): treat output as out-of-distribution"
        flags.append(message)
        findings.append(Finding("G-010", "MODEL", "MEDIUM", WARN, message, {"age": age}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def check_schema(state: PatientState) -> dict:
    """G-012: feature-schema drift check against PatientState v1."""
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []
    if isinstance(state, dict):
        actual = set(state)
    else:
        actual = set(state.to_dict())
    if actual != STATE_SCHEMA_FIELDS:
        message = (
            "patient-state schema drift: "
            f"missing={sorted(STATE_SCHEMA_FIELDS - actual)} "
            f"unexpected={sorted(actual - STATE_SCHEMA_FIELDS)}"
        )
        rejections.append(message)
        findings.append(Finding("G-012", "INPUT", "HIGH", WITHHOLD, message,
                                {"missing": sorted(STATE_SCHEMA_FIELDS - actual),
                                 "unexpected": sorted(actual - STATE_SCHEMA_FIELDS)}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def check_counterfactuals(counterfactuals: dict | None) -> dict:
    """G-013/G-014: every evaluated policy needs a complete assumption
    ledger, and the ranking must honor the engine's own ordering."""
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []
    if counterfactuals is None:
        return {"rejections": rejections, "flags": flags, "findings": findings}
    ranking = counterfactuals.get("robust_ranking") or []
    for item in ranking:
        policy = item.get("policy")
        ledger = item.get("assumptions") or {}
        missing = sorted(LEDGER_REQUIRED_KEYS - set(ledger))
        if missing:
            message = (f"policy {policy} lacks a complete assumption ledger "
                       f"(missing: {', '.join(missing)}): counterfactual unevaluable")
            rejections.append(message)
            findings.append(Finding("G-013", "COUNTERFACTUAL", "HIGH", WITHHOLD, message,
                                    {"policy": policy, "missing": missing}))
    order = [(not r.get("feasible_under_all", True),
              r.get("worst_case_risk", float("inf")),
              r.get("nominal_risk", float("inf"))) for r in ranking]
    if order != sorted(order):
        message = "robust ranking violates engine ordering: output not independently verifiable"
        rejections.append(message)
        findings.append(Finding("G-014", "OUTPUT", "HIGH", WITHHOLD, message, {}))
    top = ranking[0] if ranking else None
    if top is not None and not top.get("feasible_under_all", True):
        message = (f"top-ranked policy {top.get('policy')} is infeasible under "
                   "perturbation: shown as rejected, never as recommended")
        flags.append(message)
        findings.append(Finding("G-014", "OUTPUT", "MEDIUM", WARN, message,
                                {"policy": top.get("policy")}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def check_model(model_context: dict | None) -> dict:
    """G-015: model identity and weights-digest verification."""
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []
    if model_context is None:
        return {"rejections": rejections, "flags": flags, "findings": findings}
    from .model_registry import get_model, weights_digest

    model_id = model_context.get("model_id")
    try:
        entry = get_model(model_id)
    except KeyError:
        message = f"unregistered model_id {model_id!r}: prediction not traceable"
        rejections.append(message)
        findings.append(Finding("G-015", "MODEL", "HIGH", WITHHOLD, message,
                                {"model_id": model_id}))
        return {"rejections": rejections, "flags": flags, "findings": findings}
    live = weights_digest()
    pinned = entry.get("weights_digest")
    if pinned is None or pinned != live:
        message = ("model weights do not match the registry pin: "
                   "possible tampering or unreviewed weight change")
        rejections.append(message)
        findings.append(Finding("G-015", "MODEL", "HIGH", WITHHOLD, message,
                                {"model_id": model_id, "pinned": bool(pinned)}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def check_deployment(deployment: dict | None) -> dict:
    """G-016: deployment-state inversion protection.

    A gate reporting clinical-use open without validated status is a
    contradiction: withhold rather than present. Closed gates and absent
    deployment context pass with the state recorded in stages.
    """
    rejections: list[str] = []
    flags: list[str] = []
    findings: list[Finding] = []
    if deployment is None:
        return {"rejections": rejections, "flags": flags, "findings": findings}
    if deployment.get("clinical_use") == "open":
        from .model_registry import get_model

        try:
            status = get_model(deployment.get("model_id", ""))["status"]
        except KeyError:
            status = "unknown"
        if status != "validated":
            message = ("deployment gate reports open for a model without "
                       f"validated status ({status}): refusing to present")
            rejections.append(message)
            findings.append(Finding("G-016", "DEPLOYMENT", "HIGH", WITHHOLD, message,
                                    {"model_id": deployment.get("model_id"),
                                     "status": status}))
    return {"rejections": rejections, "flags": flags, "findings": findings}


def verdict(state: PatientState, risk_record: dict, previous: PatientState | None = None, ehr=None,
            unestimated: tuple[str, ...] = (), counterfactuals: dict | None = None,
            model_context: dict | None = None, deployment: dict | None = None) -> dict:
    """Combined verdict across gates. display_allowed is False on any WITHHOLD.

    Historical keys (display_allowed/rejections/flags/scope) are unchanged;
    findings/stages/action are additive. Optional counterfactuals,
    model_context, and deployment inputs activate the G-013…G-016 rules;
    stages with no applicable rule report passed vacuously.
    """
    state_check = check_state(state, previous, unestimated)
    pred_check = check_prediction(risk_record)
    pop_check = check_population(ehr)
    schema_check = check_schema(state)
    counter_check = check_counterfactuals(counterfactuals)
    model_check = check_model(model_context)
    deploy_check = check_deployment(deployment)
    findings: list[Finding] = (
        state_check["findings"] + pred_check["findings"] + pop_check["findings"]
        + schema_check["findings"] + counter_check["findings"]
        + model_check["findings"] + deploy_check["findings"]
    )
    rejections = (state_check["rejections"] + pred_check["rejections"] + pop_check["rejections"]
                 + schema_check["rejections"] + counter_check["rejections"]
                 + model_check["rejections"] + deploy_check["rejections"])
    flags = (state_check["flags"] + pred_check["flags"] + pop_check["flags"]
             + schema_check["flags"] + counter_check["flags"]
             + model_check["flags"] + deploy_check["flags"])
    stages: dict[str, dict] = {}
    for stage in STAGES:
        stage_findings = [f for f in findings if f.stage == stage]
        stages[stage] = {
            "passed": not any(f.action == WITHHOLD for f in stage_findings),
            "rules": [f.rule_id for f in stage_findings],
        }
    if any(f.action == WITHHOLD for f in findings):
        action = WITHHOLD
    elif findings:
        action = WARN
    else:
        action = "ALLOW"
    return {
        "display_allowed": not rejections,
        "action": action,
        "rejections": rejections,
        "flags": flags,
        "findings": [f.to_dict() for f in findings],
        "stages": stages,
        "scope": "display-safety for decision support; not a clinical authority",
    }
