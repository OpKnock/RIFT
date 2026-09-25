"""Multi-patient cohort synthesis for subgroup validation (Phase 15, synthetic).

No real patients: generates N synthetic patients with deterministic seeds
and staggered spell schedules, evaluates each through the same pipeline,
and reports per-patient + cross-patient metrics. This exercises the
patient-level split and fairness logic on synthetic data — the machinery
is real, the data is not clinical.
"""
from __future__ import annotations

from .demo_data import demo_series
from .ehr import demo_ehr, normalize_ehr
from .evaluate import backtest
from .subgroups import subgroup_metrics
from .twin import DigitalTwin


def cohort_backtest(n_patients: int = 5, days_per_patient: int = 60) -> dict:
    """Run held-out backtest per synthetic patient and aggregate."""
    patients = []
    for i in range(n_patients):
        seed = 100 + i * 17
        # Stagger spell days so patients differ
        spells = ((15 + i * 2, 2), (33 + i, 2), (50, 1))
        series = demo_series(seed=seed, days=days_per_patient, spells=spells)
        ehr, _ = normalize_ehr({**demo_ehr(), "patient_id": f"synth-patient-{i:02d}"})
        twin = DigitalTwin(ehr, series)
        report = backtest(twin, 30, days_per_patient - 1)
        patients.append({
            "patient_id": ehr.patient_id,
            "seed": seed,
            "report": report,
        })
    # Flatten per-day rows with patient tag for subgroup analysis
    all_rows = []
    for p in patients:
        for row in p["report"]["per_day"]:
            all_rows.append({**row, "patient_id": p["patient_id"]})
    overall = subgroup_metrics(all_rows)
    # Per-patient agreement for fairness
    per_patient = {p["patient_id"]: p["report"]["event_agreement"] for p in patients}
    worst_patient = min(per_patient, key=lambda k: per_patient[k]) if per_patient else None
    return {
        "n_patients": n_patients,
        "days_per_patient": days_per_patient,
        "patients": [
            {"patient_id": p["patient_id"], "seed": p["seed"],
             "agreement": p["report"]["event_agreement"],
             "sensitivity": p["report"]["sensitivity"],
             "specificity": p["report"]["specificity"],
             "events": p["report"]["confusion"]["tp"] + p["report"]["confusion"]["fn"]}
            for p in patients
        ],
        "overall": overall["overall"],
        "worst_patient": {"patient_id": worst_patient, "agreement": per_patient.get(worst_patient) if worst_patient else None},
        "subgroups": overall,
        "note": "synthetic multi-patient cohort; validates pipeline, not clinical generalizability",
    }
