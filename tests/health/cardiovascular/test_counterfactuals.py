"""Phase 11 tests: flip validity, ranking, determinism, safety."""
from __future__ import annotations

from rift.health.cardiovascular import counterfactuals, evaluate, registry, targets

THRESHOLD = 0.5


def _sample():
    frames = evaluate._load_split_frames()
    return frames["test"].iloc[[0]]


def test_every_returned_edit_really_flips():
    sample = _sample()
    label = int(targets.read_labels(sample, "cad").iloc[0])
    out = counterfactuals.counterfactuals_for("cad-v1", sample, label)
    assert out["model_id"] == "cad-v1" and out["true_label"] == label
    assert 0.0 <= out["prob_before"] <= 1.0
    for cf in out["counterfactuals"]:
        assert (cf["prob_after"] >= THRESHOLD) != (out["prob_before"] >= THRESHOLD)
        assert 0.0 <= cf["prob_after"] <= 1.0
        assert cf["std_distance"] >= 0.0


def test_corrective_first_then_distance():
    sample = _sample()
    label = int(targets.read_labels(sample, "cad").iloc[0])
    out = counterfactuals.counterfactuals_for("cad-v1", sample, label)
    flags = [cf["corrective"] for cf in out["counterfactuals"]]
    assert flags == sorted(flags, reverse=True)
    dists = [cf["std_distance"] for cf in out["counterfactuals"]]
    for group in (True, False):
        group_d = [d for cf, d in zip(out["counterfactuals"], dists)
                   if cf["corrective"] == group]
        assert group_d == sorted(group_d)


def test_deterministic_and_bounded():
    sample = _sample()
    first = counterfactuals.counterfactuals_for("lad-stenosis-v1", sample, 1)
    second = counterfactuals.counterfactuals_for("lad-stenosis-v1", sample, 1)
    assert first == second
    assert len(first["counterfactuals"]) <= counterfactuals.TOP_K


def test_non_actionable_flagged_not_hidden():
    from rift.health.cardiovascular import schemas
    assert counterfactuals.NON_ACTIONABLE <= set(schemas.PREDICTOR_COLUMNS)
    sample = _sample()
    out = counterfactuals.counterfactuals_for(
        "cad-v1", sample, int(targets.read_labels(sample, "cad").iloc[0]),
        top_k=50)
    # Invariant: the flag is exactly membership in NON_ACTIONABLE — a
    # demographic edit is shown as an explanation, never as advice.
    for cf in out["counterfactuals"]:
        assert cf["actionable"] == (cf["feature"] not in counterfactuals.NON_ACTIONABLE)


def test_values_come_from_observed_train():
    train = counterfactuals._train_predictors()
    values = counterfactuals.candidate_values(train)
    assert set(values) == set(train.columns)
    for column, vals in values.items():
        assert len(vals) >= 1, column
    # CHF is constant in train ('N' only): engine must skip it, not crash.
    assert values["CHF"] == ["N"]
