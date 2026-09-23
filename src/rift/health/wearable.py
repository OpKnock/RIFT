"""Replayable wearable time series. New observations update the twin."""
from __future__ import annotations

from statistics import median

from .models import WearableObservation

FIELDS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")

# Per-field floors for jitter normalization (units of each field).
# A day-over-day jump smaller than the floor counts as no evidence of noise.
JITTER_FLOORS = {
    "resting_hr": 1.0,
    "hrv_rmssd": 1.0,
    "sleep_hours": 0.2,
    "activity_load": 2.0,
}


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


def field_mads(prior: list[WearableObservation]) -> dict[str, float | None]:
    """Median absolute day-over-day change per field over prior history.

    Returns None per field when fewer than two usable deltas exist. This is
    a spread measure of typical fluctuation, not a physiological claim.
    """
    mads: dict[str, float | None] = {}
    for field in FIELDS:
        values = [getattr(o, field) for o in prior if getattr(o, field) is not None]
        deltas = [abs(b - a) for a, b in zip(values, values[1:])]
        mads[field] = float(median(deltas)) if len(deltas) >= 1 else None
    return mads


def jitter_score(
    today: WearableObservation | None,
    yesterday: WearableObservation | None,
    prior: list[WearableObservation],
) -> float:
    """0..1 measurement-jitter score for today's observation.

    Only the EXCESS of today's day-over-day jump beyond typical fluctuation
    (MAD) counts: ordinary day-to-day wobble scores near 0, while jumps
    several times typical score toward 1. Missing fields contribute 0 —
    absence is handled by the missing-data path, not the noise path.
    Deterministic.
    """
    if today is None or yesterday is None:
        return 0.0
    mads = field_mads(prior)
    scores: list[float] = []
    for field in FIELDS:
        cur, prev = getattr(today, field), getattr(yesterday, field)
        if cur is None or prev is None:
            continue
        typical = mads[field]
        if typical is None or typical < JITTER_FLOORS[field]:
            typical = JITTER_FLOORS[field]
        excess = max(0.0, abs(cur - prev) - typical)
        scores.append(min(1.0, excess / (3.0 * typical)))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def trend_terms(
    today: WearableObservation | None,
    yesterday: WearableObservation | None,
) -> dict[str, float | None]:
    """Signed one-day velocities for the risk trend term.

    Returns hr_slope (bpm/day, positive = rising) and sleep_delta
    (hours, negative = worsening), or None per field when either side is
    missing. Uses only observations up to today — no future leakage.
    """
    terms: dict[str, float | None] = {"hr_slope": None, "sleep_delta": None}
    if today is None or yesterday is None:
        return terms
    if today.resting_hr is not None and yesterday.resting_hr is not None:
        terms["hr_slope"] = today.resting_hr - yesterday.resting_hr
    if today.sleep_hours is not None and yesterday.sleep_hours is not None:
        terms["sleep_delta"] = today.sleep_hours - yesterday.sleep_hours
    return terms
