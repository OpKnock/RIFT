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

from .models import WearableObservation
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


# Columns beyond day_index map 1:1 to WearableObservation fields; empty
# cells mean missing (None). day_index must be unique integers.
CSV_SCHEMA = ("day_index",) + FIELDS


class PublicDatasetSource(WearableSource):
    """CSV-backed source for public datasets sharing the normalized pipeline.

    Expected header: day_index,resting_hr,hrv_rmssd,sleep_hours,activity_load
    No dataset is bundled; point this at any CSV following the schema and
    the twin, risk, Guardian, and evaluation layers work unchanged.
    """

    def __init__(self, path: str, *, delimiter: str = ","):
        observations: list[WearableObservation] = []
        try:
            handle = open(path, "r", encoding="utf-8", newline="")
        except OSError as exc:
            raise ValueError(f"cannot open dataset CSV: {path}") from exc
        with handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            if reader.fieldnames != list(CSV_SCHEMA):
                raise ValueError(
                    f"dataset CSV must have header {','.join(CSV_SCHEMA)}; "
                    f"got {','.join(reader.fieldnames or [])}"
                )
            for line_no, row in enumerate(reader, start=2):
                try:
                    day = int((row.get("day_index") or "").strip())
                except (ValueError, AttributeError) as exc:
                    raise ValueError(f"line {line_no}: bad day_index") from exc
                observations.append(WearableObservation(
                    day_index=day, **{f: _csv_num(row.get(f), line_no, f) for f in FIELDS},
                ))
        if not observations:
            raise ValueError("dataset CSV contains no observations")
        seen = sorted(o.day_index for o in observations)
        if any(b <= a for a, b in zip(seen, seen[1:])):
            raise ValueError("dataset CSV day_index values must be unique")
        self._obs = sorted(observations, key=lambda o: o.day_index)


def _csv_num(raw: str | None, line_no: int, field: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"line {line_no}: bad {field} value {raw!r}") from exc
