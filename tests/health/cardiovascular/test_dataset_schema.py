"""Phase 2 tests: dataset schema, manifest, splits, feature contract.

Locks the Z-Alizadeh Sani Extension integration: 303 records, exact
target distributions, valid provenance manifest, stratified disjoint
splits, and a leakage-free 59-feature contract.
"""
import hashlib
import json
from pathlib import Path

import pytest

from rift.health.cardiovascular import dataset, features, leakage, schemas, targets

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "cardiovascular"


def test_raw_contract_rows_columns_no_nulls():
    df = dataset.load_raw_frame()
    assert df.shape == (schemas.EXPECTED_ROWS, schemas.EXPECTED_COLUMNS)
    assert set(schemas.PREDICTOR_COLUMNS) | {"LAD", "LCX", "RCA", "Cath"} == set(df.columns)
    assert int(df.isnull().sum().sum()) == 0


def test_target_distributions_exact():
    df = dataset.load_raw_frame()
    labels = dataset.encode_targets(df)
    assert labels["cad"].sum() == 216 and (labels["cad"] == 0).sum() == 87
    assert labels["lad"].sum() == 177 and (labels["lad"] == 0).sum() == 126
    assert labels["lcx"].sum() == 119 and (labels["lcx"] == 0).sum() == 184
    assert labels["rca"].sum() == 114 and (labels["rca"] == 0).sum() == 189
    # CAD consistency: Cath=CAD iff at least one vessel stenotic holds for
    # 302/303 rows. The single exception (LAD=Stenotic yet Cath=Normal) is
    # real angiography judgment, not a pipeline bug: pin it exactly so any
    # data change fails loudly instead of silently shifting labels.
    cad = labels["cad"].to_numpy()
    any_stenotic = ((labels["lad"] + labels["lcx"] + labels["rca"]).to_numpy() > 0).astype(int)
    mismatched = (cad != any_stenotic).sum()
    assert mismatched == 1
    row = df.iloc[[i for i in range(len(df)) if cad[i] != any_stenotic[i]][0]]
    assert row["LAD"] == "Stenotic" and row["Cath"] == "Normal"


def test_manifest_complete_and_hash_matches_bytes():
    manifest = json.loads((DATA / "manifests/dataset_manifest.json").read_text())
    for key in ("dataset", "records", "source_url", "source_doi", "retrieved_at",
                "source_hash", "license", "preprocessing_version",
                "feature_schema_version", "targets", "forbidden_features", "split"):
        assert key in manifest, key
    assert manifest["records"] == 303
    assert manifest["feature_schema_version"] == schemas.FEATURE_SCHEMA_VERSION
    assert manifest["preprocessing_version"] == schemas.PREPROCESSING_VERSION
    assert sorted(manifest["forbidden_features"]) == ["Cath", "LAD", "LCX", "RCA"]
    raw = DATA / "raw" / dataset.RAW_ZIP_NAME
    assert manifest["source_hash"] == "sha256:" + hashlib.sha256(raw.read_bytes()).hexdigest()
    assert manifest["split"]["seed"] == dataset.SPLIT_SEED
    assert manifest["split"]["sizes"] == {"train": 183, "val": 60, "test": 60}
    assert len(manifest["data_notes"]) >= 4


def test_splits_disjoint_covering_stratified():
    split = json.loads((DATA / "splits/split.json").read_text())["rows"]
    train, val, test = (set(split["train"]), set(split["val"]), set(split["test"]))
    assert len(train) == 183 and len(val) == 60 and len(test) == 60
    assert not (train & val or train & test or val & test)
    assert train | val | test == set(range(303))
    labels = dataset.encode_targets(dataset.load_raw_frame())["cad"].to_numpy()
    for part, rows in (("train", train), ("val", val), ("test", test)):
        positives = sum(labels[r] for r in rows)
        rate = positives / len(rows)
        # Overall CAD rate 216/303 = 0.713; each split must carry both classes
        # within a documented tolerance band.
        assert 0 < positives < len(rows), part
        assert abs(rate - 216 / 303) < 0.08, (part, rate)


def test_processed_match_splits_and_labels():
    import pandas as pd
    df = dataset.load_raw_frame()
    labels = dataset.encode_targets(df)
    split = json.loads((DATA / "splits/split.json").read_text())["rows"]
    for part in ("train", "val", "test"):
        frame = pd.read_csv(DATA / "processed" / ("%s.csv" % part))
        assert len(frame) == len(split[part])
        for target in ("cad", "lad", "lcx", "rca"):
            col = targets.label_column(target)
            assert col in frame.columns
            expected = labels[target].iloc[split[part]].to_numpy()
            assert (frame[col].to_numpy() == expected).all(), (part, target)
        feature_cols = [c for c in frame.columns if not c.startswith("__y_")]
        assert set(feature_cols) == set(schemas.PREDICTOR_COLUMNS)
        leakage.assert_no_leakage(frame[feature_cols])


def test_feature_contract_stable():
    names = features.model_features()
    assert len(names) == 59
    assert not (set(names) & set(schemas.FORBIDDEN_FEATURES))
    assert "Exertional CP" not in names
    assert names == features.model_features()  # order stable across calls
    assert set(features.describe()["features"]) == set(names)
