"""Serving tests for the production React bundle at /app/*.

Covers: exact asset serving with content types, SPA fallback for
BrowserRouter deep links, path-traversal rejection, and the honest 404
when no bundle was built (local dev serves Vite on :5173 instead).
"""

import json
import urllib.request
import urllib.error

import rift.api as api_module
from rift.api import Handler
from http.server import ThreadingHTTPServer
import threading


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


def _get_raw(url):
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def _make_dist(tmp_path):
    dist = tmp_path / "frontend-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>app</body></html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "assets" / "style.css").write_text("body{}")
    (tmp_path / "web").mkdir()
    return tmp_path


def test_app_serves_bundle_and_spa_fallback(monkeypatch, tmp_path):
    _make_dist(tmp_path)
    monkeypatch.setattr(api_module, "FRONTEND_DIST", tmp_path / "frontend-dist")
    with _Server() as server:
        status, body, headers = _get_raw(server.url("/app/"))
        assert status == 200 and b"app" in body
        assert "text/html" in headers["Content-Type"]

        # BrowserRouter deep link falls back to index.html, not 404.
        status, body, _ = _get_raw(server.url("/app/experiments/abc"))
        assert status == 200 and b"app" in body

        status, body, headers = _get_raw(server.url("/app/assets/app.js"))
        assert status == 200 and "javascript" in headers["Content-Type"]

        status, body, headers = _get_raw(server.url("/app/assets/style.css"))
        assert status == 200 and "text/css" in headers["Content-Type"]


def test_app_rejects_traversal(monkeypatch, tmp_path):
    _make_dist(tmp_path)
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setattr(api_module, "FRONTEND_DIST", tmp_path / "frontend-dist")
    with _Server() as server:
        status, _, _ = _get_raw(server.url("/app/../secret.txt"))
        assert status == 404


def test_app_missing_bundle_is_honest_404(monkeypatch, tmp_path):
    (tmp_path / "web").mkdir()
    monkeypatch.setattr(api_module, "FRONTEND_DIST", tmp_path / "frontend-dist")
    with _Server() as server:
        status, raw, _ = _get_raw(server.url("/app/"))
        assert status == 404
        assert json.loads(raw.decode())["error"] == "frontend not built"
