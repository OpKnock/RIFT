"""Structured EHR input schema + normalization. Synthetic demo data only."""
from __future__ import annotations

from .models import EHRRecord

KNOWN_CONDITIONS = ("hypertension", "type_2_diabetes", "hyperlipidemia", "asthma", "none")
KNOWN_MEDICATIONS = ("beta_blocker", "ace_inhibitor", "statin", "metformin", "none")


def normalize_ehr(raw: dict | None) -> tuple[EHRRecord, list[str]]:
    """Validate raw EHR JSON into (EHRRecord, issues).

    Never raises on bad input: problems are returned as issue strings so the
    twin can display data-quality flags instead of crashing. Unknown
    conditions/medications are kept verbatim but flagged.
    """
    issues: list[str] = []
    if not isinstance(raw, dict):
        return EHRRecord(), ["ehr payload must be a JSON object"]

    def _num(key: str, lo: float, hi: float):
        value = raw.get(key)
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            issues.append(f"ehr.{key} is not numeric and was ignored")
            return None
        if not (lo <= number <= hi):
            issues.append(f"ehr.{key}={number} out of range [{lo}, {hi}] and was ignored")
            return None
        return number

    conditions = tuple(str(c) for c in (raw.get("conditions") or []) if isinstance(c, str))
    medications = tuple(str(m) for m in (raw.get("medications") or []) if isinstance(m, str))
    for cond in conditions:
        if cond not in KNOWN_CONDITIONS:
            issues.append(f"unknown condition '{cond}' kept verbatim (no model effect)")
    for med in medications:
        if med not in KNOWN_MEDICATIONS:
            issues.append(f"unknown medication '{med}' kept verbatim (no model effect)")

    record = EHRRecord(
        patient_id=str(raw.get("patient_id") or "demo-patient-01"),
        age=_num("age", 0.0, 120.0),
        sex=raw.get("sex") if isinstance(raw.get("sex"), str) else None,
        conditions=conditions,
        medications=medications,
        resting_hr_clinic=_num("resting_hr_clinic", 25.0, 220.0),
        systolic_bp=_num("systolic_bp", 50.0, 300.0),
    )
    if record.age is None:
        issues.append("missing age: age-related susceptibility uses a neutral default")
    return record, issues


def demo_ehr() -> dict:
    """Deterministic synthetic EHR fixture. NOT clinically validated."""
    return {
        "patient_id": "demo-patient-01",
        "age": 58.0,
        "sex": "M",
        "conditions": ["hypertension", "hyperlipidemia"],
        "medications": ["ace_inhibitor", "statin"],
        "resting_hr_clinic": 72.0,
        "systolic_bp": 138.0,
    }
