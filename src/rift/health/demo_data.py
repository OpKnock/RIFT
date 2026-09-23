"""Deterministic synthetic demo datasets. NOT clinically validated.

demo_stream(): 14 days for demo-patient-01 (dashboard): calm first week,
a poor-sleep + high-exertion spell on days 9-10 that drives strain risk
over threshold, then recovery. Day 6 is partial (missing HRV).

demo_series(): longer configurable series (default 60 days, 3 spells) for
temporal evaluation with a calibration/holdout split. Same generator
semantics. Seeded RNG => identical series on every run.
"""
from __future__ import annotations

import random

from .models import WearableObservation
from .sources import ReplaySource
from .wearable import WearableStream


def demo_stream(seed: int = 42) -> WearableStream:
    return demo_series(seed=seed, days=14, spells=((9, 2),), partial_days=(6,))


def demo_series(
    seed: int = 7,
    days: int = 60,
    spells: tuple[tuple[int, int], ...] = ((20, 2), (35, 1), (47, 2)),
    partial_days: tuple[int, ...] = (),
) -> WearableStream:
    """Longer deterministic series for temporal evaluation.

    Same generator semantics as demo_stream: calm baseline rhythm plus
    poor-sleep/high-exertion spells that drive strain up, then recovery.
    `spells` are (start_day, length) pairs. `partial_days` lose their HRV
    sample to exercise data-quality paths. Seeded => reproducible.
    """
    rng = random.Random(seed)  # nosec B311 -- synthetic demo data; determinism required, not secrecy
    observations: list[WearableObservation] = []
    spell_days = {d for start, length in spells for d in range(start, start + length)}
    for day in range(days):
        hr = 68.0 + 2.0 * rng.uniform(-1, 1)
        hrv = 48.0 + 4.0 * rng.uniform(-1, 1)
        sleep = 7.2 + 0.5 * rng.uniform(-1, 1)
        activity = 45.0 + 10.0 * rng.uniform(-1, 1)
        if day in spell_days:
            sleep -= 3.0
            activity += 40.0
            hr += 9.0
            hrv -= 14.0
        observations.append(WearableObservation(
            day_index=day,
            resting_hr=round(hr, 1),
            hrv_rmssd=None if day in partial_days else round(hrv, 1),
            sleep_hours=round(max(0.0, sleep), 1),
            activity_load=round(max(0.0, activity), 1),
        ))
    return ReplaySource(observations)
