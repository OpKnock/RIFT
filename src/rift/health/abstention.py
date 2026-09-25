"""Abstention-harm analysis (Phase 13, research-grade).

Guardian WITHHOLD protects against bad displays, but withholding itself can
harm: a withheld prediction that precedes a real event is a missed chance to
inform care. This module quantifies that trade-off on backtest records.

Input records: {day, predicted_risk, uncertainty, withheld, outcome_event}.
Output: withhold rate, event rates among withheld vs shown predictions, and
a harm-review queue (withheld days where the event still occurred).

Research-grade: runs on synthetic backtest data unless a governed cohort is
supplied. It measures the abstention policy — it never validates clinical
safety, which requires the prospective study (see study-protocol-template).
"""
from __future__ import annotations


def analyze(records: list[dict]) -> dict:
    """Summarize abstention behavior and its association with outcomes."""
    rows = [dict(r) for r in records or []]
    total = len(rows)
    withheld = [r for r in rows if r.get("withheld")]
    shown = [r for r in rows if not r.get("withheld")]
    withhold_rate = len(withheld) / total if total else 0.0

    def event_rate(subset: list[dict]) -> float | None:
        if not subset:
            return None
        return sum(1 for r in subset if r.get("outcome_event")) / len(subset)

    withheld_event_rate = event_rate(withheld)
    shown_event_rate = event_rate(shown)
    missed = [r for r in withheld if r.get("outcome_event")]
    return {
        "n_total": total,
        "n_withheld": len(withheld),
        "n_shown": len(shown),
        "withhold_rate": withhold_rate,
        "withheld_event_rate": withheld_event_rate,
        "shown_event_rate": shown_event_rate,
        "n_missed_events": len(missed),
        "missed_event_rate_among_withheld": (len(missed) / len(withheld)) if withheld else None,
        "note": ("association only: withholding correlates with uncertainty, which "
                 "correlates with risk. Causal harm analysis needs the prospective study."),
    }


def harm_review_queue(records: list[dict]) -> list[dict]:
    """Withheld days where the event occurred: mandatory human review cases."""
    queue = []
    for r in records or []:
        if r.get("withheld") and r.get("outcome_event"):
            queue.append({
                "day": r.get("day"),
                "predicted_risk": r.get("predicted_risk"),
                "uncertainty": r.get("uncertainty"),
                "reason": "withheld prediction preceded a realized event: review whether "
                          "display (with warnings) would have changed care",
            })
    return sorted(queue, key=lambda item: (item["day"] is None, item["day"]))
