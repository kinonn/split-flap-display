import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import multigroup_coordinator as mgc


class FakeESP:
    """Minimal stand-in for ESPNowManager — records sends, returns queued recv messages."""
    def __init__(self, recv_queue=None):
        self.sent = []
        self._recv_queue = recv_queue or []
        self._msg_id_seq = 100

    def next_msg_id(self):
        mid = self._msg_id_seq
        self._msg_id_seq += 1
        return mid

    def encode_display(self, msg_id, text):
        return "DISPLAY|%d|%s" % (msg_id, text)

    def encode_ack(self, msg_id, status="ok"):
        return "ACK|%d|%s" % (msg_id, status)

    def send(self, peer_mac, message):
        self.sent.append((peer_mac, message))

    def recv(self):
        if not self._recv_queue:
            return None
        return self._recv_queue.pop(0)


def _stub_time():
    """Replace time.ticks_ms / time.ticks_diff with deterministic stubs."""
    import multigroup_coordinator as _mgc
    _now = {"t": 1000}

    def ticks_ms():
        return _now["t"]

    def ticks_diff(a, b):
        return a - b

    _mgc.time.ticks_ms = ticks_ms
    _mgc.time.ticks_diff = ticks_diff
    return _now


def test_dispatch_returns_msg_id_and_sends_to_slaves():
    _stub_time()
    esp = FakeESP()
    coord = mgc.MultiGroupCoordinator(esp)
    msg_id = coord.dispatch(
        ["HELLO", "WORLD"],
        [None, b"\x11\x22\x33\x44\x55\x66"],
    )
    assert isinstance(msg_id, int)
    # Only one send (group 0 is master, no send)
    assert len(esp.sent) == 1
    peer, payload = esp.sent[0]
    assert peer == b"\x11\x22\x33\x44\x55\x66"
    assert payload.startswith("DISPLAY|")


def test_poll_acks_marks_acked_on_ok():
    _stub_time()
    ack_msg = ("host", {"type": "ack", "msg_id": 0, "status": "ok"})
    # We don't know the msg_id yet — use a sentinel via the dispatch path
    esp = FakeESP()
    coord = mgc.MultiGroupCoordinator(esp)
    # Intercept next_msg_id so we know the value
    esp._msg_id_seq = 7777
    coord.dispatch(["A", "B"], [None, b"\xaa\xbb"])
    # Now feed an ack for that msg_id (7777)
    esp._recv_queue.append((b"\xaa\xbb", {"type": "ack", "msg_id": 7777, "status": "ok"}))
    statuses = coord.poll_acks()
    assert statuses.get(1) == "acked"


def test_poll_acks_marks_error_on_error_status():
    _stub_time()
    esp = FakeESP()
    coord = mgc.MultiGroupCoordinator(esp)
    esp._msg_id_seq = 8888
    coord.dispatch(["A", "B"], [None, b"\xaa\xbb"])
    esp._recv_queue.append((b"\xaa\xbb", {"type": "ack", "msg_id": 8888, "status": "error"}))
    statuses = coord.poll_acks()
    assert statuses.get(1) == "error"


def test_timeout_after_30s():
    clock = _stub_time()
    esp = FakeESP()
    coord = mgc.MultiGroupCoordinator(esp)
    esp._msg_id_seq = 9999
    coord.dispatch(["A", "B"], [None, b"\xaa\xbb"])
    # Advance clock past 30s
    clock["t"] = 1000 + 31_000
    statuses = coord.poll_acks()
    assert statuses.get(1) == "timeout"


def test_latest_status_wins_per_group():
    _stub_time()
    esp = FakeESP()
    coord = mgc.MultiGroupCoordinator(esp)
    esp._msg_id_seq = 100
    coord.dispatch(["A", "B"], [None, b"\xaa\xbb"])
    esp._msg_id_seq = 200
    coord.dispatch(["C", "D"], [None, b"\xaa\xbb"])
    statuses = coord.poll_acks()
    # Two dispatches, both group 1 is the slave — latest status is "sent"
    assert statuses.get(1) == "sent"


def test_master_group_0_no_send():
    _stub_time()
    esp = FakeESP()
    coord = mgc.MultiGroupCoordinator(esp)
    coord.dispatch(["ONLY"], [None])
    assert esp.sent == []  # master never sends to itself
    statuses = coord.poll_acks()
    assert statuses.get(0) == "sent"