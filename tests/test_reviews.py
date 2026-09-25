"""Clinician review ledger: validation, append-only chain, idempotency."""
import pytest

from rift.health.reviews import ACTIONS, ReviewLedger


def _ledger():
    return ReviewLedger()


def test_accept_records_with_evidence_link():
    ledger = _ledger()
    entry = ledger.record(action="ACCEPT", evidence_id="ev-1", reviewer_id="dr-a")
    assert entry["action"] == "ACCEPT"
    assert entry["evidence_id"] == "ev-1"
    assert entry["prev_hash"] == "GENESIS"


def test_unknown_action_rejected():
    with pytest.raises(ValueError, match="unknown review action"):
        _ledger().record(action="MAYBE", evidence_id="ev-1", reviewer_id="dr-a")


def test_missing_reviewer_and_evidence_rejected():
    with pytest.raises(ValueError, match="reviewer_id is required"):
        _ledger().record(action="ACCEPT", evidence_id="ev-1", reviewer_id="  ")
    with pytest.raises(ValueError, match="evidence_id is required"):
        _ledger().record(action="ACCEPT", evidence_id="", reviewer_id="dr-a")


def test_override_and_reject_require_rationale():
    ledger = _ledger()
    with pytest.raises(ValueError, match="rationale is required for OVERRIDE"):
        ledger.record(action="OVERRIDE", evidence_id="ev-1", reviewer_id="dr-a")
    with pytest.raises(ValueError, match="rationale is required for REJECT"):
        ledger.record(action="REJECT", evidence_id="ev-1", reviewer_id="dr-a")
    ok = ledger.record(action="OVERRIDE", evidence_id="ev-1",
                       reviewer_id="dr-a", rationale="trend contradicts risk")
    assert ok["action"] == "OVERRIDE"


def test_override_supersedes_without_mutating():
    ledger = _ledger()
    first = ledger.record(action="ACCEPT", evidence_id="ev-1", reviewer_id="dr-a")
    second = ledger.record(action="OVERRIDE", evidence_id="ev-1", reviewer_id="dr-b",
                           rationale="new bedside finding", supersedes=first["review_id"])
    assert second["supersedes"] == first["review_id"]
    assert ledger._entries[first["review_id"]]["action"] == "ACCEPT"
    with pytest.raises(ValueError, match="unknown review"):
        ledger.record(action="OVERRIDE", evidence_id="ev-1", reviewer_id="dr-b",
                      rationale="x", supersedes="nope")


def test_identical_inputs_idempotent_and_chained():
    ledger = _ledger()
    a = ledger.record(action="ACCEPT", evidence_id="ev-1", reviewer_id="dr-a")
    b = ledger.record(action="ACCEPT", evidence_id="ev-1", reviewer_id="dr-a")
    assert a["review_id"] == b["review_id"]
    assert ledger.stats()["total"] == 1
    c = ledger.record(action="REQUEST_REVIEW", evidence_id="ev-2", reviewer_id="dr-a")
    assert c["prev_hash"] == a["review_id"]
    stats = ledger.stats()
    assert stats["by_action"]["ACCEPT"] == 1
    assert stats["by_action"]["REQUEST_REVIEW"] == 1
    assert set(stats["by_action"]) == set(ACTIONS)


def test_list_capped_newest_first_and_export_ordered():
    ledger = _ledger()
    ids = [ledger.record(action="ACCEPT", evidence_id=f"ev-{i}", reviewer_id="dr-a")["review_id"]
           for i in range(5)]
    listed = ledger.list(limit=2)
    assert [e["review_id"] for e in listed] == [ids[4], ids[3]]
    assert [e["review_id"] for e in ledger.export()] == ids
