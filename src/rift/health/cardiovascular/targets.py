"""Target access (Phase 2): label vectors live beside processed splits.

Processed CSVs carry ``__y_<target>`` columns written by dataset.prepare;
this module reads them back so training, evaluation, and prediction can
never re-derive labels from raw target columns (and therefore can never
leak them into features).
"""
from __future__ import annotations

from . import schemas


def label_column(target: str) -> str:
    if target not in schemas.TARGETS:
        raise ValueError("unknown cardiovascular target: %r" % target)
    return "__y_%s" % target


def read_labels(processed_frame, target: str):
    column = label_column(target)
    if column not in processed_frame.columns:
        raise ValueError("processed frame lacks label column %r" % column)
    return processed_frame[column].astype(int)
