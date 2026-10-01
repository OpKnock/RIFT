"""Track-A verify checklist (Phase 19): one command proves the product.

Runs every integrity, consistency, UI, API, and security check end to
end and prints PASS/FAIL per line:
``python -m rift.health.cardiovascular.verify``. Exit 0 only when all
checks pass. This is the pre-demo gate: run it before showing judges.
"""
from __future__ import annotations

import json
import os
import subprocess  # nosec B404 -- fixed argv below, no shell, no external input
import sys

CHECKS: list = []


def check(name):
    """Decorator registering a check returning (ok, detail)."""
    def wrap(fn):
        CHECKS.append((name, fn))
        return fn
    return wrap


def _require(condition: bool, message: str) -> None:
    """Fail a check loudly (asserts are banned: they vanish under -O)."""
    if not condition:
        raise ValueError(message)


@check("dataset hash matches manifest")
def _c_dataset():
    from . import dataset, pipeline
    info = pipeline.step_dataset()
    return True, info["source_hash"][:19] + "..."


@check("registry loads hash-verified (4 models + 4 calibrators)")
def _c_registry():
    from . import registry
    for target, model_id in registry.MODEL_IDS.items():
        registry.load_model(model_id)
        registry.load_calibrator(model_id)
    return True, "4 estimators + 4 calibrators verified"


@check("evaluation artifacts cross-consistent")
def _c_artifacts():
    from . import evaluate
    report = json.loads((evaluate.EVAL_DIR / "report.json").read_text())
    calibration = json.loads((evaluate.EVAL_DIR / "calibration.json").read_text())
    explain = json.loads((evaluate.EVAL_DIR / "explainability.json").read_text())
    cards = json.loads((evaluate.DATA_DIR / "site" / "model_cards.json").read_text())
    manifest = json.loads((evaluate.DATA_DIR / "manifests/dataset_manifest.json").read_text())
    _require(report["dataset_hash"] == manifest["source_hash"], "report/manifest hash drift")
    _require(set(report["targets"]) == set(calibration["models"]) == {"cad", "lad", "lcx", "rca"},
             "evaluation target sets disagree")
    _require(set(explain["targets"]) == {"cad", "lad", "lcx", "rca"}, "explainability targets disagree")
    _require([c["model_id"] for c in cards] == ["cad-v1", "lad-stenosis-v1",
                                                "lcx-stenosis-v1", "rca-stenosis-v1"],
             "model card set disagree")
    return True, "report/calibration/explainability/cards agree"


@check("UI mirrors byte-identical to sources")
def _c_mirrors():
    from . import cardio_site_data, evaluate
    pairs = [("demo_patients.json", evaluate.DATA_DIR / "site" / "demo_patients.json"),
             ("model_cards.json", evaluate.DATA_DIR / "site" / "model_cards.json"),
             ("report.json", evaluate.EVAL_DIR / "report.json"),
             ("calibration.json", evaluate.EVAL_DIR / "calibration.json"),
             ("explainability.json", evaluate.EVAL_DIR / "explainability.json")]
    ui = cardio_site_data.UI_DATA_DIR
    for name, src in pairs:
        _require((ui / name).read_bytes() == src.read_bytes(), "mirror drift: %s" % name)
    return True, "%d files pinned" % len(pairs)


@check("UI pages and scripts present and wired")
def _c_pages():
    from . import cardio_site_data
    ui = cardio_site_data.REPO_ROOT / "stitch-ui"
    _require("whatif-panel" in (ui / "coronary.html").read_text(encoding="utf-8"),
             "coronary.html missing what-if panel")
    _require("model_cards.json" in (ui / "live" / "cardio-dashboard.js").read_text(encoding="utf-8"),
             "dashboard not wired to model cards")
    pages = ["dashboard", "scenarios", "simulation", "runs", "experiments",
             "evidence", "incidents", "explainability", "settings",
             "coronary", "cardio-dashboard"]
    for page in pages:
        html = (ui / (page + ".html")).read_text(encoding="utf-8")
        _require('href="./coronary.html"' in html and 'href="./cardio-dashboard.html"' in html,
                 "Track A missing from %s nav" % page)
        _require(html.count("border-l-2 border-primary") == 1,
                 "nav active marker broken on %s" % page)
    return True, "coronary.html + cardio-dashboard.html wired; Track A in 11/11 navs"


