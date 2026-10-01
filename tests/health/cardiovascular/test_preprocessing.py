"""Phase 4 tests: preprocessing determinism, encoding, scaler discipline."""
from rift.health.cardiovascular import dataset, features, preprocessing, schemas


def _raw_predictors():
    df = dataset.load_raw_frame()
    return df[list(schemas.PREDICTOR_COLUMNS)]


def test_encoded_shape_and_feature_order():
    frame, scaler = preprocessing.prepare_matrices(_raw_predictors())
    assert list(frame.columns) == features.model_features()
    assert frame.shape == (303, 59)


def test_scaler_fit_on_train_only():
    import pandas as pd
    df = dataset.load_raw_frame()
    split = __import__("json").loads(
        (dataset.DATA_DIR / "splits" / "split.json").read_text())["rows"]
    train = df.iloc[split["train"]][list(schemas.PREDICTOR_COLUMNS)]
    unscaled = preprocessing.encoded_frame(train)
    _, scaler = preprocessing.prepare_matrices(train)
    # Scaler means equal the train means of the UNSCALED encoded frame.
    import statistics
    for column in list(unscaled.columns)[:5]:
        assert scaler["means"][column] == statistics.fmean(
            float(v) for v in unscaled[column].tolist())


def test_unknown_category_never_crashes():
    import pandas as pd
    frame = _raw_predictors()
    frame = frame.copy()
    frame.loc[frame.index[0], "VHD"] = "alien-level"
    frame.loc[frame.index[1], "Sex"] = "Unknown"
    encoded, scaler = preprocessing.prepare_matrices(frame)
    assert encoded.shape[1] == 59
    # Unknown level -> all-zero one-hot, then standardized: every VHD
    # column must equal -mean/std of that column (no NaN, no crash).
    for column in ("VHD=N", "VHD=mild", "VHD=Moderate", "VHD=Severe"):
        expected = (0.0 - scaler["means"][column]) / scaler["stds"][column]
        assert float(encoded.loc[frame.index[0], column]) == expected
    assert float(encoded.loc[frame.index[1], "Sex"]) == (
        (0.0 - scaler["means"]["Sex"]) / scaler["stds"]["Sex"])


def test_deterministic_encoding():
    first, _ = preprocessing.prepare_matrices(_raw_predictors())
    second, _ = preprocessing.prepare_matrices(_raw_predictors())
    assert (first.to_numpy() == second.to_numpy()).all()
