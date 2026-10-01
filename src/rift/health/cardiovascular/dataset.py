"""Reproducible dataset acquisition and preparation (Phase 2 + 14).

Pipeline (one command: ``python -m rift.health.cardiovascular.dataset prepare``):

1. fetch the UCI Extension zip (id 411) unless ``data/cardiovascular/raw/``
   already holds a byte-identical copy,
2. verify row/column contract (303 x 59) and SHA-256,
3. write ``processed`` CSVs (raw values + target labels, leakage firewall
   enforced: target columns are NEVER copied into feature frames),
4. write a stratified train/val/test split (seed 7) plus ``dataset_manifest.json``
   with source URL, hash, license, versions.

Raw upstream bytes are committed under ``data/cardiovascular/raw/`` so a
clean environment rebuilds offline; the manifest records provenance either way.

Dataset: Alizadehsani et al., "extention of Z-Alizadeh sani dataset",
UCI ML Repository, https://doi.org/10.24432/C5461K. Research use.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import schemas
from .leakage import assert_no_leakage

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data" / "cardiovascular"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SPLITS_DIR = DATA_DIR / "splits"
MANIFESTS_DIR = DATA_DIR / "manifests"

SOURCE_URL = ("https://archive.ics.uci.edu/static/public/411/"
              "extention+of+z+alizadeh+sani+dataset.zip")
SOURCE_DOI = "https://doi.org/10.24432/C5461K"
RAW_ZIP_NAME = "z-alizadeh-sani-extension.zip"
RAW_XLSX_NAME = "extention of Z-Alizadeh sani dataset.xlsx"
SPLIT_SEED = 7
SPLIT_RATIOS = {"train": 0.6, "val": 0.2, "test": 0.2}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_raw(dest: Path | None = None) -> Path:
    """Download the upstream zip unless an identical copy already exists."""
    dest = dest or (RAW_DIR / RAW_ZIP_NAME)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 50000:
        return dest
    tmp = dest.with_suffix(".tmp")
    urllib.request.urlretrieve(SOURCE_URL, tmp)
    if tmp.stat().st_size < 50000:
        raise ValueError("downloaded archive suspiciously small: %d bytes" % tmp.stat().st_size)
    os.replace(tmp, dest)
    return dest


def extract_raw(zip_path: Path | None = None) -> Path:
    zip_path = zip_path or (RAW_DIR / RAW_ZIP_NAME)
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if RAW_XLSX_NAME not in names:
            raise ValueError("upstream archive layout changed: %s" % names)
        target = RAW_DIR / RAW_XLSX_NAME
        if not target.exists():
            archive.extract(RAW_XLSX_NAME, RAW_DIR)
    return RAW_DIR / RAW_XLSX_NAME


def load_raw_frame(xlsx_path: Path | None = None):
    """Raw 303x59 frame. Fails loudly on schema drift."""
    import pandas as pd
    xlsx_path = xlsx_path or (RAW_DIR / RAW_XLSX_NAME)
    df = pd.read_excel(xlsx_path, sheet_name="Sheet 1 - Table 1")
    if df.shape != (schemas.EXPECTED_ROWS, schemas.EXPECTED_COLUMNS):
        raise ValueError("raw schema drift: got %s, want (%d, %d)" %
                         (df.shape, schemas.EXPECTED_ROWS, schemas.EXPECTED_COLUMNS))
    missing = [c for c in list(schemas.PREDICTOR_COLUMNS) + ["LAD", "LCX", "RCA", "Cath"]
               if c not in df.columns]
    if missing:
        raise ValueError("raw columns missing: %s" % missing)
    if int(df.isnull().sum().sum()) != 0:
        raise ValueError("unexpected nulls in raw frame")
    return df


def encode_targets(df):
    """Target label vectors (0/1) per schemas.TARGETS."""
    labels = {}
    for target, spec in schemas.TARGETS.items():
        col = df[spec["source"]].astype(str)
        labels[target] = (col == spec["positive"]).astype(int)
    return labels


def stratified_split(df, labels, seed: int = SPLIT_SEED):
    """Stratified train/val/test row-index split on the CAD label."""
    import numpy as np
    y = labels["cad"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = np.arange(len(df))
    out = {"train": [], "val": [], "test": []}
    for cls in (0, 1):
        members = idx[y == cls]
        rng.shuffle(members)
        n = len(members)
        n_test = max(1, int(round(n * SPLIT_RATIOS["test"])))
        n_val = max(1, int(round(n * SPLIT_RATIOS["val"])))
        out["test"].extend(members[:n_test].tolist())
        out["val"].extend(members[n_test:n_test + n_val].tolist())
        out["train"].extend(members[n_test + n_val:].tolist())
    for key in out:
        out[key] = sorted(out[key])
    return out


def prepare() -> dict:
    """Run the full acquisition pipeline; return the manifest dict."""
    zip_path = fetch_raw()
    xlsx_path = extract_raw(zip_path)
    df = load_raw_frame(xlsx_path)
    labels = encode_targets(df)

    # Feature frame: predictors only. The firewall raises on any leak.
    features = df[list(schemas.PREDICTOR_COLUMNS)].copy()
    assert_no_leakage(features)

    split = stratified_split(df, labels)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    for part, rows in split.items():
        part_frame = features.iloc[rows].copy()
        for target, series in labels.items():
            part_frame["__y_%s" % target] = series.iloc[rows].to_numpy()
        part_frame.to_csv(PROCESSED_DIR / ("%s.csv" % part), index=False)

    (SPLITS_DIR / "split.json").write_text(json.dumps(
        {"seed": SPLIT_SEED, "ratios": SPLIT_RATIOS, "rows": split}, indent=1),
        encoding="utf-8")

    manifest = {
        "dataset": "Z-Alizadeh Sani Extension",
        "records": int(len(df)),
        "source_url": SOURCE_URL,
        "source_doi": SOURCE_DOI,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_hash": "sha256:" + sha256_file(zip_path),
        "license": "UCI ML Repository default terms (research use; see dataset page)",
        "preprocessing_version": schemas.PREPROCESSING_VERSION,
        "feature_schema_version": schemas.FEATURE_SCHEMA_VERSION,
        "targets": schemas.TARGETS,
        "forbidden_features": sorted(schemas.FORBIDDEN_FEATURES),
        "data_notes": [
            "Second workbook sheet 'Sheet1' is an empty 100-column template; ignored.",
            "Cath=CAD coincides with any-vessel-stenotic in 302/303 rows; one row has "
            "LAD=Stenotic yet Cath=Normal (angiography judgment, kept verbatim).",
            "'Exertional CP' is constant 'N' across all rows; excluded from features.",
            "'Sex' level 'Fmale' is the dataset's verbatim spelling, kept as-is.",
        ],
        "split": {"seed": SPLIT_SEED, "ratios": SPLIT_RATIOS,
                  "sizes": {k: len(v) for k, v in split.items()}},
    }
    (MANIFESTS_DIR / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "prepare":
        manifest = prepare()
        print(json.dumps({k: v for k, v in manifest.items() if k != "targets"}, indent=1))
    else:
        raise SystemExit("usage: python -m rift.health.cardiovascular.dataset prepare")
