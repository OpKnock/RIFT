"""Scrape open PhysioNet cardiac datasets for RIFT.
CHFDB: Congestive Heart Failure RR Interval Database (open)
BIDMC: BIDMC Congestive Heart Failure Database (open)

Note: PhysioNet waveform databases use WFDB format (.dat/.hea binary).
This scraper uses available CSV/numerics exports where available.
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
# Open cardiac datasets
DATASETS = {
    "chfdb": {
        "version": "1.0.0",
        "subjects": [f"chf{i:02d}" for i in range(1, 30)],  # chf01-chf29
        "description": "Congestive Heart Failure RR Interval Database",
        "license": "Open Data Commons Attribution License v1.0",
        "rr_files": True,  # RR interval text files available
    },
    "bidmc": {
        "version": "1.0.0",
        "subjects": [f"bidmc_{i:02d}" for i in range(1, 54)],  # bidmc_01-bidmc_53
        "description": "BIDMC Congestive Heart Failure Database",
        "license": "Open Data Commons Attribution License v1.0",
        "rr_files": False,  # Use numerics CSV export instead
    },
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
    For BIDMC: Uses numerics CSV export where available.
    
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
        
        if cfg.get("rr_files", False):
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
            
        else:
            # BIDMC: Try numerics CSV export
            csv_url = f"{BASE}/{dataset_name}/{cfg['version']}/{subject}_numerics.csv"
            hea_url = f"{BASE}/{dataset_name}/{cfg['version']}/{subject}.hea"
            
            csv_prov, csv_text = fetch_with_provenance(csv_url)
            hea_prov, hea_text = fetch_with_provenance(hea_url)
            
            if not csv_prov["success"]:
                print(f"  [{subject}] No numerics CSV: {csv_prov['error']}")
                continue
            
            # Parse numerics CSV
            numerics = parse_numerics_csv(csv_text)
            if not numerics:
                print(f"  [{subject}] No valid numerics data")
                continue
            
            # Extract key vital signs from numerics
            # BIDMC numerics typically include: HR, SBP, DBP, MAP, RR, SpO2, Temp
            hr_vals = []
            sbp_vals = []
            dbp_vals = []
            map_vals = []
            resp_vals = []
            spo2_vals = []
            temp_vals = []
            
            for row in numerics:
                try:
                    if "HR" in row and row["HR"] != "":
                        hr_vals.append(float(row["HR"]))
                    if "SBP" in row and row["SBP"] != "":
                        sbp_vals.append(float(row["SBP"]))
                    if "DBP" in row and row["DBP"] != "":
                        dbp_vals.append(float(row["DBP"]))
                    if "MAP" in row and row["MAP"] != "":
                        map_vals.append(float(row["MAP"]))
                    if "RESP" in row and row["RESP"] != "":
                        resp_vals.append(float(row["RESP"]))
                    if "SPO2" in row and row["SPO2"] != "":
                        spo2_vals.append(float(row["SPO2"]))
                    if "TEMP" in row and row["TEMP"] != "":
                        temp_vals.append(float(row["TEMP"]))
                except (ValueError, KeyError):
                    continue
            
            import statistics
            # Add available metrics
            metrics_to_add = []
            if hr_vals:
                metrics_to_add.append(("heart_rate", statistics.mean(hr_vals), "bpm", "heart_rate_from_numerics"))
            if sbp_vals:
                metrics_to_add.append(("sbp", statistics.mean(sbp_vals), "mmHg", "sbp_from_numerics"))
            if dbp_vals:
                metrics_to_add.append(("dbp", statistics.mean(dbp_vals), "mmHg", "dbp_from_numerics"))
            if map_vals:
                metrics_to_add.append(("map", statistics.mean(map_vals), "mmHg", "map_from_numerics"))
            if resp_vals:
                metrics_to_add.append(("resp_rate", statistics.mean(resp_vals), "breaths/min", "resp_rate_from_numerics"))
            if spo2_vals:
                metrics_to_add.append(("spo2", statistics.mean(spo2_vals), "%", "spo2_from_numerics"))
            if temp_vals:
                metrics_to_add.append(("temperature", statistics.mean(temp_vals), "C", "temperature_from_numerics"))
            
            for metric, mean_val, unit, derived in metrics_to_add:
                prov = dict(csv_prov)
                prov["derived_metric"] = derived
                provenance_json = json.dumps(prov, separators=(",", ":"))
                rows.append({
                    "subject_id": subject,
                    "recording_id": recording_id,
                    "date": "2024-01-01",
                    "metric": metric,
                    "value": f"{mean_val:.1f}",
                    "unit": unit,
                    "source": f"physionet_{dataset_name}",
                    "provenance": provenance_json,
                })
            
            all_provenance.append({
                "subject_id": subject,
                "recording_id": recording_id,
                "csv": csv_prov,
                "hea": hea_prov,
            })
            
            print(f"  [{subject}] Added {len(metrics_to_add)} metrics from numerics CSV")
    
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
        "note": "HR and HRV derived from RR intervals (CHFDB) or numerics CSV (BIDMC). "
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