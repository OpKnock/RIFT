"""Quick scrape: S1, midterm_1, SMALL files only (skip ACC, BVP)."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://physionet.org/files/wearable-exam-stress/1.0.0"
# Skip ACC (3.4MB) and BVP (likely large) - use small files only
MODALITIES = ["HR", "IBI", "EDA", "TEMP"]
UNITS = {"HR": "bpm", "IBI": "ms", "EDA": "µS", "TEMP": "°C"}
CANONICAL_METRICS = {"HR": "heart_rate", "IBI": "rr_sd", "EDA": "eda", "TEMP": "skin_temp"}


def fetch(url: str) -> tuple[bool, str, dict]:
    prov = {"url": url, "success": False, "error": None, "sha256": None, "rows": 0}
    try:
        req = urllib.request.Request(url, headers={"Accept": "text/csv"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
            prov["sha256"] = hashlib.sha256(content).hexdigest()
            text = content.decode(errors="replace")
            prov["success"] = True
            return True, text, prov
    except Exception as e:
        prov["error"] = str(e)
        return False, "", prov


def parse_mean(text: str) -> tuple[float | None, int]:
    lines = text.strip().splitlines()
    if not lines:
        return None, 0
    values = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        try:
            parts = line.split(',')
            val = float(parts[0])
            values.append(val)
        except (ValueError, IndexError):
            continue
    if not values:
        return None, 0
    return statistics.mean(values), len(values)


def main():
    path = Path("data/wearable_exam_stress")
    path.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ["subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"]
    rows = []
    all_prov = []
    
    subject = "S1"
    exam = "midterm_1"
    rec_id = f"{subject}_{exam}"
    date = "2024-01-01"
    
    for mod in MODALITIES:
        url = f"{BASE}/data/{subject}/{exam}/{mod}.csv"
        print(f"Fetching {mod}...")
        ok, text, prov = fetch(url)
        
        if not ok:
            print(f"  [{rec_id}/{mod}] FAIL: {prov['error']}")
            continue
        
        mean_val, count = parse_mean(text)
        if mean_val is None:
            print(f"  [{rec_id}/{mod}] No data")
            continue
        
        prov["rows"] = count
        prov["modality"] = mod
        prov_json = json.dumps(prov, separators=(",", ":"))
        
        rows.append({
            "subject_id": subject,
            "recording_id": rec_id,
            "date": date,
            "metric": CANONICAL_METRICS[mod],
            "value": f"{mean_val:.3f}",
            "unit": UNITS.get(mod, ""),
            "source": "physionet_wearable_exam_stress",
            "provenance": prov_json,
        })
        all_prov.append({"subject": subject, "exam": exam, "modality": mod, "prov": prov})
        print(f"  [{rec_id}/{mod}] mean={mean_val:.3f} {UNITS.get(mod,'')} ({count} samples)")
    
    csv_path = path / "wearable_exam_stress_S1_midterm1_small.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    
    sidecar = csv_path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps({
        "source": "PhysioNet Wearable Exam Stress v1.0.0",
        "license": "ODC Attribution v1.0",
        "subjects": ["S1"],
        "recordings": all_prov,
        "note": "Small modalities only (HR, IBI, EDA, TEMP). Skipped ACC/BVP (large). Subject identity preserved. No clinical outcomes.",
    }, indent=2))
    
    print(f"Done: {csv_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()