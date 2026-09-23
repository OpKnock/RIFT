"""Wearable data sources: replay today, live ingestion tomorrow.

The twin only depends on the WearableSource interface, so the demo replay
and a future live IoT adapter feed the SAME normalized pipeline:

    WearableSource (interface: history + freshness queries)
    ├── ReplaySource  — fixed historical list (this demo)
    └── LiveIngestSource — append-only live observations (future adapter)

No Bluetooth/hardware is implemented; LiveIngestSource is the seam where a
live adapter plugs in without touching twin, risk, or Guardian code.
"""
from __future__ import annotations

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
