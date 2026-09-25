"""Scrape open PhysioNet cardiac datasets for RIFT.

CHFDB: BIDMC Congestive Heart Failure Database (``chfdb``), 15 subjects
``chf01``–``chf15``. Official layout per recording is WFDB
``chfXX.dat`` + ``chfXX.hea`` (+ ``chfXX.ecg`` beat annotations).
There are NO official ``chfXX.txt`` RR files — a previous revision of this
adapter incorrectly attempted ``.txt`` URLs.

This adapter consumes the real WFDB representation via the validated
``wfdb`` package (``pip install -e .[physio]``). RR intervals are derived
from beat-annotation sample numbers and the header sampling frequency,
never from fabricated text parsing of binary ``.dat`` waveforms.

Note: the 53-subject ``bidmc_##`` collection is the BIDMC PPG and
Respiration Dataset, NOT a CHF database — it is deliberately excluded
here to avoid dataset conflation. ``chf2db`` (29 records) is a different
dataset from ``chfdb`` (15 records).
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

BASE = "https://physionet.org/files"
DATASETS = {
    "chfdb": {
        "version": "1.0.0",
        "subjects": [f"chf{i:02d}" for i in range(1, 16)],  # chf01-chf15 (15 subjects)
        "description": "BIDMC Congestive Heart Failure Database",
        "license": "Open Data Commons Attribution License v1.0",
        "annotation_ext": "ecg",  # official CHFDB beat annotations: chfXX.ecg (not .atr)
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


def fetch_bytes_with_provenance(url: str, timeout: int = 60) -> tuple[FetchResult, bytes]:
    result: FetchResult = {
        "success": False,
        "url": url,
        "http_status": None,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": None,
        "row_count": 0,
        "error": None,
    }
    data = b""
    # Scheme allowlist: urllib supports file:// and custom schemes, so every
    # fetch target must be https under the fixed PhysioNet base.
    from urllib.parse import urlparse as _urlparse

    if _urlparse(url).scheme != "https" or not url.startswith(BASE):
        result["error"] = "refusing non-allowlisted fetch target"
        return result, data
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # nosec B310 - allowlisted above; nosemgrep -- fixed https base, validated inputs
            result["http_status"] = resp.getcode()
            data = resp.read()
            result["content_sha256"] = hashlib.sha256(data).hexdigest()
            result["success"] = True
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["error"] = f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        result["error"] = f"URL error: {exc.reason}"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result, data


def fetch_text_with_provenance(url: str, timeout: int = 60) -> tuple[FetchResult, str]:
    prov, data = fetch_bytes_with_provenance(url, timeout=timeout)
    return prov, data.decode(errors="replace")


def chfdb_urls(subject: str, version: str = "1.0.0", annotation_ext: str = "ecg") -> dict[str, str]:
    """Return the official WFDB file URLs for one CHFDB recording."""
    base = f"{BASE}/chfdb/{version}/{subject}"
    return {
        "dat": f"{base}.dat",
        "hea": f"{base}.hea",
        "ann": f"{base}.{annotation_ext}",
    }


def parse_hea_sampfreq(hea_text: str) -> float:
    """Parse sampling frequency from a WFDB .hea header first line.

    First line format: ``record nsig sampfreq nsamples ...``.
    Raises ValueError on unparseable headers (fail-closed).
    """
    lines = [ln.strip() for ln in hea_text.splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines:
        raise ValueError("empty .hea header")
    parts = lines[0].split()
    if len(parts) < 3:
        raise ValueError(f"unparseable .hea first line: {lines[0]!r}")
    try:
        fs = float(parts[2])
    except ValueError as exc:
        raise ValueError(f"unparseable sampling frequency in .hea: {lines[0]!r}") from exc
    if not fs > 0:
        raise ValueError(f"non-positive sampling frequency: {fs}")
    return fs


def annotation_samples_to_rr_ms(sample_numbers: list[int], sampfreq_hz: float) -> list[float]:
    """Convert beat-annotation sample numbers to RR intervals in ms."""
    if not sampfreq_hz > 0:
        raise ValueError("sampling frequency must be positive")
    rr: list[float] = []
    for a, b in zip(sample_numbers, sample_numbers[1:]):
        delta = b - a
        if delta <= 0:
            continue
        ms = delta / sampfreq_hz * 1000.0
        if 200.0 < ms < 2000.0:  # physiological RR range
            rr.append(ms)
    return rr


def rr_to_hr_hrv(rr_ms: list[float]) -> tuple[float, float]:
    """Mean HR (bpm) and RMSSD (ms) from RR intervals. Raises on empty input."""
    if not rr_ms:
        raise ValueError("no valid RR intervals")
    mean_rr = statistics.mean(rr_ms)
    mean_hr = 60000.0 / mean_rr
    if len(rr_ms) > 1:
        diffs = [rr_ms[i + 1] - rr_ms[i] for i in range(len(rr_ms) - 1)]
        rmssd = (statistics.mean(d * d for d in diffs)) ** 0.5
    else:
        rmssd = 0.0
    return float(mean_hr), float(rmssd)


def read_annotation_samples_wfdb(record_path: str, annotation_ext: str = "ecg") -> list[int]:
    """Read beat-annotation sample numbers via the validated ``wfdb`` package.

    Raises RuntimeError with install guidance when ``wfdb`` is missing —
    we do not hand-roll binary WFDB annotation parsing for clinical data.
    """
    try:
        import wfdb  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "WFDB parsing requires the validated 'wfdb' package: "
            "pip install -e '.[physio]' (wfdb>=4.1). "
            "Refusing to guess binary .dat/.ecg contents."
        ) from exc
    ann = wfdb.rdann(record_path, annotation_ext)
    return [int(s) for s in ann.sample]


def scrape_dataset(dataset_name: str = "chfdb", out_dir: str = "data/physionet_cardiac",
                   download: bool = True) -> Path:
    """Scrape CHFDB with full provenance via real WFDB files.

    When ``download=False``, only validates dataset definitions without
    network access (used by CI/offline tests).
    """
    cfg = DATASETS[dataset_name]
    path = Path(out_dir) / dataset_name
    path.mkdir(parents=True, exist_ok=True)

    if not download:
        return path

    fieldnames = ["subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"]
    rows: list[dict] = []
    all_provenance: list[dict] = []

    for subject in cfg["subjects"]:
        recording_id = f"{dataset_name}_{subject}"
        urls = chfdb_urls(subject, cfg["version"], cfg.get("annotation_ext", "ecg"))

        hea_prov, hea_text = fetch_text_with_provenance(urls["hea"])
        if not hea_prov["success"]:
            print(f"  [{subject}] No .hea: {hea_prov['error']}")
            continue
        try:
            fs = parse_hea_sampfreq(hea_text)
        except ValueError as exc:
            print(f"  [{subject}] Bad .hea: {exc}")
            continue

        # Fetch .dat for provenance (waveform bytes are not text-parsed).
        dat_prov, _ = fetch_bytes_with_provenance(urls["dat"])
        if not dat_prov["success"]:
            print(f"  [{subject}] No .dat: {dat_prov['error']}")
            continue

        # Beat annotations via validated wfdb library.
        try:
            import tempfile
            import os

            # wfdb.rdann works on local record paths; download .ecg to temp dir.
            ann_prov, ann_bytes = fetch_bytes_with_provenance(urls["ann"])
            if not ann_prov["success"]:
                print(f"  [{subject}] No .{cfg.get('annotation_ext', 'ecg')}: {ann_prov['error']}")
                continue
            with tempfile.TemporaryDirectory() as tmp:
                # wfdb needs matching .hea + annotation file locally.
                for ext, payload, prov in (("hea", hea_text.encode(), hea_prov),
                                           (cfg.get("annotation_ext", "ecg"), ann_bytes, ann_prov)):
                    with open(os.path.join(tmp, f"{subject}.{ext}"), "wb") as fh:
                        fh.write(payload)
                samples = read_annotation_samples_wfdb(os.path.join(tmp, subject),
                                                       cfg.get("annotation_ext", "ecg"))
        except RuntimeError as exc:
            raise RuntimeError(f"  [{subject}] {exc}") from exc

        rr = annotation_samples_to_rr_ms(samples, fs)
        if not rr:
            print(f"  [{subject}] No valid RR intervals from annotations")
            continue
        mean_hr, rmssd = rr_to_hr_hrv(rr)

        base_prov = {
            "hea_sha256": hea_prov["content_sha256"],
            "dat_sha256": dat_prov["content_sha256"],
            "ann_sha256": ann_prov["content_sha256"],
            "sampfreq_hz": fs,
            "n_beats": len(samples),
            "n_rr": len(rr),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
        for metric, val, unit, derived in (
            ("heart_rate", mean_hr, "bpm", "heart_rate_from_wfdb_ann"),
            ("hrv_rmssd", rmssd, "ms", "hrv_rmssd_from_wfdb_ann"),
        ):
            prov = dict(base_prov)
            prov.update({"url_hea": urls["hea"], "url_dat": urls["dat"],
                         "url_ann": urls["ann"], "derived_metric": derived})
            rows.append({
                "subject_id": subject,
                "recording_id": recording_id,
                "date": "2024-01-01",
                "metric": metric,
                "value": f"{val:.3f}",
                "unit": unit,
                "source": f"physionet_{dataset_name}",
                "provenance": json.dumps(prov, separators=(",", ":")),
            })
        all_provenance.append({"subject_id": subject, "recording_id": recording_id,
                               "hea": hea_prov, "dat": dat_prov, "ann": ann_prov})
        print(f"  [{subject}] HR {mean_hr:.1f} bpm, HRV {rmssd:.1f} ms ({len(rr)} RR)")

    # Fail closed on incomplete cohort: requested vs succeeded must match.
    if len(all_provenance) != len(cfg["subjects"]):
        raise RuntimeError(
            f"incomplete cardiac extraction: requested {len(cfg['subjects'])} subjects, "
            f"succeeded {len(all_provenance)} in {dataset_name}; "
            f"refusing to write partial validation cohort"
        )

    csv_path = path / f"{dataset_name}_cardiac.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    sidecar = csv_path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps({
        "source": f"PhysioNet {cfg['description']} v{cfg['version']}",
        "license": cfg["license"],
        "dataset": dataset_name,
        "recordings": all_provenance,
        "note": "HR/HRV derived from WFDB beat annotations + header sampling "
                "frequency via the validated wfdb package. No .txt RR files used.",
    }, indent=2), encoding="utf-8")

    print(f"Wrote {csv_path} ({len(rows)} rows) and {sidecar}")
    return csv_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default="chfdb")
    parser.add_argument("--out", default="data/physionet_cardiac")
    parser.add_argument("--no-download", action="store_true",
                        help="validate definitions only, no network")
    args = parser.parse_args()
    scrape_dataset(args.dataset, args.out, download=not args.no_download)
