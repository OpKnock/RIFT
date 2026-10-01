"""Track A API contract tests (Phase 17): cardio endpoints over live HTTP."""
from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from rift.api import Handler
from rift.health.cardiovascular import schemas


class _Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"


def _get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, json.loads(response.read().decode())


def _post(url, payload):
    body = json.dumps(payload, default=str).encode()
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _predictors():
    import pandas as pd
    from rift.health.cardiovascular import evaluate
    frame = pd.read_csv(evaluate.DATA_DIR / "processed" / "test.csv")
    row = frame.iloc[0]
    return {c: (row[c].item() if hasattr(row[c], "item") else row[c])
            for c in schemas.PREDICTOR_COLUMNS}


def test_models_lists_four_registered_models():
    with _Server() as server:
        status, payload = _get(server.url("/api/cardio/models"))
        assert status == 200
        assert [m["model_id"] for m in payload["models"]] == [
            "cad-v1", "lad-stenosis-v1", "lcx-stenosis-v1", "rca-stenosis-v1"]
        for model in payload["models"]:
            assert model["calibration"] in ("sigmoid", "isotonic")
            assert 0.0 <= model["test_roc_auc"] <= 1.0


def test_report_serves_committed_evaluation():
    with _Server() as server:
        status, payload = _get(server.url("/api/cardio/report"))
        assert status == 200
        assert set(payload["targets"]) == {"cad", "lad", "lcx", "rca"}
        assert payload["targets"]["cad"]["test"]["n"] == 60


def test_model_cards_flag_weak_models():
    with _Server() as server:
        status, payload = _get(server.url("/api/cardio/model-cards"))
        assert status == 200
        cards = {c["target"]: c for c in payload}
        assert "NOT decision-grade" in cards["rca"]["limitations"]


def test_predict_returns_calibrated_probability():
    with _Server() as server:
        status, payload = _post(server.url("/api/cardio/predict"), {
            "model_id": "cad-v1", "predictors": _predictors()})
        assert status == 200
        assert payload["target"] == "cad"
        assert 0.0 <= payload["probability"] <= 1.0
        assert payload["predicted_label"] in ("CAD", "Normal")
        assert payload["predicted_positive"] == (payload["probability"] >= 0.5)
        assert "not a medical device" in payload["disclaimer"].lower()


def test_predict_with_counterfactuals():
    with _Server() as server:
        status, payload = _post(server.url("/api/cardio/predict"), {
            "model_id": "lad-stenosis-v1", "predictors": _predictors(),
            "include_counterfactuals": True})
        assert status == 200
        assert isinstance(payload["counterfactuals"], list)
        assert len(payload["counterfactuals"]) <= 3


def test_predict_rejects_unknown_model():
    with _Server() as server:
        status, payload = _post(server.url("/api/cardio/predict"), {
            "model_id": "nope-v9", "predictors": _predictors()})
        assert status == 400
        assert payload["error"] == "unknown_model"


def test_predict_rejects_missing_and_unexpected_predictors():
    with _Server() as server:
        partial = _predictors()
        del partial["Age"]
        status, payload = _post(server.url("/api/cardio/predict"), {
            "model_id": "cad-v1", "predictors": partial})
        assert status == 400
        assert payload["error"] == "missing_predictors"
        assert payload["missing"] == ["Age"]

        injected = _predictors()
        injected["Cath"] = "CAD"
        status, payload = _post(server.url("/api/cardio/predict"), {
            "model_id": "cad-v1", "predictors": injected})
        assert status == 400
        assert payload["error"] == "unexpected_predictors"
        assert payload["unexpected"] == ["Cath"]


def test_meta_advertises_cardio():
    with _Server() as server:
        status, payload = _get(server.url("/api/meta"))
        assert status == 200
        assert "cardio" in payload["capabilities"]
