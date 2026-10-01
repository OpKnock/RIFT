"""Phase 14 tests: pipeline verification, resume, failure record."""
from __future__ import annotations

import json

from rift.health.cardiovascular import dataset, pipeline


def test_step_dataset_verifies_hash_and_artifacts():
    out = pipeline.step_dataset()
    manifest = json.loads((dataset.DATA_DIR / "manifests/dataset_manifest.json").read_text())
    assert out["source_hash"] == manifest["source_hash"]


def test_step_order_and_resume():
    assert pipeline.STEPS == ("dataset", "train", "evaluate", "calibrate",
                              "explain", "site")
    record = pipeline.run_pipeline(from_step="site")
    assert record["ok"] is True
    assert list(record["steps"]) == ["site"]
    on_disk = json.loads((dataset.DATA_DIR / "site" / "pipeline.json").read_text())
    assert on_disk == record


def test_invalid_step_rejected():
    try:
        pipeline.run_pipeline(from_step="nope")
    except ValueError:
        return
    raise SystemExit("pipeline accepted an unknown step")
