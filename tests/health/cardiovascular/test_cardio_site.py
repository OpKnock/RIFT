"""Phases 8-10 tests: demo patients honest, UI mirrors exact, pages wired."""
from __future__ import annotations

import json

from rift.health.cardiovascular.cardio_site_data import REPO_ROOT

UI_DATA = REPO_ROOT / "stitch-ui" / "live" / "cardio"

EXPECTED = {"demo_patients.json", "model_cards.json", "report.json",
            "calibration.json", "explainability.json"}


def test_mirrors_match_sources_byte_for_byte():
    from rift.health.cardiovascular import evaluate
    sources = {"demo_patients.json": evaluate.DATA_DIR / "site" / "demo_patients.json",
               "model_cards.json": evaluate.DATA_DIR / "site" / "model_cards.json",
               "report.json": evaluate.EVAL_DIR / "report.json",
               "calibration.json": evaluate.EVAL_DIR / "calibration.json",
               "explainability.json": evaluate.EVAL_DIR / "explainability.json"}
    assert {p.name for p in UI_DATA.iterdir()} == EXPECTED
    for name, src in sources.items():
        assert (UI_DATA / name).read_bytes() == src.read_bytes(), name


def test_demo_patients_are_test_rows_with_labels():
    from rift.health.cardiovascular import cardio_site_data, dataset, schemas, targets
    patients = json.loads((UI_DATA / "demo_patients.json").read_text())
    assert [p["slug"] for p in patients] == ["classic-positive", "clear-negative", "discordant"]
    raw = dataset.load_raw_frame()
    manifest = json.loads((dataset.DATA_DIR / "manifests/dataset_manifest.json").read_text())
    for patient in patients:
        assert manifest["source_hash"] == patient["dataset_hash"]
        for target in ("cad", "lad", "lcx", "rca"):
            probs = patient["calibrated_probabilities"][target]
            assert 0.0 <= probs <= 1.0
            assert patient["labels"][target] in (0, 1)
        assert set(patient["display"]) == set(cardio_site_data.DISPLAY_FIELDS)
        assert set(patient["counterfactuals"]) == {"cad", "lad", "lcx", "rca"}
        for target, flips in patient["counterfactuals"].items():
            assert len(flips) <= 3
            for flip in flips:
                assert (flip["prob_after"] >= 0.5) != (
                    patient["calibrated_probabilities"][target] >= 0.5)


def test_demo_generation_deterministic():
    from rift.health.cardiovascular import cardio_site_data
    on_disk = json.loads((UI_DATA / "demo_patients.json").read_text())
    assert cardio_site_data.build_demo_patients() == on_disk


def test_pages_and_scripts_wired():
    ui = REPO_ROOT / "stitch-ui"
    coronary = (ui / "coronary.html").read_text(encoding="utf-8")
    assert "./live/coronary.js" in coronary and "not a medical device" in coronary
    assert "whatif-panel" in coronary
    viewer = (ui / "live" / "coronary.js").read_text(encoding="utf-8")
    assert "demo_patients.json" in viewer
    for seg in ("'lad'", "'lcx'", "'rca'"):
        assert seg in viewer
    dash = (ui / "cardio-dashboard.html").read_text(encoding="utf-8")
    assert "./live/cardio-dashboard.js" in dash and "RCA AUC 0.594" in dash
    script = (ui / "live" / "cardio-dashboard.js").read_text(encoding="utf-8")
    for name in ("report.json", "calibration.json", "explainability.json",
                 "model_cards.json"):
        assert name in script
