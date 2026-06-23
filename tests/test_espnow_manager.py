import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from espnow_manager import ESPNowManager


def test_format_mac():
    assert ESPNowManager.format_mac(b"\xaa\xbb\xcc\xdd\xee\xff") == "aa:bb:cc:dd:ee:ff"


def test_parse_mac_roundtrip():
    s = "aa:bb:cc:dd:ee:ff"
    assert ESPNowManager.parse_mac(s) == b"\xaa\xbb\xcc\xdd\xee\xff"


def test_parse_mac_rejects_garbage():
    import pytest
    with pytest.raises(ValueError):
        ESPNowManager.parse_mac("not-a-mac")


def test_msg_id_monotonic():
    m = ESPNowManager()
    ids = [m.next_msg_id() for _ in range(5)]
    assert ids == [1, 2, 3, 4, 5]


def test_encode_decode_display_roundtrip():
    m = ESPNowManager()
    payload = m.encode_display(42, "HELLO")
    decoded = m.decode(payload)
    assert decoded == {"type": "display", "msg_id": 42, "text": "HELLO"}


def test_encode_decode_ack_roundtrip():
    m = ESPNowManager()
    payload = m.encode_ack(42, "ok")
    assert m.decode(payload) == {"type": "ack", "msg_id": 42, "status": "ok"}
