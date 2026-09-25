"""HTTP tests for clinician review endpoints: fail-closed, audited, counted."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from rift.api import Handler
from rift.health import reviews as reviews_module


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


def _post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, json.loads(response.read().decode())


def test_review_lifecycle_over_http(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    reviews_module.ledger.reset()
    with _Server() as server:
        status, body = _post(server.url("/api/twin/reviews"), {
            "action": "ACCEPT", "evidence_id": "ev-1", "reviewer_id": "dr-a"})
        assert status == 201, body
        assert body["review_id"]
        status, body = _post(server.url("/api/twin/reviews"), {
            "action": "OVERRIDE", "evidence_id": "ev-1", "reviewer_id": "dr-b"})
        assert status == 400
        assert "rationale" in body["detail"]
        status, body = _post(server.url("/api/twin/reviews"), {
            "action": "MAYBE", "evidence_id": "ev-1", "reviewer_id": "dr-b"})
        assert status == 400
        status, body = _post(server.url("/api/twin/reviews"), {
            "action": "REJECT", "reviewer_id": "dr-b", "rationale": "artifact"})
        assert status == 400
        status, body = _get(server.url("/api/twin/reviews"))
        assert status == 200
        assert body["stats"]["total"] == 1
        assert body["stats"]["by_action"]["ACCEPT"] == 1
        assert body["reviews"][0]["evidence_id"] == "ev-1"


def test_review_override_chain_over_http(monkeypatch):
    monkeypatch.delenv("RIFT_API_TOKEN", raising=False)
    monkeypatch.delenv("RIFT_SUPABASE_JWT_SECRET", raising=False)
    reviews_module.ledger.reset()
    with _Server() as server:
        _, first = _post(server.url("/api/twin/reviews"), {
            "action": "ACCEPT", "evidence_id": "ev-9", "reviewer_id": "dr-a"})
        status, second = _post(server.url("/api/twin/reviews"), {
            "action": "OVERRIDE", "evidence_id": "ev-9", "reviewer_id": "dr-b",
            "rationale": "bedside exam overrides", "supersedes": first["review_id"]})
        assert status == 201, second
        assert second["supersedes"] == first["review_id"]
