"""EventBus delivery semantics: drops (never crashes) on slow subscribers."""
import asyncio

from rift import realtime
from rift.realtime import (
    CrossSourceConsistencyChecker,
    EventBus,
    ReconciliationEngine,
    ReoptimizationTrigger,
)


def test_no_websocket_transport_exists():
    # SSE is the only supported transport: no WS handler may linger for
    # contributors to mistake as supported.
    assert not hasattr(realtime, "WSConnection")
    import inspect

    src = inspect.getsource(realtime)
    assert "WSConnection" not in src


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_publish_drops_on_full_async_queue_without_loop_error():
    errors: list = []
    loop = asyncio.new_event_loop()
    try:
        loop.set_exception_handler(lambda _loop, ctx: errors.append(ctx))
        bus = EventBus()
        bus.set_loop(loop)
        q = bus.subscribe("t")
        for _ in range(100):
            q.put_nowait({"fill": True})

        async def go():
            bus.publish("t", {"x": 1})
            # Let the scheduled loop callbacks run.
            for _ in range(3):
                await asyncio.sleep(0)

        loop.run_until_complete(go())
        assert errors == [], errors
        assert q.qsize() == 100
    finally:
        loop.close()


def test_publish_after_loop_close_does_not_raise():
    loop = asyncio.new_event_loop()
    bus = EventBus()
    bus.set_loop(loop)
    bus.subscribe("t")
    loop.close()
    assert bus.publish("t", {"x": 1}) == 0


def test_failed_rule_is_explicit_failed_state():
    engine = ReconciliationEngine(CrossSourceConsistencyChecker(), EventBus())

    def bad_rule(_checks):
        raise RuntimeError("boom")

    engine.add_rule(bad_rule)
    actions = engine.run_reconciliation({})
    assert len(actions) == 1
    failed = actions[0]
    assert failed["status"] == "failed"
    assert failed["error_type"] == "RuntimeError"
    assert "rule" in failed
    assert "action" not in failed


def test_optimizer_failure_is_explicit_not_material():
    trigger = ReoptimizationTrigger(
        EventBus(),
        twin_factory=lambda: None,
        optimizer_fn=lambda _state: (_ for _ in ()).throw(ValueError("solver down")),
    )
    low = {"risk": {"risk": 0.1}, "guardian": {"action": "ALLOW"}}
    high = {"risk": {"risk": 0.9}, "guardian": {"action": "ALLOW"}}
    assert trigger.check_and_trigger(low) is None
    result = trigger.check_and_trigger(high)
    assert result is not None
    assert result["triggered"] is False
    assert result["status"] == "failed"
    assert result["error_type"] == "ValueError"


class _Stream:
    """Minimal SSE client over a raw socket (http.client buffers and its
    buffered reader wedges permanently after a timeout on newer Pythons;
    select + manual framing has neither problem)."""

    def __init__(self, port, topics):
        import socket

        self.sock = socket.create_connection(("127.0.0.1", port), timeout=25)
        self.sock.sendall(
            f"GET /api/events/stream?topics={topics} HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n".encode()
        )
        self.buf = b""
        head = self._recv_until(b"\r\n\r\n", timeout=25.0)
        assert head.startswith(b"HTTP/1.1 200") or head.startswith(b"HTTP/1.0 200"), head[:60]

    def _recv_until(self, marker, timeout):
        import select
        import time

        deadline = time.monotonic() + timeout
        while marker not in self.buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([self.sock], [], [], remaining)
            if not ready:
                break
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            self.buf += chunk
        out, sep, rest = self.buf.partition(marker)
        if sep:
            self.buf = rest
            return out
        out, self.buf = self.buf, b""
        return out

    def next_frame(self, timeout=20.0):
        raw = self._recv_until(b"\n\n", timeout)
        return [l.decode("utf-8", errors="replace").rstrip("\r")
                for l in raw.split(b"\n") if l.strip()]

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def _post_json(port, path, payload):
    import json
    import urllib.request

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode())


def test_sse_connect_publish_heartbeat_reconnect():
    import threading
    from http.server import ThreadingHTTPServer

    from rift.api import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        stream = _Stream(port, "incidents.lifecycle")
        first = stream.next_frame()
        assert any(l.startswith("event: connected") for l in first), first

        status, _ = _post_json(port, "/api/operations/incidents", {
            "user_id": "sse-probe", "type": "manual", "title": "sse lifecycle probe",
        })
        assert status == 201
        got = []
        for _ in range(20):
            for line in stream.next_frame(timeout=5.0):
                got.append(line)
            if any("incidents.lifecycle" in l for l in got):
                break
        assert any("incidents.lifecycle" in l for l in got), got

        # Idle keepalive: the server must emit a heartbeat comment
        # rather than letting the connection go silent.
        beat = []
        for _ in range(6):
            for line in stream.next_frame(timeout=5.0):
                beat.append(line)
            if any(l.startswith(":") for l in beat):
                break
        assert any(l.startswith(":") for l in beat), beat

        # Disconnect + reconnect: cleanup must not break the bus.
        stream.close()
        stream2 = _Stream(port, "incidents.lifecycle")
        again = stream2.next_frame()
        assert any(l.startswith("event: connected") for l in again), again
        stream2.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_publish_drops_on_full_sync_queue():
    import queue as _queue

    bus = EventBus()
    q = bus.subscribe_sync("t", maxsize=2)
    assert isinstance(q, _queue.Queue)
    q.put_nowait({"a": 1})
    q.put_nowait({"b": 2})
    assert bus.publish("t", {"c": 3}) == 0
    assert q.qsize() == 2
