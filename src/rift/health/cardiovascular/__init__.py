"""Track-A cardiovascular domain: Z-Alizadeh Sani Extension models.

Research decision-support only. Not a medical device; no diagnosis.
See docs/models/cardiovascular/ for model cards.
"""
from .schemas import (
    DOMAIN_ID,
    FEATURE_SCHEMA_VERSION,
    PREPROCESSING_VERSION,
    TARGETS,
    FORBIDDEN_FEATURES,
)

__all__ = ["DOMAIN_ID", "FEATURE_SCHEMA_VERSION", "PREPROCESSING_VERSION",
           "TARGETS", "FORBIDDEN_FEATURES"]
