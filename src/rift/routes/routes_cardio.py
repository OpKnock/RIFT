"""Route handlers for the Track A cardiovascular API contract (Phase 16).

Read-only model/report endpoints plus one compute endpoint
(POST /api/cardio/predict). Same posture as the rest of the service:
identity-gated (open in dev, bearer-gated otherwise), fail-closed
validation (400 malformed, 422 leakage, 503 not-trained), upstream
details never echoed.
"""
from __future__ import annotations

import json

from rift.observability import log_event


def _gate(h, request_id, timer, method, path):
    _, ok = h._identity(request_id)
    if not ok:
        h._finish(timer, request_id, method, path, 401, "auth")
        return False
    return True


def _read_site_json(name: str):
    from rift.health.cardiovascular import evaluate
    path = evaluate.EVAL_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text())


def get_api_cardio_models(h, request_id, timer, path, query):
    """Route if path == "/api/cardio/models": registry summaries + test metrics."""
    if not _gate(h, request_id, timer, "GET", path):
        return True
    try:
        from rift.health.cardiovascular import registry
        report = _read_site_json("report.json")
        calibration = _read_site_json("calibration.json")
        if report is None:
            h._send(503, json.dumps({"error": "cardio_not_ready",
                                     "detail": "evaluation report not built; run the Track A pipeline"}),
                    request_id=request_id)
            h._finish(timer, request_id, "GET", path, 503, "not_ready")
            return True
        models = []
        for record in registry.list_models():
            target = record["target"]
            test = report["targets"][target]["test"]
            models.append({
                "model_id": record["model_id"],
                "target": target,
                "algorithm": record["algorithm"],
                "test_roc_auc": test["roc_auc"],
                "test_f1": test["f1"],
                "calibration": (calibration["models"][target]["method"]
                                if calibration else None),
                "feature_schema_version": record["feature_schema_version"],
            })
        h._send(200, json.dumps({"models": models}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        log_event("internal_error", request_id=request_id, route="cardio-models")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}),
                request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True


def get_api_cardio_report(h, request_id, timer, path, query):
    """Route if path == "/api/cardio/report": the committed evaluation report."""
    if not _gate(h, request_id, timer, "GET", path):
        return True
    report = _read_site_json("report.json")
    if report is None:
        h._send(503, json.dumps({"error": "cardio_not_ready"}), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 503, "not_ready")
        return True
    h._send(200, json.dumps(report), request_id=request_id)
    h._finish(timer, request_id, "GET", path, 200)
    return True


def get_api_cardio_model_cards(h, request_id, timer, path, query):
    """Route if path == "/api/cardio/model-cards": honest per-model cards."""
    if not _gate(h, request_id, timer, "GET", path):
        return True
    try:
        from rift.health.cardiovascular import evaluate as _eval
        path_cards = _eval.DATA_DIR / "site" / "model_cards.json"
        if not path_cards.exists():
            h._send(503, json.dumps({"error": "cardio_not_ready"}), request_id=request_id)
            h._finish(timer, request_id, "GET", path, 503, "not_ready")
            return True
        h._send(200, path_cards.read_text(), request_id=request_id)
        h._finish(timer, request_id, "GET", path, 200)
    except Exception:
        log_event("internal_error", request_id=request_id, route="cardio-cards")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}),
                request_id=request_id)
        h._finish(timer, request_id, "GET", path, 500, "internal")
    return True


def post_api_cardio_predict(h, request_id, timer, path, query):
    """Route if path == "/api/cardio/predict": calibrated stenosis probability."""
    body, _raw = h._read_json()
    if body == "overflow":
        h._send(413, json.dumps({"error": "payload_too_large"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 413, "validation")
        return True
    if not isinstance(body, dict):
        h._send(400, json.dumps({"error": "invalid_json"}), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 400, "validation")
        return True
    _, ok = h._identity(request_id, body, None)
    if not ok:
        h._finish(timer, request_id, "POST", path, 401, "auth")
        return True
    try:
        from rift.health.cardiovascular import calibration as _cal
        from rift.health.cardiovascular import counterfactuals as _cf
        from rift.health.cardiovascular import registry as _reg
        from rift.health.cardiovascular import schemas as _schemas
        from rift.health.cardiovascular.leakage import TargetLeakageError
        model_id = body.get("model_id")
        if model_id not in _reg.MODEL_IDS.values():
            h._send(400, json.dumps({"error": "unknown_model",
                                     "detail": "known models: %s" % sorted(_reg.MODEL_IDS.values())}),
                    request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        predictors = body.get("predictors")
        if not isinstance(predictors, dict):
            h._send(400, json.dumps({"error": "missing_predictors",
                                     "detail": "predictors must map all 55 feature names to values"}),
                    request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        missing = [c for c in _schemas.PREDICTOR_COLUMNS if c not in predictors]
        if missing:
            h._send(400, json.dumps({"error": "missing_predictors", "missing": missing}),
                    request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        unexpected = [c for c in predictors if c not in _schemas.PREDICTOR_COLUMNS]
        if unexpected:
            h._send(400, json.dumps({"error": "unexpected_predictors",
                                     "unexpected": sorted(unexpected)}),
                    request_id=request_id)
            h._finish(timer, request_id, "POST", path, 400, "validation")
            return True
        import pandas as pd
        frame = pd.DataFrame([{c: predictors[c] for c in _schemas.PREDICTOR_COLUMNS}])
        try:
            prob = float(_cal.predict_calibrated(model_id, frame)[0])
        except TargetLeakageError as exc:
            log_event("validation_failure", request_id=request_id, detail=str(exc)[:200])
            h._send(422, json.dumps({"error": "target_leakage",
                                     "detail": "forbidden angiography-outcome column in predictors"}),
                    request_id=request_id)
            h._finish(timer, request_id, "POST", path, 422, "validation")
            return True
        _, record = _reg.load_model(model_id)
        positive = prob >= 0.5
        names = {"cad": ("CAD", "Normal"), "lad": ("Stenotic", "Normal"),
                 "lcx": ("Stenotic", "Normal"), "rca": ("Stenotic", "Normal")}
        payload = {
            "model_id": model_id,
            "target": record["target"],
            "probability": prob,
            "predicted_label": names[record["target"]][0 if positive else 1],
            "predicted_positive": positive,
            "threshold": 0.5,
            "feature_schema_version": record["feature_schema_version"],
            "disclaimer": "Research prototype output; not a medical device. "
                          "See /api/cardio/model-cards for limitations.",
        }
        if body.get("include_counterfactuals"):
            payload["counterfactuals"] = _cf.counterfactuals_for(
                model_id, frame, top_k=3)["counterfactuals"]
        h._send(200, json.dumps(payload), request_id=request_id)
        h._finish(timer, request_id, "POST", path, 200)
    except FileNotFoundError:
        h._send(503, json.dumps({"error": "cardio_not_ready",
                                 "detail": "model artifacts not trained"}),
                request_id=request_id)
        h._finish(timer, request_id, "POST", path, 503, "not_ready")
    except Exception:
        log_event("internal_error", request_id=request_id, route="cardio-predict")
        h._send(500, json.dumps({"error": "internal_error", "request_id": request_id}),
                request_id=request_id)
        h._finish(timer, request_id, "POST", path, 500, "internal")
    return True
