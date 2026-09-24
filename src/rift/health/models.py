"""Healthcare domain types. Plain JSON-safe dataclasses; no clinical claims."""
from __future__ import annotations

from dataclasses import dataclass, field

# Hard physiological plausibility envelope for the demo observables.
# Values outside these ranges are rejected by Guardian as impossible.
PHYSIOLOGICAL_BOUNDS = {
    "resting_hr": (25.0, 220.0),      # bpm
    "hrv_rmssd": (0.0, 300.0),        # ms
    "sleep_hours": (0.0, 24.0),       # h/day
    "activity_load": (0.0, 200.0),    # demo exertion index
    "age": (0.0, 120.0),              # years
}


@dataclass(frozen=True)
class EHRRecord:
    """Normalized EHR snapshot. Unknown/absent fields stay None (flagged)."""
    patient_id: str = "demo-patient-01"
    age: float | None = None
    sex: str | None = None
    conditions: tuple[str, ...] = ()
    medications: tuple[str, ...] = ()
    resting_hr_clinic: float | None = None
    systolic_bp: float | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "age": self.age,
            "sex": self.sex,
            "conditions": list(self.conditions),
            "medications": list(self.medications),
            "resting_hr_clinic": self.resting_hr_clinic,
            "systolic_bp": self.systolic_bp,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class WearableObservation:
    """One timestamped wearable sample. day_index is days since demo start.

    provenance names the origin (e.g. source adapter + file/device id);
    empty means unrecorded origin, which Guardian treats as a flag, never
    as verified provenance.
    """
    day_index: int
    resting_hr: float | None = None
    hrv_rmssd: float | None = None
    sleep_hours: float | None = None
    activity_load: float | None = None
    stale: bool = False  # True when carried forward from an older sample
    provenance: str = ""

    def to_dict(self) -> dict:
        return {
            "day_index": self.day_index,
            "resting_hr": self.resting_hr,
            "hrv_rmssd": self.hrv_rmssd,
            "sleep_hours": self.sleep_hours,
            "activity_load": self.activity_load,
            "stale": self.stale,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class PatientState:
    """Synchronized twin state at one replay time. All numerics or None."""
    day_index: int = 0
    resting_hr: float | None = None
    hrv_rmssd: float | None = None
    sleep_hours: float | None = None
    activity_load: float | None = None
    data_quality: float = 1.0  # 0..1 fraction of expected fields present+fresh
    stale_days: int = 0
    provenance: str = ""  # origin chain of the synchronized observation

    def to_dict(self) -> dict:
        return {
            "day_index": self.day_index,
            "resting_hr": self.resting_hr,
            "hrv_rmssd": self.hrv_rmssd,
            "sleep_hours": self.sleep_hours,
            "activity_load": self.activity_load,
            "data_quality": self.data_quality,
            "stale_days": self.stale_days,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class PersonalBaseline:
    """Medians over the patient's own history window (never population norms)."""
    resting_hr: float | None = None
    hrv_rmssd: float | None = None
    sleep_hours: float | None = None
    activity_load: float | None = None
    window_days: int = 0

    def to_dict(self) -> dict:
        return {
            "resting_hr": self.resting_hr,
            "hrv_rmssd": self.hrv_rmssd,
            "sleep_hours": self.sleep_hours,
            "activity_load": self.activity_load,
            "window_days": self.window_days,
        }


@dataclass(frozen=True)
class Deviation:
    """Current value expressed against the personal baseline."""
    field: str
    current: float | None
    baseline: float | None
    delta: float | None  # current - baseline
    direction: str  # "above" | "below" | "at" | "unknown"

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "current": self.current,
            "baseline": self.baseline,
            "delta": self.delta,
            "direction": self.direction,
        }
