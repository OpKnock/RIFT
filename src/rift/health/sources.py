"""Wearable data sources: replay today, live ingestion tomorrow.

The twin only depends on the WearableSource interface, so the demo replay,
a public-dataset CSV, and a future live IoT adapter feed the SAME
normalized pipeline:

    WearableSource (interface: history + freshness queries)
    ├── ReplaySource  — fixed historical list (this demo)
    ├── PublicDatasetSource — CSV file with a documented schema
    └── LiveIngestSource — append-only live observations (future adapter)

No Bluetooth/hardware is implemented; LiveIngestSource is the seam where a
live adapter plugs in without touching twin, risk, or Guardian code.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from .models import WearableObservation
from .observations import normalize_batch, CanonicalObservation
from .wearable import FIELDS, WearableStream


class WearableSource(WearableStream):
    """Interface marker: anything the twin can synchronize from.

    Subclasses must provide: observations_upto, latest_at, stale_days_at,
    completeness_at, start_day, end_day. WearableStream already implements
    all of them for replay; see LiveIngestSource for ingestion.
    """


class ReplaySource(WearableSource):
    """Named alias documenting demo intent: fixed history, replayed by day."""


class LiveIngestSource(WearableSource):
    """Append-only buffer for live observations. Same queries, live writes.

    Accepts observations in non-decreasing day order; duplicates and
    time-travel are rejected so replay semantics (monotone history) hold.
    """

    def __init__(self):
        self._obs: list[WearableObservation] = []

    def ingest(self, observation: WearableObservation) -> WearableObservation:
        if not isinstance(observation, WearableObservation):
            raise ValueError("ingest requires a WearableObservation")
        if self._obs and observation.day_index < self._obs[-1].day_index:
            raise ValueError("observations must arrive in non-decreasing day order")
        if self._obs and observation.day_index == self._obs[-1].day_index:
            raise ValueError("duplicate day_index: one observation per day")
        self._obs.append(observation)
        return observation

    @property
    def buffered_days(self) -> int:
        return len(self._obs)


# Legacy schema for backward compatibility (day_index + FIELDS)
LEGACY_CSV_SCHEMA = ("day_index",) + FIELDS

# New provenance-rich schema (one row per metric per recording)
PUBLIC_DATASET_CSV_SCHEMA = (
    "subject_id", "recording_id", "date", "metric", "value", "unit", "source", "provenance"
)


def _parse_iso_date(text: str) -> int:
    """Parse ISO date string and return days since epoch for day_index.

    For demo purposes, we use a simple mapping. In production, this would
    use a proper study timeline.
    """
    try:
        # Parse as YYYY-MM-DD
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Use days since 2024-01-01 as day_index for demo
        epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return (dt - epoch).days
    except ValueError:
        # Fallback: hash the date string to a deterministic day_index
        # Not for security; usedforsecurity=False suppresses Bandit B324
        import hashlib
        return int(hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16) % 10000


def _canonical_to_wearable(observations: list[CanonicalObservation]) -> list[WearableObservation]:
    """Convert canonical observations to WearableObservation grouped by day.
    
    Maps canonical metrics to wearable fields with explicit provenance tracking.
    """
    # Group by day_index (derived from timestamp)
    by_day: dict[int, dict] = {}
    for obs in observations:
        # Derive day_index from timestamp
        try:
            dt = datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
            day_index = (dt - epoch).days
        except ValueError:
            # Fallback: use a hash-based day_index
            # Not for security; usedforsecurity=False suppresses Bandit B324
            import hashlib
            day_index = int(hashlib.md5(obs.timestamp.encode(), usedforsecurity=False).hexdigest(), 16) % 10000
        
        if day_index not in by_day:
            by_day[day_index] = {"provenance_parts": []}
        
        day_data = by_day[day_index]
        prov = f"{obs.metric}={obs.value:.1f}{obs.unit}@{obs.source}"
        if obs.provenance:
            prov += f"[{obs.provenance}]"
        day_data["provenance_parts"].append(prov)
        
        # Map canonical metrics to wearable fields with explicit provenance
        if obs.metric == "heart_rate":
            # Explicitly mark as instantaneous HR, not clinical resting HR
            day_data["resting_hr"] = obs.value
            day_data["provenance_parts"][-1] += " (mapped: heart_rate→resting_hr, NOTE: instantaneous HR)"
        elif obs.metric == "resting_hr":
            day_data["resting_hr"] = obs.value
        elif obs.metric == "hrv_rmssd":
            day_data["hrv_rmssd"] = obs.value
        elif obs.metric == "rr_sd":
            # RR interval SD maps to HRV RMSSD
            day_data["hrv_rmssd"] = obs.value
            day_data["provenance_parts"][-1] += " (mapped: rr_sd→hrv_rmssd)"
        elif obs.metric == "sleep_hours":
            day_data["sleep_hours"] = obs.value
        elif obs.metric == "activity_load":
            day_data["activity_load"] = obs.value
        elif obs.metric == "accel_magnitude_mean":
            # Raw sensor metric, NOT clinical activity_load
            day_data["activity_load"] = obs.value
            day_data["provenance_parts"][-1] += " (mapped: accel_magnitude_mean→activity_load, NOTE: raw sensor metric)"
        elif obs.metric == "eda":
            # EDA stored in provenance (no wearable field)
            day_data["provenance_parts"][-1] += " (eda stored in provenance)"
        elif obs.metric == "skin_temp":
            # Skin temp stored in provenance (no wearable field)
            day_data["provenance_parts"][-1] += " (skin_temp stored in provenance)"
        # Ignore unknown metrics (they're already validated by canonical pipeline)
    
    # Build WearableObservation list
    wearable_obs = []
    for day_index in sorted(by_day.keys()):
        day_data = by_day[day_index]
        provenance = "; ".join(day_data["provenance_parts"])
        wearable_obs.append(WearableObservation(
            day_index=day_index,
            resting_hr=day_data.get("resting_hr"),
            hrv_rmssd=day_data.get("hrv_rmssd"),
            sleep_hours=day_data.get("sleep_hours"),
            activity_load=day_data.get("activity_load"),
            provenance=provenance,
        ))
    
    return wearable_obs


class PublicDatasetSource(WearableSource):
    """CSV-backed source for public datasets sharing the normalized pipeline.

    Supports two schemas:
    1. Legacy: day_index,resting_hr,hrv_rmssd,sleep_hours,activity_load
    2. Provenance-rich: subject_id,recording_id,date,metric,value,unit,source,provenance
    
    The provenance-rich schema feeds through the canonical observation pipeline
    for full validation, unit normalization, and provenance tracking.
    """

    def __init__(self, path: str, *, delimiter: str = ","):
        try:
            handle = open(path, "r", encoding="utf-8", newline="")
        except OSError as exc:
            raise ValueError(f"cannot open dataset CSV: {path}") from exc
        
        with handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            fieldnames = reader.fieldnames or []
            
            # Detect schema
            if fieldnames == list(LEGACY_CSV_SCHEMA):
                observations = self._load_legacy_schema(reader)
            elif fieldnames == list(PUBLIC_DATASET_CSV_SCHEMA):
                observations = self._load_provenance_schema(reader)
            else:
                raise ValueError(
                    f"dataset CSV must have header {','.join(LEGACY_CSV_SCHEMA)} (legacy) "
                    f"or {','.join(PUBLIC_DATASET_CSV_SCHEMA)} (provenance-rich); "
                    f"got {','.join(fieldnames)}"
                )
        
        if not observations:
            raise ValueError("dataset CSV contains no observations")
        seen = sorted(o.day_index for o in observations)
        if any(b <= a for a, b in zip(seen, seen[1:])):
            raise ValueError("dataset CSV day_index values must be unique")
        self._obs = sorted(observations, key=lambda o: o.day_index)

    def _load_legacy_schema(self, reader: csv.DictReader) -> list[WearableObservation]:
        """Load legacy schema (day_index + FIELDS) - bypasses canonical pipeline for backward compat."""
        observations: list[WearableObservation] = []
        for line_no, row in enumerate(reader, start=2):
            try:
                day = int((row.get("day_index") or "").strip())
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"line {line_no}: bad day_index") from exc
            observations.append(WearableObservation(
                day_index=day, **{f: _csv_num(row.get(f), line_no, f) for f in FIELDS},
            ))
        return observations

    def _load_provenance_schema(self, reader: csv.DictReader) -> list[WearableObservation]:
        """Load provenance-rich schema through canonical observation pipeline."""
        raw_items: list[dict] = []
        for line_no, row in enumerate(reader, start=2):
            # Parse provenance JSON
            provenance_data = {}
            try:
                if row.get("provenance"):
                    provenance_data = json.loads(row["provenance"])
            except json.JSONDecodeError:
                provenance_data = {"raw": row["provenance"]}
            
            # Build raw observation for canonical pipeline
            raw_items.append({
                "patient_id": row.get("subject_id", "unknown"),
                "timestamp": row.get("date", "2024-01-01"),  # ISO date
                "source": row.get("source", "public_dataset"),
                "metric": row.get("metric", ""),
                "value": row.get("value", ""),
                "unit": row.get("unit", ""),
                "quality": 1.0,
                "provenance": json.dumps(provenance_data, separators=(",", ":")),
            })
        
        # Validate through canonical pipeline
        canonical_obs, issues = normalize_batch(raw_items)
        if issues:
            # Log issues but don't fail - canonical pipeline already rejects bad data
            for issue in issues:
                print(f"[PublicDatasetSource] Canonical validation issue: {issue}")
        
        # Convert to WearableObservation
        return _canonical_to_wearable(canonical_obs)


def _csv_num(raw: str | None, line_no: int, field: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"line {line_no}: bad {field} value {raw!r}") from exc
