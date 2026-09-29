"""Serving tests for the API-only service (React UI removed, Stitch builds it).

Covers: `/` returns the API index JSON (no redirect to a bundle that no
longer ships), and every `/app/*` path answers an honest JSON 404 without
touching the filesystem (nothing left to traverse).
"""

import json
import urllib.request
import urllib.error

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


def test_root_serves_api_index():
    with _Server() as server:
        status, raw, headers = _get_raw(server.url("/"))
        assert status == 200
        body = json.loads(raw.decode())
        assert body["service"] == "rift-engine"
        assert body["health"] == "/api/health"
        assert "application/json" in headers["Content-Type"]


def test_app_paths_are_honest_404():
    with _Server() as server:
        for path in ("/app/", "/app", "/app/experiments/abc", "/app/assets/app.js"):
            status, raw, _ = _get_raw(server.url(path))
            assert status == 404, path
            assert json.loads(raw.decode())["error"] == "web UI removed", path


def test_app_traversal_is_honest_404():
    with _Server() as server:
        status, raw, _ = _get_raw(server.url("/app/../secret.txt"))
        assert status == 404
        assert json.loads(raw.decode())["error"] == "web UI removed"
