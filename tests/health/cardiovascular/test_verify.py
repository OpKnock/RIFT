"""Phase 19 test: the verify checklist is green end to end."""
from __future__ import annotations

from rift.health.cardiovascular import verify


def test_verify_checklist_all_green():
    results = verify.run_all()
    assert len(results) == len(verify.CHECKS) == 7
    failures = [(name, detail) for name, ok, detail in results if not ok]
    assert failures == [], failures
    assert verify.print_results(results) is True
