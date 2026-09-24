"""Patient timeline: canonical observations → daily twin inputs.

Separates three jobs the old day-index rows conflated:
1. bucketing timestamped observations into calendar days,
2. estimating one daily value per metric (median: robust to multi-obs days),
3. mapping calendar days to reproducible integer indices.

Estimation is deliberately simple (median) and documented as such — a
future StatisticalModel/ValidatedClinicalModel plugs into estimate_day().
"""
from __future__ import annotations

from statistics import median

from .models import WearableObservation
from .observations import CanonicalObservation
from .wearable import FIELDS


def bucket_by_day(observations: list[CanonicalObservation]) -> dict[str, list[CanonicalObservation]]:
    """Group observations by calendar date (timestamp[:10]). Sorted output."""
    buckets: dict[str, list[CanonicalObservation]] = {}
    for obs in sorted(observations, key=lambda o: o.timestamp):
        buckets.setdefault(obs.timestamp[:10], []).append(obs)
    return buckets


def estimate_day(day_observations: list[CanonicalObservation]) -> dict[str, float | None]:
    """Median per metric over one day's observations; None when absent."""
    estimated: dict[str, float | None] = {}
    for field in FIELDS:
        values = [o.value for o in day_observations if o.metric == field]
        estimated[field] = float(median(values)) if values else None
    return estimated


def day_quality(day_observations: list[CanonicalObservation]) -> float:
    """Mean source quality of the day's observations (0.0 when empty)."""
    if not day_observations:
        return 0.0
    return sum(o.quality for o in day_observations) / len(day_observations)


def to_daily_rows(
    observations: list[CanonicalObservation],
) -> tuple[list[WearableObservation], dict[str, int]]:
    """Bucket + estimate a full timeline.

    Returns (daily_rows, day_index) where day_index maps 'YYYY-MM-DD' to
    0..n in chronological order. Rows carry stale=False; staleness is a
    replay-time property computed by WearableStream, not stored here.
    """
    buckets = bucket_by_day(observations)
    dates = sorted(buckets)
    day_index = {date: index for index, date in enumerate(dates)}
    rows = []
    for date in dates:
        estimated = estimate_day(buckets[date])
        rows.append(WearableObservation(
            day_index=day_index[date],
            resting_hr=estimated["resting_hr"],
            hrv_rmssd=estimated["hrv_rmssd"],
            sleep_hours=estimated["sleep_hours"],
            activity_load=estimated["activity_load"],
        ))
    return rows, day_index
