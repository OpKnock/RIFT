"""Replayable wearable time series. New observations update the twin."""
from __future__ import annotations

from statistics import median

from .models import WearableObservation

# Required fields for completeness/staleness calculations (original 4)
REQUIRED_FIELDS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load")

# All fields including optional new metrics
FIELDS = ("resting_hr", "hrv_rmssd", "sleep_hours", "activity_load", "heart_rate", "rr_sd")

# Per-field floors for jitter normalization (units of each field).
# A day-over-day jump smaller than the floor counts as no evidence of noise.
JITTER_FLOORS = {
    "resting_hr": 1.0,
    "hrv_rmssd": 1.0,
    "sleep_hours": 0.2,
    "activity_load": 2.0,
    "heart_rate": 1.0,
    "rr_sd": 1.0,
}


class WearableStream:
    """Ordered observations replayable up to any day index.

    Missing days are carried forward and marked stale so uncertainty grows
    instead of silently using fresh-looking data.
    """

    def __init__(self, observations: list[WearableObservation]):
        self._obs = sorted(observations, key=lambda o: (o.patient_id, o.day_index))
        if self._obs and any(b.day_index <= a.day_index and b.patient_id == a.patient_id for a, b in zip(self._obs, self._obs[1:])):
            raise ValueError("duplicate day_index in wearable stream for same patient")

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
        real = [o for o in past if not o.stale and all(getattr(o, f) is not None for f in REQUIRED_FIELDS)]
        if not real:
            return len(past)
        return day_index - real[-1].day_index

    def completeness_at(self, day_index: int) -> float:
        """Fraction of REQUIRED fields present in the latest sample."""
        latest = self.latest_at(day_index)
        if latest is None:
            return 0.0
        present = sum(1 for f in REQUIRED_FIELDS if getattr(latest, f) is not None)
        return present / len(REQUIRED_FIELDS)


class MultiPatientStream:
    """Multi-patient wearable stream that delegates to patient-specific streams.
    
    Provides a unified interface for multi-patient cohorts while maintaining
    patient-specific timelines and staleness calculations.
    """

    def __init__(self, observations: list[WearableObservation]):
        # Group observations by patient_id
        by_patient: dict[str, list[WearableObservation]] = {}
        for obs in observations:
            pid = obs.patient_id or "unknown"
            if pid not in by_patient:
                by_patient[pid] = []
            by_patient[pid].append(obs)
        
        # Create patient-specific streams
        self._streams: dict[str, WearableStream] = {}
        for pid, obs in by_patient.items():
            self._streams[pid] = WearableStream(obs)
        
        # Global ordering for iteration
        self._all_obs = sorted(observations, key=lambda o: (o.patient_id, o.day_index))

    @property
    def patient_ids(self) -> list[str]:
        return sorted(self._streams.keys())

    @property
    def start_day(self) -> int | None:
        if not self._streams:
            return None
        return min(s.start_day for s in self._streams.values() if s.start_day is not None)

    @property
    def end_day(self) -> int | None:
        if not self._streams:
            return None
        return max(s.end_day for s in self._streams.values() if s.end_day is not None)

    def get_stream(self, patient_id: str) -> WearableStream | None:
        """Get the stream for a specific patient."""
        return self._streams.get(patient_id)

    def observations_upto(self, day_index: int) -> list[WearableObservation]:
        """Get all observations up to day_index across all patients."""
        result = []
        for stream in self._streams.values():
            result.extend(stream.observations_upto(day_index))
        return sorted(result, key=lambda o: (o.patient_id, o.day_index))

    def latest_at(self, day_index: int) -> WearableObservation | None:
        """Get the latest observation across all patients up to day_index."""
        latest = None
        for stream in self._streams.values():
            obs = stream.latest_at(day_index)
            if obs is not None:
                if latest is None or obs.day_index > latest.day_index:
                    latest = obs
        return latest

    def stale_days_at(self, day_index: int) -> int:
        """Maximum staleness across all patients."""
        if not self._streams:
            return day_index
        return max(s.stale_days_at(day_index) for s in self._streams.values())

    def completeness_at(self, day_index: int) -> float:
        """Average completeness across all patients."""
        if not self._streams:
            return 0.0
        return sum(s.completeness_at(day_index) for s in self._streams.values()) / len(self._streams)

    def observations_upto_patient(self, patient_id: str, day_index: int) -> list[WearableObservation]:
        """Get observations up to day_index for a specific patient."""
        stream = self._streams.get(patient_id)
        if stream is None:
            return []
        return stream.observations_upto(day_index)

    def latest_at_patient(self, patient_id: str, day_index: int) -> WearableObservation | None:
        """Get latest observation for a specific patient up to day_index."""
        stream = self._streams.get(patient_id)
        if stream is None:
            return None
        return stream.latest_at(day_index)


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
    if today.heart_rate is not None and yesterday.heart_rate is not None:
        # Also track generic HR trend separately
        terms["generic_hr_slope"] = today.heart_rate - yesterday.heart_rate
    if today.sleep_hours is not None and yesterday.sleep_hours is not None:
        terms["sleep_delta"] = today.sleep_hours - yesterday.sleep_hours
    return terms