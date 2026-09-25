"""Subgroup evaluation: where does the system work, and where doesn't it.

Splits evaluated per-day rows along honest, pre-declared dimensions —
time period, data completeness, event prevalence — and reports the same
metrics per subgroup plus the worst subgroup. No subgroup is hidden:
small groups carry explicit sample counts so weak slices read as weak
evidence, not as failures to display.
"""
from __future__ import annotations


def _metrics(rows: list[dict]) -> dict:
    tp = sum(1 for r in rows if r["predicted_event"] and r["realized_event"])
    tn = sum(1 for r in rows if not r["predicted_event"] and not r["realized_event"])
    fp = sum(1 for r in rows if r["predicted_event"] and not r["realized_event"])
    fn = sum(1 for r in rows if not r["predicted_event"] and r["realized_event"])
    total = tp + tn + fp + fn
    brier = (sum((r["predicted_risk"] - (1.0 if r["realized_event"] else 0.0)) ** 2
                 for r in rows) / total) if total else None
    return {
        "n": total,
        "events": tp + fn,
        "agreement": (tp + tn) / total if total else None,
        "sensitivity": tp / (tp + fn) if (tp + fn) else None,
        "specificity": tn / (tn + fp) if (tn + fp) else None,
        "brier": brier,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def split_dimensions(per_day: list[dict], completeness: dict[int, float] | None = None) -> dict[str, dict[int, str]]:
    """Assign each evaluated day to one bucket per dimension.

    Dimensions are fixed upfront (never data-mined): first/second half of
    the window, complete vs degraded inputs (needs a day->completeness map),
    event vs non-event days. Unknown completeness degrades to a single
    'unmeasured' bucket rather than guessing.
    """
    days = sorted(d["day"] for d in per_day)
    midpoint = days[len(days) // 2] if days else 0
    groups: dict[str, dict[int, str]] = {"period": {}, "completeness": {}, "outcome": {}}
    for row in per_day:
        day = row["day"]
        groups["period"][day] = "first-half" if day < midpoint else "second-half"
        if completeness is None or day not in completeness:
            groups["completeness"][day] = "unmeasured"
        else:
            groups["completeness"][day] = "complete" if completeness[day] >= 0.9 else "degraded"
        groups["outcome"][day] = "event-day" if row["realized_event"] else "non-event-day"
    return groups


def subgroup_metrics(per_day: list[dict], completeness: dict[int, float] | None = None) -> dict:
    """Metrics per subgroup plus overall and worst-subgroup comparison."""
    groups = split_dimensions(per_day, completeness)
    by_dimension: dict = {}
    for dimension, assignment in groups.items():
        buckets: dict[str, list[dict]] = {}
        for row in per_day:
            buckets.setdefault(assignment[row["day"]], []).append(row)
        by_dimension[dimension] = {name: _metrics(rows) for name, rows in sorted(buckets.items())}
    overall = _metrics(per_day)
    agreements = [(f"{dim}/{name}", m["agreement"])
                  for dim, buckets in by_dimension.items()
                  for name, m in buckets.items()
                  if m["agreement"] is not None and m["n"] >= 3]
    worst = min(agreements, key=lambda kv: kv[1]) if agreements else (None, None)
    return {"overall": overall, "by_dimension": by_dimension,
            "worst_subgroup": {"name": worst[0], "agreement": worst[1]},
            "dimensions": ["period", "completeness", "outcome"]}
