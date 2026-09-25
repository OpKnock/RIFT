"""Abstention-harm analysis on synthetic backtest records."""
from rift.health.abstention import analyze, harm_review_queue

RECORDS = [
    {"day": 0, "predicted_risk": 0.2, "uncertainty": 0.05, "withheld": False, "outcome_event": False},
    {"day": 1, "predicted_risk": 0.8, "uncertainty": 0.40, "withheld": True, "outcome_event": True},
    {"day": 2, "predicted_risk": 0.7, "uncertainty": 0.38, "withheld": True, "outcome_event": False},
    {"day": 3, "predicted_risk": 0.3, "uncertainty": 0.06, "withheld": False, "outcome_event": False},
]


def test_analyze_rates():
    result = analyze(RECORDS)
    assert result["n_total"] == 4
    assert result["n_withheld"] == 2
    assert result["withhold_rate"] == 0.5
    assert result["withheld_event_rate"] == 0.5
    assert result["shown_event_rate"] == 0.0
    assert result["n_missed_events"] == 1
    assert "association only" in result["note"]


def test_harm_queue_lists_withheld_events_only():
    queue = harm_review_queue(RECORDS)
    assert [item["day"] for item in queue] == [1]
    assert "review" in queue[0]["reason"]


def test_empty_input_never_crashes():
    result = analyze([])
    assert result["n_total"] == 0
    assert result["withheld_event_rate"] is None
    assert harm_review_queue([]) == []
