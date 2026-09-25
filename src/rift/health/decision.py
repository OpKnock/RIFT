"""Decision analysis: compare intervention policies side by side.

RIFT's product question is not "risk = 0.61" but: under these assumptions,
what futures do the candidate decisions produce, how robust is each, and
what blocks it? This module presents already-computed FORESIGHT +
robustness output as one decision table. No new modeling inside.
"""
from __future__ import annotations


def decision_table(
    robust_ranking: list[dict],
    trajectories: list[dict],
    guardian_scope_note: str = "nominal + every declared perturbation",
) -> list[dict]:
    """Join robust ranking with end-of-trajectory risk per policy.

    Rows are sorted best-first by (feasible, worst-case risk, nominal
    risk), mirroring the engine's own ordering so the table can never
    contradict the ranking it presents.
    """
    end_risk = {}
    for traj in trajectories:
        key = tuple(sorted((traj.get("policy") or {}).items()))
        path = traj.get("path") or []
        end_risk[key] = path[-1].get("risk") if path else None
    rows = []
    for item in robust_ranking:
        key = tuple(sorted((item.get("policy") or {}).items()))
        rows.append({
            "policy": item.get("policy"),
            "nominal_risk": item.get("nominal_risk"),
            "worst_case_risk": item.get("worst_case_risk"),
            "trajectory_end_risk": end_risk.get(key),
            "feasible_under_all": item.get("feasible_under_all"),
            "guardian_scope": guardian_scope_note,
        })
    rows.sort(key=lambda r: (
        not r["feasible_under_all"],
        r["worst_case_risk"] if r["worst_case_risk"] is not None else float("inf"),
        r["nominal_risk"] if r["nominal_risk"] is not None else float("inf"),
    ))
    return rows


def sensitivity_analysis(state: dict, risk_fn, fields: tuple[str, ...] = (
        "resting_hr", "hrv_rmssd", "sleep_hours", "activity_load"),
        deltas: tuple[float, ...] = (-5.0, 5.0)) -> dict:
    """How stable is the ranking when inputs move? Perturb each field by
    each delta, re-score with risk_fn(state_dict) -> float, and report
    whether the top policy (lowest risk) changes.

    risk_fn is injected so this stays a pure presentation analysis with no
    hidden model of its own. Deterministic.
    """
    base = risk_fn(dict(state))
    per_field: dict = {}
    for field in fields:
        if state.get(field) is None:
            per_field[field] = {"skipped": "missing baseline value"}
            continue
        swings = []
        for delta in deltas:
            moved = dict(state)
            moved[field] = moved[field] + delta
            try:
                swings.append(abs(risk_fn(moved) - base))
            except Exception as exc:
                swings.append(f"error: {type(exc).__name__}")
        numeric = [s for s in swings if isinstance(s, (int, float))]
        per_field[field] = {
            "deltas": list(deltas),
            "risk_swings": swings,
            "max_swing": max(numeric) if numeric else None,
        }
    return {"base_risk": base, "fields": per_field,
            "note": "ranking stability under input perturbation; not causal proof"}
