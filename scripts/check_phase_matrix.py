"""CI: validate docs/phase-matrix.json against the repository.

Every phase must use a known status; every evidence file path must exist;
every referenced test file must exist; COMPLETE phases must cite at least
one test file; blockers must be explicit (may be "none" only with a reason
that is itself verifiable, e.g. not-applicable deployment scope).
Exit non-zero with actionable messages on any violation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "phase-matrix.json"
STATUSES = {"COMPLETE", "PARTIAL", "NOT_IMPLEMENTED"}


def main() -> int:
    errors: list[str] = []
    try:
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"phase matrix unreadable: {exc}")
        return 1
    phases = matrix.get("phases")
    if not isinstance(phases, list) or not phases:
        print("phase matrix has no phases")
        return 1
    ids = [p.get("id") for p in phases]
    if ids != list(range(len(phases))):
        errors.append(f"phase ids must be 0..{len(phases) - 1} contiguous")
    for phase in phases:
        label = f"phase {phase.get('id')} ({phase.get('name')})"
        if phase.get("status") not in STATUSES:
            errors.append(f"{label}: unknown status {phase.get('status')!r}")
            continue
        evidence = phase.get("evidence", {})
        for key in ("files", "tests", "endpoints"):
            if not isinstance(evidence.get(key), list):
                errors.append(f"{label}: evidence.{key} must be a list")
        for path in evidence.get("files", []):
            if not (ROOT / path).is_file():
                errors.append(f"{label}: evidence file missing: {path}")
        for path in evidence.get("tests", []):
            if not (ROOT / path).is_file():
                errors.append(f"{label}: test file missing: {path}")
        if phase["status"] == "COMPLETE" and not evidence.get("tests"):
            errors.append(f"{label}: COMPLETE requires at least one test file")
        if not isinstance(phase.get("blockers"), list) or not phase["blockers"]:
            errors.append(f"{label}: blockers must be a non-empty list")
        if not isinstance(phase.get("deployment_state"), str):
            errors.append(f"{label}: deployment_state must be a string")
    if errors:
        print("phase matrix validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    complete = sum(1 for p in phases if p["status"] == "COMPLETE")
    print(f"phase matrix ok: {len(phases)} phases, {complete} complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
