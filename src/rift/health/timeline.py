"""Patient timeline: canonical observations → daily twin inputs.

Pipeline order is load-bearing: raw timestamp → strict ISO parse →
UTC normalization (in observations.normalize_timestamp) → calendar-day
bucket → per-metric estimation → integer day indices.

"Calendar day" therefore always means UTC calendar day. Naive timestamps
are documented as assumed UTC at the validation boundary, so
2026-01-05T00:30+05:30 and 2026-01-04T19:00Z bucket together (same
instant), deterministically. Patient/site-local day bucketing is future
work requiring an explicit timezone field this schema does not yet have.
"""
from __future__ import annotations

from statistics import median

from .models import WearableObservation
from .observations import CanonicalObservation
from .wearable import FIELDS


def bucket_by_day(observations: list[CanonicalObservation]) -> dict[str, list[CanonicalObservation]]:
    """Group observations by UTC calendar date (normalized timestamp[:10]).

    Requires normalized timestamps: bucketing raw strings would split one
    instant across days. Sorted output for reproducible indices.
    """
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


# Twin-estimated metrics in this schema version. Accepted canonical metrics
# outside this set are preserved at observation level but NOT consumed by
# twin estimation v1 — timeline_coverage() reports them on every snapshot
# so acceptance can never silently become loss.
TWIN_ESTIMATED_METRICS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")


def timeline_coverage(observations: list[CanonicalObservation]) -> dict[str, str]:
    """Per-metric disposition: estimated by the twin, or preserved-but-unestimated with reason."""
    present = {o.metric for o in observations}
    coverage: dict[str, str] = {}
    for metric in sorted(present):
        if metric in TWIN_ESTIMATED_METRICS:
            coverage[metric] = "estimated"
        else:
            coverage[metric] = (
                "preserved-not-estimated: accepted by ingestion, not consumed "
                "by twin estimation v1 (no silent loss; revisit on schema upgrade)"
            )
    return coverage


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
        origins = sorted({o.provenance for o in buckets[date] if o.provenance})
        rows.append(WearableObservation(
            day_index=day_index[date],
            resting_hr=estimated["resting_hr"],
            hrv_rmssd=estimated["hrv_rmssd"],
            sleep_hours=estimated["sleep_hours"],
            activity_load=estimated["activity_load"],
            provenance=";".join(origins),
        ))
    return rows, day_index
