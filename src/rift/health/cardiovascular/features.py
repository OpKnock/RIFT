"""Feature contract (Phase 2): the single ordered model feature list."""
from __future__ import annotations

from . import preprocessing, schemas


def model_features() -> list:
    """Ordered feature names every model, explainer, and API shares."""
    return preprocessing.feature_names()


def describe() -> dict:
    return {
        "schema_version": schemas.FEATURE_SCHEMA_VERSION,
        "n_features": len(model_features()),
        "features": model_features(),
        "dropped": schemas.DROPPED_COLUMNS,
    }
