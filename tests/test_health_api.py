"""Twin API contract: endpoint shape matches what the dashboard consumes."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from rift.api import Handler


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


def test_twin_demo_contract():
    with _Server() as server:
        with urllib.request.urlopen(server.url("/api/twin/demo?t=10"), timeout=20) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode())
    for key in ("day_index", "patient_id", "state", "baseline", "deviations",
                "risk", "robustness", "guardian", "futures", "trajectories",
                "reasons", "meta", "ehr"):
        assert key in payload, f"missing dashboard key: {key}"
    assert payload["day_index"] == 10
    assert payload["risk"]["event_predicted"] is True
    assert len(payload["trajectories"]) == 4
    assert payload["meta"]["engine_version"] == "0.6.0"
    assert "NOT clinically validated" in payload["meta"]["dataset"]
    assert isinstance(payload["guardian"]["display_allowed"], bool)


def test_twin_demo_rejects_bad_day():
    import urllib.error

    with _Server() as server:
        for bad in ("99", "-1", "soon"):
            try:
                urllib.request.urlopen(server.url(f"/api/twin/demo?t={bad}"), timeout=10)
                raise AssertionError(f"t={bad} must be rejected")
            except urllib.error.HTTPError as exc:
                assert exc.code == 422
                assert json.loads(exc.read().decode())["error"] == "invalid twin request"
