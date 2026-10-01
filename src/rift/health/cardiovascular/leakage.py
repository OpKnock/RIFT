"""Hard leakage firewall (Phase 3).

Challenge rule: exactly one of LAD / LCX / RCA / Cath may inform a model,
the rest must be eliminated. RIFT is stricter: NONE of them may EVER be
model inputs, because all four encode angiography outcomes (the targets).

Every feature frame passes through :func:`assert_no_leakage` before it
reaches training, evaluation, calibration, explanation, or prediction.
:func:`columns_for_target` additionally drops the target's own source
column defensively (belt and suspenders: the firewall already excludes
all four, so this is normally a no-op that documents intent).
"""
from __future__ import annotations

from . import schemas


class TargetLeakageError(ValueError):
    """Raised when a forbidden clinical predictor reaches model inputs."""


def assert_no_leakage(frame) -> None:
    """Fail closed if any forbidden column is present in a feature frame."""
    columns = set(frame.columns if hasattr(frame, "columns") else frame)
    leaked = schemas.FORBIDDEN_FEATURES.intersection(columns)
    if leaked:
        raise TargetLeakageError(
            "target leakage: forbidden clinical predictor(s) in model inputs: %s. "
            "LAD/LCX/RCA/Cath encode angiography outcomes and must never be features."
            % sorted(leaked))


def columns_for_target(frame, target: str):
    """Return the frame restricted to legal predictor columns for a target."""
    if target not in schemas.TARGETS:
        raise ValueError("unknown cardiovascular target: %r" % target)
    assert_no_leakage(frame)
    keep = [c for c in schemas.PREDICTOR_COLUMNS if c in frame.columns]
    return frame[keep].copy()
