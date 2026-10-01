"""Phase 3 tests: the leakage firewall holds per model.

The challenge rule lets exactly one of LAD/LCX/RCA/Cath into a model.
RIFT is stricter: none of them may ever be inputs, because all four
encode angiography outcomes. These tests prove, per target model, that:
- each forbidden column is rejected individually,
- the classic accident (angiography result as a feature) is rejected,
- all four models share one identical, clean 55-predictor input space,
- the firewall works on both DataFrames and plain column lists.
"""
import pytest

from rift.health.cardiovascular import dataset, leakage, schemas
from rift.health.cardiovascular.leakage import TargetLeakageError


def _predictors():
    df = dataset.load_raw_frame()
    return df[list(schemas.PREDICTOR_COLUMNS)].copy()


@pytest.mark.parametrize("forbidden", ["LAD", "LCX", "RCA", "Cath"])
def test_each_forbidden_column_rejected_individually(forbidden):
    frame = _predictors()
    frame[forbidden] = 0
    with pytest.raises(TargetLeakageError, match=forbidden):
        leakage.assert_no_leakage(frame)


def test_classic_accident_angiography_result_as_feature():
    # The single most likely real-world mistake: feeding the Cath
    # (angiography) outcome in as a predictor of CAD.
    frame = _predictors()
    frame["Cath"] = (dataset.load_raw_frame()["Cath"] == "CAD").astype(int)
    with pytest.raises(TargetLeakageError):
        leakage.assert_no_leakage(frame)


def test_all_four_forbidden_at_once_names_all():
    frame = _predictors()
    for col in ("LAD", "LCX", "RCA", "Cath"):
        frame[col] = 0
    with pytest.raises(TargetLeakageError) as exc:
        leakage.assert_no_leakage(frame)
    for col in ("LAD", "LCX", "RCA", "Cath"):
        assert col in str(exc.value)


def test_clean_predictor_frame_passes():
    leakage.assert_no_leakage(_predictors())


def test_all_models_share_one_clean_input_space():
    spaces = {t: list(leakage.columns_for_target(_predictors(), t).columns)
              for t in ("cad", "lad", "lcx", "rca")}
    assert (spaces["cad"] == spaces["lad"] == spaces["lcx"] == spaces["rca"]
            == list(schemas.PREDICTOR_COLUMNS))


def test_columns_for_target_rejects_unknown_target():
    with pytest.raises(ValueError, match="unknown cardiovascular target"):
        leakage.columns_for_target(_predictors(), "lm")


def test_firewall_accepts_plain_column_lists():
    leakage.assert_no_leakage(list(schemas.PREDICTOR_COLUMNS))
    with pytest.raises(TargetLeakageError):
        leakage.assert_no_leakage(list(schemas.PREDICTOR_COLUMNS) + ["Cath"])


def test_lookalike_columns_are_not_blocked():
    # Exact-match semantics, pinned: near-misses are legitimate features.
    frame = _predictors()
    frame["lad_score"] = 0.0
    frame["cath_lab_visits"] = 0
    leakage.assert_no_leakage(frame)
