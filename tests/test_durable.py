"""Durable JSONL store + crash-safe ledgers."""
import json

import pytest

from rift.durable import JsonlStore
from rift.health import prospective as pros_module
from rift.health.prospective import ProspectiveManager
from rift.health.reviews import ReviewLedger


def test_append_fsync_replay(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    store = JsonlStore(path)
    store.append({"a": 1})
    store.append({"b": [1, 2]})
    assert JsonlStore(path).load() == [{"a": 1}, {"b": [1, 2]}]
    assert store.count() == 2


def test_corrupt_line_fails_closed_with_lineno(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('{"ok": true}\n{broken\n')
    with pytest.raises(ValueError, match="line 2"):
        JsonlStore(path).load()


def test_non_dict_rejected(tmp_path):
    with pytest.raises(ValueError, match="dict records"):
        JsonlStore(str(tmp_path / "x.jsonl")).append([1, 2])


def test_reviews_ledger_survives_restart(tmp_path):
    path = str(tmp_path / "reviews.jsonl")
    first = ReviewLedger(store_path=path)
    assert first.durable is True
    entry = first.record(action="ACCEPT", evidence_id="ev-1", reviewer_id="dr-a")
    second = ReviewLedger(store_path=path)  # simulated restart
    assert second.stats()["total"] == 1
    assert second.list()[0]["review_id"] == entry["review_id"]
    assert second._head_hash == entry["review_id"]


def test_prospective_ledger_survives_restart(tmp_path):
    path = str(tmp_path / "pros.jsonl")
    first = ProspectiveManager(store_path=path)
    locked = first.lock_prediction("p1", 3, 0.4, False, "hash-1")
    first.reconcile_outcome(locked["lock_id"], True)
    second = ProspectiveManager(store_path=path)
    assert second.stats() == {"n_locked": 1, "n_reconciled": 1, "agreement": 0.0}


def test_in_memory_ledgers_stay_demo_grade():
    assert ReviewLedger().durable is False
    assert ProspectiveManager().durable is False
    assert pros_module.manager.durable is False  # default process: demo mode
