"""Scrape PhysioNet Sepsis Challenge 2019 dataset for RIFT external validation.
~40,000 patients with sepsis outcome labels. Open access (CC BY 4.0).
"""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

BASE = "https://physionet.org/files/challenge-2019/1.0.0"
# Two training sets: training_setA (20,336), training_setB (20,000)
TRAINING_SETS = ["training_setA", "training_setB"]


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
    # Scheme allowlist: urllib supports file:// and custom schemes, so every
    # fetch target must be https under the fixed PhysioNet base.
    from urllib.parse import urlparse as _urlparse

    if _urlparse(url).scheme != "https" or not url.startswith(BASE):
        result["error"] = "refusing non-allowlisted fetch target"
        return result, text
    try:
        request = urllib.request.Request(url, headers={"Accept": "text/plain"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # nosec B310 - allowlisted above; nosemgrep -- fixed https base, validated inputs
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


def parse_psv(text: str) -> tuple[list[dict], list[str]]:
    """Parse pipe-separated values. Returns (rows, header)."""
    lines = text.strip().splitlines()
    if not lines:
        return [], []
    header = lines[0].split("|")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        rows.append(row)
    return rows, header


def scrape_patient(patient_id: str, training_set: str, max_hours: int = 24) -> list[dict] | None:
    """Fetch and parse one patient's time series."""
    url = f"{BASE}/training/{training_set}/{patient_id}.psv"
    prov, text = fetch_with_provenance(url)
    
    if not prov["success"]:
        return None
    
    rows, header = parse_psv(text)
    if not rows:
        return None
    
    # Limit to max_hours
    rows = rows[:max_hours]
    
    prov["row_count"] = len(rows)
    prov["patient_id"] = patient_id
    prov["training_set"] = training_set
    
    return [{
        "patient_data": rows,
        "header": header,
        "provenance": prov,
        "patient_id": patient_id,
        "training_set": training_set,
    }]


def scrape_sample(out_dir: str = "data/physionet_sepsis", 
                  training_set: str = "training_setA",
                  max_patients: int = 100,
                  max_hours: int = 24) -> Path:
    """Scrape a sample of the sepsis challenge dataset.
    
    Each row's SepsisLabel is preserved at its actual hour (no future leakage).
    Metrics use canonical names matching observations.METRICS.
    """
    path = Path(out_dir) / training_set
    path.mkdir(parents=True, exist_ok=True)
    
    # Get patient list (allowlisted fixed base; training_set is validated below).
    if training_set not in TRAINING_SETS:
        raise ValueError(f"unknown training set {training_set!r}")
    url = f"{BASE}/training/{training_set}/"
    resp = urllib.request.urlopen(url, timeout=30)  # nosec B310 - fixed base + validated set; nosemgrep -- fixed https base, validated set
    html = resp.read().decode('utf-8', errors='ignore')
    
    import re
    patient_files = re.findall(r'href="([^"]+\.psv)"', html)
    patient_ids = [f.replace('.psv', '') for f in patient_files[:max_patients]]
    
    print(f"Found {len(patient_ids)} patients in {training_set}, scraping {max_patients}...")
    
    all_rows = []
    all_provenance = []
    sepsis_counts = {0: 0, 1: 0}
    
    for i, patient_id in enumerate(patient_ids):
        result = scrape_patient(patient_id, training_set, max_hours)
        if result is None:
            continue
        
        data = result[0]
        rows = data["patient_data"]
        prov = data["provenance"]
        
        if not rows:
            continue
        
        # Map PhysioNet fields to canonical metric names
        vital_map = {
            "HR": ("heart_rate", "bpm"),
            "O2Sat": ("spo2", "%"),
            "Temp": ("temperature", "C"),
            "SBP": ("sbp", "mmHg"),
            "MAP": ("map", "mmHg"),
            "DBP": ("dbp", "mmHg"),
            "Resp": ("resp_rate", "breaths/min"),
            "ICULOS": ("icu_los_hours", "hours"),
        }
        
        for hour_idx, row in enumerate(rows):
            rec_id = f"{patient_id}_icu_h{hour_idx}"
            # Strict ICULOS: invalid/missing ICU time rejects the row (no fabricated time).
            iculos_val = row.get("ICULOS", "NaN")
            try:
                iculos_hours = float(iculos_val)
                if not (iculos_hours == iculos_hours and abs(iculos_hours) < 1e6):  # finite check
                    raise ValueError(f"non-finite ICULOS {iculos_val!r}")
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"patient {patient_id} hour {hour_idx}: invalid/missing ICULOS {iculos_val!r}; "
                    f"refusing to manufacture time ({exc})"
                )
            
            # For date field, use a synthetic study start date + ICULOS hours
            # This preserves relative time while avoiding fabricated calendar dates
            # Use a study epoch (e.g., 2024-01-01) + ICULOS hours
            from datetime import datetime, timedelta, timezone
            study_epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
            dt = study_epoch + timedelta(hours=iculos_hours)
            date_str = dt.isoformat()
            
            # Vital signs - use each row's actual values
            for vital, (metric, unit) in vital_map.items():
                val = row.get(vital, "NaN")
                if val != "NaN" and val != "":
                    try:
                        fval = float(val)
                        all_rows.append({
                            "subject_id": patient_id,
                            "recording_id": rec_id,
                            "date": date_str,
                            "metric": metric,
                            "value": f"{fval:.3f}",
                            "unit": unit,
                            "source": f"physionet_sepsis_challenge2019_{training_set}",
                            "provenance": json.dumps(prov, separators=(",", ":")),
                        })
                    except ValueError:
                        pass
            
            # Sepsis label - use EACH ROW'S actual label (no future leakage)
            sepsis_label = row.get("SepsisLabel", "NaN")
            if sepsis_label != "NaN":
                try:
                    sepsis_counts[int(float(sepsis_label))] += 1
                except (ValueError, TypeError):
                    pass
                
                all_rows.append({
                    "subject_id": patient_id,
                    "recording_id": rec_id,
                    "date": date_str,
                    "metric": "sepsis_label",
                    "value": sepsis_label,
                    "unit": "binary",
                    "source": f"physionet_sepsis_challenge2019_{training_set}",
                    "provenance": json.dumps(prov, separators=(",", ":")),
                })
        
        all_provenance.append(prov)
        
        if (i + 1) % 20 == 0:
            print(f"  Processed {i+1}/{max_patients} patients...")
    
    print(f"Sepsis distribution: {sepsis_counts}")

    # Fail closed on incomplete cohort: requested vs succeeded must match.
    if len(all_provenance) != len(patient_ids):
        raise RuntimeError(
            f"incomplete cohort extraction: requested {len(patient_ids)} patients, "
            f"succeeded {len(all_provenance)} in {training_set}; "
            f"refusing to write partial validation cohort"
        )

    # Write CSV
    fieldnames = ["subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"]
    csv_path = path / f"sepsis_challenge2019_{training_set}_sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    
    # Provenance sidecar
    sidecar = csv_path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps({
        "source": f"PhysioNet Sepsis Prediction Challenge 2019 v1.0.0",
        "license": "Creative Commons Attribution 4.0",
        "training_set": training_set,
        "patients_scraped": len(all_provenance),
        "sepsis_distribution": sepsis_counts,
        "note": f"Sample of {max_patients} patients, {max_hours} hours each. "
                f"Each row's SepsisLabel preserved at its actual hour (no future leakage). "
                f"Metrics use canonical names. CC BY 4.0 license.",
    }, indent=2), encoding="utf-8")
    
    print(f"Wrote {csv_path} ({len(all_rows)} rows) and {sidecar}")
    return csv_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=TRAINING_SETS, default="training_setA")
    parser.add_argument("--patients", type=int, default=50)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--out", default="data/physionet_sepsis")
    args = parser.parse_args()
    scrape_sample(args.out, args.set, args.patients, args.hours)