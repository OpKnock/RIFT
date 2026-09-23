"""Patient-specific baselines from the patient's own history window."""
from __future__ import annotations

from statistics import median

from .models import Deviation, PersonalBaseline, WearableObservation
from .wearable import FIELDS


def _median(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return float(median(clean)) if clean else None


def personal_baseline(history: list[WearableObservation], window: int = 7) -> PersonalBaseline:
    """Median of each field over the trailing `window` real samples.

    Stale or partial samples are excluded so the baseline reflects measured
    physiology, not carried-forward filler.
    """
    real = [o for o in history if not o.stale][-window:] if window > 0 else []
    return PersonalBaseline(
        resting_hr=_median([o.resting_hr for o in real]),
        hrv_rmssd=_median([o.hrv_rmssd for o in real]),
        sleep_hours=_median([o.sleep_hours for o in real]),
        activity_load=_median([o.activity_load for o in real]),
        window_days=len(real),
    )


def deviations(current: WearableObservation | None, baseline: PersonalBaseline) -> list[Deviation]:
    """Express the current sample against the personal baseline."""
    out: list[Deviation] = []
    for field in FIELDS:
        cur = getattr(current, field) if current else None
        base = getattr(baseline, field)
        if cur is None or base is None:
            out.append(Deviation(field, cur, base, None, "unknown"))
        elif cur > base:
            out.append(Deviation(field, cur, base, cur - base, "above"))
        elif cur < base:
            out.append(Deviation(field, cur, base, cur - base, "below"))
        else:
            out.append(Deviation(field, cur, base, 0.0, "at"))
    return out
