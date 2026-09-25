"""Scrape open PhysioNet cardiac datasets for RIFT.
CHFDB: Congestive Heart Failure RR Interval Database (open) - 15 subjects
BIDMC CHF: BIDMC Congestive Heart Failure Database (open) - same as CHFDB
Note: The 53-subject BIDMC dataset is the PPG/Respiration dataset, not CHF.

Note: PhysioNet waveform databases use WFDB format (.dat/.hea binary).
This scraper uses available RR interval text files (.txt) where available.
For full waveform access, use wfdb-python library with WFDB format.
"""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

BASE = "https://physionet.org/files"
# Open cardiac datasets - corrected based on PhysioNet documentation
DATASETS = {
    "chfdb": {
        "version": "1.0.0",
        "subjects": [f"chf{i:02d}" for i in range(1, 16)],  # chf01-chf15 (15 subjects)
        "description": "Congestive Heart Failure RR Interval Database",
        "license": "Open Data Commons Attribution License v1.0",
        "rr_files": True,  # RR interval text files available (.txt)
    },
    # Note: The 53-subject BIDMC dataset (bidmc_01-bidmc_53) is the 
    # BIDMC PPG and Respiration Dataset, NOT a CHF database.
    # It is excluded here to avoid dataset conflation.
}


class FetchResult(TypedDict):
    success: bool
    url: str
    http_status: int | None
    retrieved_at: str
    content_sha256: str | None
    row_count: int
    error: str | None


def fetch_with_provenance(url: str, timeout: int = 60) -> tuple[FetchResult, str]:
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
    try:
        request = urllib.request.Request(url, headers={"Accept": "text/plain"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # nosec B310 - fixed PhysioNet URLs
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
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result, text


def parse_rr_intervals(text: str) -> list[float]:
    """Parse RR intervals from text format (ms between beats)."""
    intervals = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            val = float(line.split()[0])
            if 200 < val < 2000:  # Physiological RR range (300-2000ms)
                intervals.append(val)
        except (ValueError, IndexError):
            continue
    return intervals


def parse_numerics_csv(text: str) -> list[dict]:
    """Parse numerics CSV export from PhysioNet."""
    lines = text.strip().splitlines()
    if not lines:
        return []
    # Skip header, parse as CSV
    import csv
    reader = csv.DictReader(lines)
    rows = []
    for row in reader:
        rows.append(row)
    return rows


def scrape_dataset(dataset_name: str, out_dir: str = "data/physionet_cardiac") -> Path:
    """Scrape an open cardiac dataset with full provenance.
    
    For CHFDB: Uses RR interval text files (.txt) where available.
    
    Note: Full waveform access requires wfdb-python library with WFDB format (.dat/.hea).
    """
    cfg = DATASETS[dataset_name]
    path = Path(out_dir) / dataset_name
    path.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ["subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"]
    rows = []
    all_provenance = []
    
    for subject in cfg["subjects"]:
        recording_id = f"{dataset_name}_{subject}"
        recording_date = "2024-01-01"
        
        # CHFDB: RR interval text files
        rr_url = f"{BASE}/{dataset_name}/{cfg['version']}/{subject}.txt"
        hea_url = f"{BASE}/{dataset_name}/{cfg['version']}/{subject}.hea"
        
        rr_prov, rr_text = fetch_with_provenance(rr_url)
        hea_prov, hea_text = fetch_with_provenance(hea_url)
        
        if not rr_prov["success"]:
            print(f"  [{subject}] No RR text file: {rr_prov['error']}")
            continue
            
        # Parse RR intervals
        rr_intervals = parse_rr_intervals(rr_text)
        if not rr_intervals:
            print(f"  [{subject}] No valid RR intervals")
            continue
        
        # Compute HRV metrics from RR intervals
        import statistics
        mean_rr = statistics.mean(rr_intervals)
        mean_hr = 60000 / mean_rr  # bpm
        rmssd = 0.0
        if len(rr_intervals) > 1:
            diffs = [rr_intervals[i+1] - rr_intervals[i] for i in range(len(rr_intervals)-1)]
            rmssd = (statistics.mean(d*d for d in diffs)) ** 0.5
        
        # Provenance for HR
        hr_prov = dict(rr_prov)
        hr_prov["row_count"] = len(rr_intervals)
        hr_prov["derived_metric"] = "heart_rate_from_rr"
        provenance_json = json.dumps(hr_prov, separators=(",", ":"))
        rows.append({
            "subject_id": subject,
            "recording_id": recording_id,
            "date": "2024-01-01",
            "metric": "heart_rate",
            "value": f"{mean_hr:.1f}",
            "unit": "bpm",
            "source": f"physionet_{dataset_name}",
            "provenance": provenance_json,
        })
        
        # Provenance for HRV
        hrv_prov = dict(rr_prov)
        hrv_prov["row_count"] = len(rr_intervals)
        hrv_prov["derived_metric"] = "hrv_rmssd_from_rr"
        provenance_json = json.dumps(hrv_prov, separators=(",", ":"))
        rows.append({
            "subject_id": subject,
            "recording_id": recording_id,
            "date": "2024-01-01",
            "metric": "hrv_rmssd",
            "value": f"{rmssd:.1f}",
            "unit": "ms",
            "source": f"physionet_{dataset_name}",
            "provenance": provenance_json,
        })
        
        all_provenance.append({
            "subject_id": subject,
            "recording_id": recording_id,
            "rr": rr_prov,
            "hea": hea_prov,
        })
        
        print(f"  [{subject}] HR {mean_hr:.1f} bpm, HRV {rmssd:.1f} ms ({len(rr_intervals)} RR intervals)")
    
    # Write CSV
    csv_path = path / f"{dataset_name}_cardiac.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    
    # Provenance sidecar
    sidecar = csv_path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps({
        "source": f"PhysioNet {cfg['description']} v{cfg['version']}",
        "license": cfg["license"],
        "dataset": dataset_name,
        "recordings": all_provenance,
        "note": "HR and HRV derived from RR intervals (CHFDB). "
                "No clinical outcomes available. "
                "For full waveform access, use wfdb-python with WFDB format (.dat/.hea).",
    }, indent=2), encoding="utf-8")
    
    print(f"Wrote {csv_path} ({len(rows)} rows) and {sidecar}")
    return csv_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default="chfdb")
    parser.add_argument("--out", default="data/physionet_cardiac")
    args = parser.parse_args()
    scrape_dataset(args.dataset, args.out)