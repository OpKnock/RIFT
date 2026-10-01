"""Track-A pipeline (Phase 14): dataset → train → evaluate → calibrate → explain → site.

One command reproduces every Track A artifact from the raw UCI zip:
``python -m rift.health.cardiovascular.pipeline``. Steps run in order,
each verified before the next starts; a ``--from-step`` flag resumes
mid-chain (e.g. ``--from-step site`` after editing only UI code).
Writes ``data/cardiovascular/site/pipeline.json`` with per-step timing
and artifact hashes.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from . import calibration, cardio_site_data, dataset, evaluate, explain, train

STEPS = ("dataset", "train", "evaluate", "calibrate", "explain", "site")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def step_dataset() -> dict:
    """Verify raw hash + processed artifacts (no re-download, no network)."""
    manifest = json.loads((dataset.DATA_DIR / "manifests/dataset_manifest.json").read_text())
    raw = dataset.DATA_DIR / "raw" / "z-alizadeh-sani-extension.zip"
    if not raw.exists():
        raise ValueError("raw zip missing: %s" % raw)
    if ("sha256:" + _hash(raw)) != manifest["source_hash"]:
        raise ValueError("raw zip hash drift: upstream data changed")
    for name in ("train.csv", "val.csv", "test.csv"):
        if not (dataset.DATA_DIR / "processed" / name).exists():
            raise ValueError("processed artifact missing: %s" % name)
    if not (dataset.DATA_DIR / "splits" / "split.json").exists():
        raise ValueError("split manifest missing")
    return {"source_hash": manifest["source_hash"]}


def step_train() -> dict:
    return train.train_all()


def step_evaluate() -> dict:
    return evaluate.evaluate_all()


def step_calibrate() -> dict:
    return calibration.calibrate_all()


def step_explain() -> dict:
    return explain.explain_all()


def step_site() -> dict:
    return cardio_site_data.sync_site_data()


RUNNERS = {"dataset": step_dataset, "train": step_train,
           "evaluate": step_evaluate, "calibrate": step_calibrate,
           "explain": step_explain, "site": step_site}


def run_pipeline(from_step: str = "dataset") -> dict:
    """Run steps in order from ``from_step``; returns the run record."""
    if from_step not in STEPS:
        raise ValueError("unknown pipeline step: %r (choose from %s)" % (from_step, list(STEPS)))
    record = {"steps": {}, "ok": True}
    for step in STEPS[STEPS.index(from_step):]:
        started = time.monotonic()
        try:
            RUNNERS[step]()
            record["steps"][step] = {"ok": True,
                                     "seconds": round(time.monotonic() - started, 1)}
            print("ok   %-9s %5.1fs" % (step, time.monotonic() - started), flush=True)
        except Exception as exc:  # fail fast, record where
            record["steps"][step] = {"ok": False, "error": str(exc)[:300]}
            record["ok"] = False
            print("FAIL %-9s %s" % (step, exc), flush=True)
            break
    out = dataset.DATA_DIR / "site" / "pipeline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


if __name__ == "__main__":
    from_step = "dataset"
    for arg in sys.argv[1:]:
        if arg.startswith("--from-step="):
            from_step = arg.split("=", 1)[1]
    record = run_pipeline(from_step)
    sys.exit(0 if record["ok"] else 1)