@check("API smoke: models/report/cards/predict+safety")
def _c_api():
    os.environ["no_proxy"] = os.environ.get("no_proxy", "") + ",127.0.0.1,localhost"
    os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",127.0.0.1,localhost"
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    from rift.api import Handler
    from . import evaluate, schemas
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def url(path: str) -> str:
        # Loopback only: host is a constant, path must be absolute.
        _require(path.startswith("/"), "refusing non-absolute path")
        return "http://127.0.0.1:%d%s" % (port, path)

    try:
        def get(path):
            # Loopback URL built by url() above, never from input.
            with urllib.request.urlopen(url(path), timeout=60) as response:  # nosec B310
                return json.loads(response.read().decode())
        def post(path, payload):
            body = json.dumps(payload, default=str).encode()
            request = urllib.request.Request(
                url(path), data=body, method="POST",
                headers={"Content-Type": "application/json"})
            # Loopback URL built by url() above, never from input.
            with urllib.request.urlopen(request, timeout=120) as response:  # nosec B310
                return json.loads(response.read().decode())
        _require(len(get("/api/cardio/models")["models"]) == 4, "models endpoint short")
        _require(set(get("/api/cardio/report")["targets"]) == {"cad", "lad", "lcx", "rca"},
                 "report endpoint targets disagree")
        _require(len(get("/api/cardio/model-cards")) == 4, "model-cards endpoint short")
        import pandas as pd
        row = pd.read_csv(evaluate.DATA_DIR / "processed" / "test.csv").iloc[0]
        predictors = {c: (row[c].item() if hasattr(row[c], "item") else row[c])
                      for c in schemas.PREDICTOR_COLUMNS}
        answer = post("/api/cardio/predict", {"model_id": "cad-v1",
                                              "predictors": predictors})
        _require(answer["safety"]["safe_to_show"] is True, "in-distribution CAD refused")
        rca = post("/api/cardio/predict", {"model_id": "rca-stenosis-v1",
                                           "predictors": predictors})
        _require(any("NOT decision-grade" in w for w in rca["safety"]["warnings"]),
                 "RCA warning missing over HTTP")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
    return True, "4 endpoints + safety verdicts live"


@check("bandit clean over src/")
def _c_bandit():
    # Fixed argv, no shell, no external input: this is the CI security gate.
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-m", "bandit", "-r", "src", "-q"],
        capture_output=True, text=True, timeout=300)
    _require(proc.returncode == 0,
             "bandit findings: %s" % (proc.stdout[-500:] + proc.stderr[-500:]))
    return True, "zero issues"


def run_all() -> list:
    """Run every check; return [(name, ok, detail)]. Never raises."""
    results = []
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
            results.append((name, bool(ok), str(detail)))
        except Exception as exc:  # a check must report, not crash the run
            results.append((name, False, "%s: %s" % (type(exc).__name__, str(exc)[:200])))
    return results


def print_results(results: list) -> bool:
    width = max(len(name) for name, _, _ in results)
    all_ok = True
    for name, ok, detail in results:
        print("%s  %-*s  %s" % ("PASS" if ok else "FAIL", width, name, detail),
              flush=True)
        all_ok = all_ok and ok
    print("TRACK A VERIFY: %s (%d/%d)" % ("GREEN" if all_ok else "RED",
                                          sum(1 for _, ok, _ in results if ok),
                                          len(results)))
    return all_ok


if __name__ == "__main__":
    sys.exit(0 if print_results(run_all()) else 1)
