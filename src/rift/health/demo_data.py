"""Deterministic synthetic demo dataset. NOT clinically validated.

Fourteen days for demo-patient-01: stable first week, then a poor-sleep +
high-exertion spell (days 9-11) that drives strain risk up, then recovery.
Day 6 is a partial sample (missing HRV) to exercise data-quality paths.
Seeded RNG => identical series on every run.
"""
from __future__ import annotations

import random

from .models import WearableObservation
from .wearable import WearableStream


def demo_stream(seed: int = 42) -> WearableStream:
    rng = random.Random(seed)  # nosec B311 -- synthetic demo data; determinism required, not secrecy
    observations: list[WearableObservation] = []
    for day in range(14):
        hr = 68.0 + 2.0 * rng.uniform(-1, 1)
        hrv = 48.0 + 4.0 * rng.uniform(-1, 1)
        sleep = 7.2 + 0.5 * rng.uniform(-1, 1)
        activity = 45.0 + 10.0 * rng.uniform(-1, 1)
        if day in (9, 10):
            sleep -= 3.0
            activity += 40.0
            hr += 9.0
            hrv -= 14.0
        if day == 11:
            sleep -= 1.5
            activity += 20.0
            hr += 4.0
            hrv -= 7.0
        observations.append(WearableObservation(
            day_index=day,
            resting_hr=round(hr, 1),
            hrv_rmssd=None if day == 6 else round(hrv, 1),
            sleep_hours=round(max(0.0, sleep), 1),
            activity_load=round(max(0.0, activity), 1),
        ))
    return WearableStream(observations)
