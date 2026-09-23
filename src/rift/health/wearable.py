"""Replayable wearable time series. New observations update the twin."""
from __future__ import annotations

from .models import WearableObservation

FIELDS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")


class WearableStream:
    """Ordered observations replayable up to any day index.

    Missing days are carried forward and marked stale so uncertainty grows
    instead of silently using fresh-looking data.
    """

    def __init__(self, observations: list[WearableObservation]):
        self._obs = sorted(observations, key=lambda o: o.day_index)
        if self._obs and any(b.day_index <= a.day_index for a, b in zip(self._obs, self._obs[1:])):
            raise ValueError("duplicate day_index in wearable stream")

    @property
    def start_day(self) -> int | None:
        return self._obs[0].day_index if self._obs else None

    @property
    def end_day(self) -> int | None:
        return self._obs[-1].day_index if self._obs else None

    def observations_upto(self, day_index: int) -> list[WearableObservation]:
        return [o for o in self._obs if o.day_index <= day_index]

    def latest_at(self, day_index: int) -> WearableObservation | None:
        past = self.observations_upto(day_index)
        return past[-1] if past else None

    def stale_days_at(self, day_index: int) -> int:
        """Days since the last real (non-stale, fully present) sample."""
        past = self.observations_upto(day_index)
        real = [o for o in past if not o.stale and all(getattr(o, f) is not None for f in FIELDS)]
        if not real:
            return len(past)
        return day_index - real[-1].day_index

    def completeness_at(self, day_index: int) -> float:
        """Fraction of expected fields present in the latest sample."""
        latest = self.latest_at(day_index)
        if latest is None:
            return 0.0
        present = sum(1 for f in FIELDS if getattr(latest, f) is not None)
        return present / len(FIELDS)
