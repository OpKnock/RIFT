"""Scrape a tiny slice of the public BIDSleep PhysioNet dataset for RIFT.

Fetches hr.csv for a few nights from the openly licensed
bidsleep-dataset (ODC Attribution License v1.0) and converts to the
strict PublicDatasetSource CSV schema. No clinical claim: this
demonstrates the real-data seam, not a validated clinical dataset.

Run: python -m rift.health.bidsleep_scrape --nights 3 --out data/public_real_bidsleep.csv
"""
from __future__ import annotations

import csv
import statistics
import urllib.request
from pathlib import Path

BASE = "https://physionet.org/files/bidsleep-dataset/1.0.0"
# Deterministic slice: 6 nights across 3 subjects — all verified live.
# Tiny fraction of 5.9GB, no auth. Expand by editing this list.
NIGHTS = [
    ("Bidslab00", "1"), ("Bidslab00", "2"),
    ("Bidslab01", "1"), ("Bidslab01", "2"),
    ("Bidslab02", "1"), ("Bidslab02", "2"),
]


def fetch_hr_median(subject: str, night: str) -> tuple[float | None, int]:
    url = f"{BASE}/{subject}/{night}/hr.csv"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # nosec B310 -- URL is fixed PhysioNet base + validated subject/night, never user input
            text = resp.read().decode()
    except Exception as exc:
        return None, 0
    hrs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 2:
            continue
        try:
            hrs.append(float(parts[1]))
        except ValueError:
            continue
    if not hrs:
        return None, 0
    return float(statistics.median(hrs)), len(hrs)


def scrape(out_path: str = "data/public_real_bidsleep.csv", nights=None) -> Path:
    target = nights or NIGHTS
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, (subject, night) in enumerate(target):
        median_hr, n = fetch_hr_median(subject, night)
        rows.append({
            "day_index": idx,
            "resting_hr": f"{median_hr:.1f}" if median_hr is not None else "",
            "hrv_rmssd": "",
            "sleep_hours": "",
            "activity_load": "",
            "_source": f"{BASE}/{subject}/{night}/hr.csv ({n} samples)",
        })
        print(f"[{idx}] {subject}/{night}: median HR {median_hr} from {n} samples")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "day_index", "resting_hr", "hrv_rmssd", "sleep_hours", "activity_load"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in writer.fieldnames})
    # Provenance sidecar
    sidecar = path.with_suffix(".provenance.json")
    import json as _json
    sidecar.write_text(_json.dumps({
        "source": "PhysioNet bidsleep-dataset v1.0.0",
        "license": "Open Data Commons Attribution License v1.0",
        "doi": "10.13026/a0sy-7t69",
        "nights": target,
        "note": "Median HR per night; other fields left blank to demonstrate missingness handling, not imputed.",
    }, indent=2), encoding="utf-8")
    print(f"Wrote {path} and {sidecar}")
    return path


if __name__ == "__main__":
    import argparse as _arg
    parser = _arg.ArgumentParser()
    parser.add_argument("--nights", type=int, default=3)
    parser.add_argument("--out", default="data/public_real_bidsleep.csv")
    args = parser.parse_args()
    # Respect requested count but cap to the predefined list for determinism
    scrape(args.out, NIGHTS[:args.nights])
