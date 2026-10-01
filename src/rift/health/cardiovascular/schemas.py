"""Track-A schemas: targets, leakage firewall lists, feature contract.

Dataset: UCI Z-Alizadeh Sani Extension (id 411), 303 records x 59 columns.
55 predictor columns + 4 target columns (LAD, LCX, RCA, Cath).

The challenge rule is structural: to use the dataset, exactly one of
LAD / LCX / RCA / Cath may be a model input and the others must be
eliminated. RIFT goes further: NONE of them may ever be inputs.
:mod:`leakage` enforces this at runtime; tests prove it per model.
"""
from __future__ import annotations

DOMAIN_ID = "cardiovascular"
FEATURE_SCHEMA_VERSION = "v1.2"
PREPROCESSING_VERSION = "v1"

# Target definitions: source column -> positive label.
TARGETS = {
    "cad": {"source": "Cath", "positive": "CAD", "description": "CAD if any vessel stenotic"},
    "lad": {"source": "LAD", "positive": "Stenotic", "description": "LAD stenosis"},
    "lcx": {"source": "LCX", "positive": "Stenotic", "description": "LCX stenosis"},
    "rca": {"source": "RCA", "positive": "Stenotic", "description": "RCA stenosis"},
}

# HARD leakage firewall: these columns must never appear in model inputs.
# LAD/LCX/RCA/Cath encode angiography outcomes (the targets themselves).
FORBIDDEN_FEATURES = frozenset({"LAD", "LCX", "RCA", "Cath"})

# Binary Y/N columns -> 1/0.
BINARY_YN = (
    "Obesity", "CRF", "CVA", "Airway disease", "Thyroid Disease", "CHF",
    "DLP", "Weak Peripheral Pulse", "Lung rales", "Systolic Murmur",
    "Diastolic Murmur", "Dyspnea", "Atypical", "Nonanginal",
    "LowTH Ang", "LVH", "Poor R Progression",
)

# Multi-category columns -> one-hot with these fixed levels.
CATEGORICAL_LEVELS = {
    "Sex": ("Male", "Fmale"),  # "Fmale" is the dataset's verbatim spelling
    "BBB": ("N", "LBBB", "RBBB"),
    "VHD": ("N", "mild", "Moderate", "Severe"),
}

# Predictor columns (everything except targets), in dataset order.
PREDICTOR_COLUMNS = (
    "Age", "Weight", "Length", "Sex", "BMI", "DM", "HTN",
    "Current Smoker", "EX-Smoker", "FH", "Obesity", "CRF", "CVA",
    "Airway disease", "Thyroid Disease", "CHF", "DLP", "BP", "PR",
    "Edema", "Weak Peripheral Pulse", "Lung rales", "Systolic Murmur",
    "Diastolic Murmur", "Typical Chest Pain", "Dyspnea", "Function Class",
    "Atypical", "Nonanginal", "Exertional CP", "LowTH Ang", "Q Wave",
    "St Elevation", "St Depression", "Tinversion", "LVH",
    "Poor R Progression", "BBB", "FBS", "CR", "TG", "LDL", "HDL",
    "BUN", "ESR", "HB", "K", "Na", "WBC", "Lymph", "Neut", "PLT",
    "EF-TTE", "Region RWMA", "VHD",
)

# Zero-variance columns dropped with documentation (not silently).
DROPPED_COLUMNS = {
    # 'Exertional CP' is constant 'N' across all 303 records.
    "Exertional CP": "zero variance (constant 'N' in all 303 records)",
}

# Expected raw sheet contract (fails loudly on schema drift).
EXPECTED_ROWS = 303
EXPECTED_COLUMNS = 59
