"""Phase 4 tests: target mapping from raw columns to labels."""
from rift.health.cardiovascular import dataset, schemas


def test_each_target_maps_expected_counts():
    df = dataset.load_raw_frame()
    labels = dataset.encode_targets(df)
    assert labels["cad"].sum() == 216
    assert labels["lad"].sum() == 177
    assert labels["lcx"].sum() == 119
    assert labels["rca"].sum() == 114
    for target, spec in schemas.TARGETS.items():
        assert set(labels[target].unique().tolist()) <= {0, 1}


def test_target_definitions_match_challenge():
    # Cath=CAD label; vessel Stenotic labels; sources pinned.
    assert schemas.TARGETS["cad"] == {
        "source": "Cath", "positive": "CAD",
        "description": "CAD if any vessel stenotic"}
    for vessel in ("lad", "lcx", "rca"):
        assert schemas.TARGETS[vessel]["positive"] == "Stenotic"
