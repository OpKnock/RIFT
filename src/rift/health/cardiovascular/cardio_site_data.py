"""Track-A site data (Phases 8-10): demo patients + JSON copies for the UI.

Generates ``data/cardiovascular/site/demo_patients.json`` (three fixed
test-split patients with calibrated probabilities) and mirrors it plus
the evaluation reports into ``stitch-ui/live/cardio/`` so the static
``:8000`` preview can fetch them with relative paths. Re-running is
byte-deterministic; a test pins the mirror copies to the sources.

One command: ``python -m rift.health.cardiovascular.cardio_site_data``
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import calibration, evaluate, registry, schemas, targets

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data" / "cardiovascular"
SITE_DIR = DATA_DIR / "site"
UI_DATA_DIR = REPO_ROOT / "stitch-ui" / "live" / "cardio"

DISPLAY_FIELDS = ("Age", "Sex", "Typical Chest Pain", "Atypical", "Nonanginal",
                  "HTN", "FH", "EF-TTE", "Region RWMA", "Tinversion",
                  "St Depression", "FBS", "TG", "LDL")


def _test_frame():
    import pandas as pd
    return pd.read_csv(DATA_DIR / "processed" / "test.csv")


def build_demo_patients() -> list:
    """Three fixed patients: classic positive, clear negative, discordant."""
    frame = _test_frame()
    cad_scores = calibration.predict_calibrated("cad-v1", frame)
    cad_label = targets.read_labels(frame, "cad").to_numpy()
    import numpy as np
    scores = np.asarray(cad_scores)
    pos = np.where(cad_label == 1)[0]
    neg = np.where(cad_label == 0)[0]
    picks = {
        "classic-positive": int(pos[int(scores[pos].argmax())]),
        "clear-negative": int(neg[int(scores[neg].argmin())]),
        "discordant": int(pos[int(scores[pos].argmin())]),
    }
    manifest = json.loads((DATA_DIR / "manifests/dataset_manifest.json").read_text())
    patients = []
    for slug, idx in picks.items():
        row = frame.iloc[idx]
        probs = {}
        for target in ("cad", "lad", "lcx", "rca"):
            probs[target] = float(
                calibration.predict_calibrated(registry.MODEL_IDS[target],
                                               frame.iloc[[idx]])[0])
        patients.append({
            "slug": slug,
            "test_row": int(idx),
            "labels": {t: int(targets.read_labels(frame.iloc[[idx]], t).iloc[0])
                       for t in ("cad", "lad", "lcx", "rca")},
            "display": {f: _jsonable(row[f]) for f in DISPLAY_FIELDS},
            "calibrated_probabilities": probs,
            "dataset_hash": manifest["source_hash"],
        })
    return patients


def _jsonable(value):
    import math
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def sync_site_data() -> dict:
    """Write demo patients + mirror reports into the static UI directory."""
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    UI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    patients = build_demo_patients()
    (SITE_DIR / "demo_patients.json").write_text(
        json.dumps(patients, indent=1), encoding="utf-8")
    mirrored = {"demo_patients.json": SITE_DIR / "demo_patients.json",
                "report.json": evaluate.EVAL_DIR / "report.json",
                "calibration.json": evaluate.EVAL_DIR / "calibration.json",
                "explainability.json": evaluate.EVAL_DIR / "explainability.json"}
    for name, src in mirrored.items():
        shutil.copyfile(src, UI_DATA_DIR / name)
    return {"patients": [p["slug"] for p in patients],
            "mirrored": sorted(mirrored)}


if __name__ == "__main__":
    print(json.dumps(sync_site_data(), indent=1))
