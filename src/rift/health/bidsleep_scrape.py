"""Scrape a tiny slice of the public BIDSleep PhysioNet dataset for RIFT.

Fetches hr.csv and motion.csv for a few nights from the openly licensed
bidsleep-dataset (ODC Attribution License v1.0) and converts to a
provenance-rich CSV schema. No clinical claim: this demonstrates the
real-data seam with proper identity preservation, not a validated clinical dataset.

Run: python -m rift.health.bidsleep_scrape --nights 3 --out data/public_real_bidsleep.csv
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

BASE = "https://physionet.org/files/bidsleep-dataset/1.0.0"
# Deterministic slice: 6 nights across 3 subjects — all verified live.
# Tiny fraction of 5.9GB, no auth. Expand by editing this list.
NIGHTS = [
    ("Bidslab00", "1"), ("Bidslab00", "2"),
    ("Bidslab01", "1"), ("Bidslab01", "2"),
    ("Bidslab02", "1"), ("Bidslab02", "2"),
]


class FetchResult(TypedDict):
    success: bool
    url: str
    http_status: int | None
    retrieved_at: str
    content_sha256: str | None
    row_count: int
    error: str | None


def fetch_with_provenance(url: str, timeout: int = 30) -> tuple[FetchResult, str]:
    """Fetch a URL and return (provenance_result, text_content).
    
    Fails closed: any exception results in success=False with error details.
    """
    result: FetchResult = {
        "success": False,
        "url": url,
        "http_status": None,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": None,
        "row_count": 0,
        "error": None,
    }
    text = ""
    # Scheme allowlist: urllib supports file:// and custom schemes, so every
    # fetch target must be https (fixed PhysioNet base + validated subject/night).
    from urllib.parse import urlparse as _urlparse

    if _urlparse(url).scheme != "https" or not url.startswith(BASE):
        result["error"] = "refusing non-allowlisted fetch target"
        return result, text
    try:
        request = urllib.request.Request(url, headers={"Accept": "text/csv"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # nosec B310 -- allowlisted above; nosemgrep -- fixed https base, validated inputs
            result["http_status"] = resp.getcode()
            content = resp.read()
            result["content_sha256"] = hashlib.sha256(content).hexdigest()
            text = content.decode(errors="replace")
            result["success"] = True
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["error"] = f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        result["error"] = f"URL error: {exc.reason}"
    except Exception as exc:  # pragma: no cover - defensive
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result, text


def parse_hr_csv(text: str) -> tuple[list[float], int]:
    """Parse hr.csv and return (hr_values, valid_row_count)."""
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
    return hrs, len(hrs)


def parse_motion_csv(text: str, max_rows: int = 8000) -> tuple[list[float], int]:
    """Parse motion.csv and return (magnitudes, valid_row_count)."""
    import math
    mags = []
    lines = text.splitlines()
    if not lines:
        return mags, 0
    # Skip header
    for line in lines[1:max_rows+1]:
        try:
            parts = line.strip().split(",")
            if len(parts) < 4:
                continue
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            mags.append(math.sqrt(x*x + y*y + z*z))
        except ValueError:
            continue
    return mags, len(mags)


def scrape(out_path: str = "data/public_real_bidsleep.csv", nights=None) -> Path:
    """Scrape BIDSleep data with full provenance tracking.
    
    Output CSV schema:
    subject_id,recording_id,date,metric,value,unit,source,provenance_json
    
    Where provenance_json contains: url, http_status, retrieved_at, content_sha256, row_count
    """
    target = nights or NIGHTS
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ["subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"]
    rows = []
    all_provenance = []
    
    for subject, night in target:
        recording_id = f"{subject}_night{night}"
        # Use a nominal date for the recording (BIDSleep doesn't expose real dates)
        recording_date = f"2024-01-{int(night):02d}"  # placeholder date per night
        
        # Fetch HR
        hr_url = f"{BASE}/{subject}/{night}/hr.csv"
        hr_prov, hr_text = fetch_with_provenance(hr_url)
        
        # Fetch motion
        motion_url = f"{BASE}/{subject}/{night}/motion.csv"
        motion_prov, motion_text = fetch_with_provenance(motion_url)
        
        # Both must succeed for this recording to be included (fail closed)
        if not hr_prov["success"]:
            raise RuntimeError(f"Failed to fetch HR for {subject}/{night}: {hr_prov['error']}")
        if not motion_prov["success"]:
            raise RuntimeError(f"Failed to fetch motion for {subject}/{night}: {motion_prov['error']}")
        
        hrs, hr_count = parse_hr_csv(hr_text)
        mags, motion_count = parse_motion_csv(motion_text)
        
        if not hrs:
            raise RuntimeError(f"No valid HR samples for {subject}/{night}")
        if not mags:
            raise RuntimeError(f"No valid motion samples for {subject}/{night}")
        
        # Median HR (instantaneous heart rate, NOT resting HR)
        median_hr = float(statistics.median(hrs))
        # Mean acceleration magnitude (raw sensor metric, NOT clinical activity_load)
        mean_mag = float(statistics.mean(mags))
        
        # Provenance for HR
        hr_prov["row_count"] = hr_count
        provenance_json = json.dumps(hr_prov, separators=(",", ":"))
        rows.append({
            "subject_id": subject,
            "recording_id": recording_id,
            "date": recording_date,
            "metric": "heart_rate",
            "value": f"{median_hr:.1f}",
            "unit": "bpm",
            "source": "physionet_bidsleep",
            "provenance": provenance_json,
        })
        
        # Provenance for motion
        motion_prov["row_count"] = motion_count
        provenance_json = json.dumps(motion_prov, separators=(",", ":"))
        rows.append({
            "subject_id": subject,
            "recording_id": recording_id,
            "date": recording_date,
            "metric": "accel_magnitude_mean",
            "value": f"{mean_mag:.3f}",
            "unit": "g",
            "source": "physionet_bidsleep",
            "provenance": provenance_json,
        })
        
        all_provenance.append({
            "subject_id": subject,
            "recording_id": recording_id,
            "hr": hr_prov,
            "motion": motion_prov,
        })
        
        print(f"[{subject}/{night}] HR median {median_hr:.1f} bpm ({hr_count} samples), "
              f"accel mean {mean_mag:.3f} g ({motion_count} samples)")
    
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    
    # Provenance sidecar
    sidecar = path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps({
        "source": "PhysioNet bidsleep-dataset v1.0.0",
        "license": "Open Data Commons Attribution License v1.0",
        "doi": "10.13026/a0sy-7t69",
        "recordings": all_provenance,
        "note": "Instantaneous heart_rate from hr.csv + mean accel_magnitude_mean from motion.csv per night. "
                "HRV/sleep not available in this dataset. Subject identity preserved. "
                "accel_magnitude_mean is a raw sensor metric, not a clinical activity_load index.",
    }, indent=2), encoding="utf-8")
    
    print(f"Wrote {path} ({len(rows)} rows) and {sidecar}")
    return path


if __name__ == "__main__":
    import argparse as _arg
    parser = _arg.ArgumentParser()
    parser.add_argument("--nights", type=int, default=3)
    parser.add_argument("--out", default="data/public_real_bidsleep.csv")
    args = parser.parse_args()
    # Respect requested count but cap to the predefined list for determinism
    scrape(args.out, NIGHTS[:args.nights])
