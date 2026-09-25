"""Scrape wearable-exam-stress dataset (open access).
9 subjects, 3 exam periods each, multiple wearable modalities.
"""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

BASE = "https://physionet.org/files/wearable-exam-stress/1.0.0"
# Official dataset describes 10 participants; S10 is included but a missing
# directory fails closed per-recording (see strict mode below) instead of
# silently producing a smaller cohort.
SUBJECTS = [f"S{i}" for i in range(1, 11)]  # S1-S10
EXAMS = ["midterm_1", "midterm_2", "Final"]
# Distinct nominal dates per exam so sessions never collapse into one bucket.
# The source date-shifts timestamps but preserves time-of-day; we preserve
# session identity explicitly via recording_id + date.
EXAM_DATES = {"midterm_1": "2024-01-01", "midterm_2": "2024-02-01", "Final": "2024-03-01"}
MODALITIES = ["ACC", "BVP", "EDA", "HR", "IBI", "TEMP"]


class FetchResult(TypedDict):
    success: bool
    url: str
    http_status: int | None
    retrieved_at: str
    content_sha256: str | None
    row_count: int
    error: str | None


def fetch_with_provenance(url: str, timeout: int = 30) -> tuple[FetchResult, str]:
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
        request = urllib.request.Request(url, headers={"Accept": "text/csv"})
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


def parse_csv_metric(text: str, metric: str) -> tuple[float | None, int]:
    """Parse a CSV and return (mean_value, row_count) for the metric column."""
    lines = text.strip().splitlines()
    if not lines:
        return None, 0
    
    # Skip header
    reader = csv.reader(lines[1:])
    values = []
    for row in reader:
        if not row:
            continue
        try:
            # Assume first column is timestamp, second is value
            # or single column of values
            if len(row) >= 2:
                val = float(row[1])
            else:
                val = float(row[0])
            values.append(val)
        except (ValueError, IndexError):
            continue
    
    if not values:
        return None, 0
    
    import statistics
    return statistics.mean(values), len(values)


def scrape(out_dir: str = "data/wearable_exam_stress") -> Path:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ["subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"]
    rows = []
    all_provenance = []
    
    units = {
        "ACC": "g",
        "BVP": "a.u.",
        "EDA": "µS",
        "HR": "bpm",
        "IBI": "ms",
        "TEMP": "°C",
    }

    # Canonical metric names per observations.METRICS. ACC/BVP have no
    # validated canonical mapping and are skipped so output always loads
    # via PublicDatasetSource (fail-closed downstream would reject them).
    # IBI mean is NOT RR SD / RMSSD — it is stored as explicit ibi_mean.
    CANONICAL_MAP = {
        "EDA": "eda",
        "HR": "heart_rate",
        "IBI": "ibi_mean",
        "TEMP": "skin_temp",
    }
    
    strict_missing: list[str] = []

    for subject in SUBJECTS:
        for exam in EXAMS:
            recording_id = f"{subject}_{exam}"
            recording_date = EXAM_DATES[exam]
            
            succeeded_here: set[str] = set()
            for modality in MODALITIES:
                url = f"{BASE}/data/{subject}/{exam}/{modality}.csv"
                prov, text = fetch_with_provenance(url)

                if modality not in CANONICAL_MAP:
                    print(f"  [{recording_id}/{modality}] skipped: no canonical metric (would fail validation)")
                    continue

                if not prov["success"]:
                    print(f"  [{recording_id}/{modality}] Failed: {prov['error']}")
                    strict_missing.append(f"{recording_id}/{modality}: {prov['error']}")
                    continue

                mean_val, count = parse_csv_metric(text, modality)
                if mean_val is None:
                    print(f"  [{recording_id}/{modality}] No valid data")
                    strict_missing.append(f"{recording_id}/{modality}: no valid data")
                    continue
                succeeded_here.add(modality)

                prov["row_count"] = count
                prov["modality"] = modality
                prov["canonical_metric"] = CANONICAL_MAP[modality]
                provenance_json = json.dumps(prov, separators=(",", ":"))

                rows.append({
                    "subject_id": subject,
                    "recording_id": recording_id,
                    "date": recording_date,
                    "metric": CANONICAL_MAP[modality],
                    "value": f"{mean_val:.3f}",
                    "unit": units.get(modality, ""),
                    "source": "physionet_wearable_exam_stress",
                    "provenance": provenance_json,
                })
                
                all_provenance.append({
                    "subject_id": subject,
                    "recording_id": recording_id,
                    "modality": modality,
                    "provenance": prov,
                })
                
                print(f"  [{recording_id}/{modality}] mean={mean_val:.3f} {units.get(modality, '')} ({count} samples)")

            missing_required = [m for m in CANONICAL_MAP if m not in succeeded_here]
            if missing_required:
                strict_missing.append(f"{recording_id}: missing required modalities {missing_required}")

    if strict_missing:
        raise RuntimeError(
            "incomplete exam-stress extraction: "
            + "; ".join(strict_missing)
            + " — refusing to write partial validation cohort"
        )

    # Write CSV
    csv_path = path / "wearable_exam_stress.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    
    # Provenance sidecar
    sidecar = csv_path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps({
        "source": "PhysioNet Wearable Exam Stress Dataset v1.0.0",
        "license": "Open Data Commons Attribution License v1.0",
        "subjects": SUBJECTS,
        "exams": EXAMS,
        "modalities": MODALITIES,
        "recordings": all_provenance,
        "note": "Mean values per modality per exam period. Subject identity preserved. No clinical outcomes.",
    }, indent=2), encoding="utf-8")
    
    print(f"Wrote {csv_path} ({len(rows)} rows) and {sidecar}")
    return csv_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/wearable_exam_stress")
    args = parser.parse_args()
    scrape(args.out)