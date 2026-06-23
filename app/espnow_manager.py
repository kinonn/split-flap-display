try:
    import ujson as json
except ImportError:
    import json

try:
    from espnow import ESPNow
except ImportError:
    ESPNow = None

try:
    import network
except ImportError:
    network = None


_MSG_DISPLAY = "display"
_MSG_ACK = "ack"


class ESPNowManager:
    def __init__(self):
        self._esp = None
        self._next_msg_id = 1

    # --- Pure-Python helpers (unit-testable) ---

    @staticmethod
    def format_mac(mac_bytes):
        return ":".join("%02x" % b for b in mac_bytes)

    @staticmethod
    def parse_mac(mac_str):
        parts = mac_str.strip().split(":")
        if len(parts) != 6:
            raise ValueError("MAC must have 6 hex octets")
        return bytes(int(p, 16) for p in parts)

    def next_msg_id(self):
        mid = self._next_msg_id
        self._next_msg_id = (self._next_msg_id + 1) & 0xFFFFFFFF
        if self._next_msg_id == 0:
            self._next_msg_id = 1
        return mid

    def encode_display(self, msg_id, text):
        return json.dumps({"type": _MSG_DISPLAY, "msg_id": msg_id, "text": text})

    def encode_ack(self, msg_id, status="ok"):
        return json.dumps({"type": _MSG_ACK, "msg_id": msg_id, "status": status})

    def decode(self, payload):
        if isinstance(payload, bytes):
            payload = payload.decode()
        return json.loads(payload)

    # --- Hardware-bound (only callable on ESP32) ---

    def init(self):
        if ESPNow is None or network is None:
            raise RuntimeError("espnow/network unavailable on this platform")
        sta = network.WLAN(network.STA_IF)
        if not sta.active():
            sta.active(True)
        self._esp = ESPNow()
        self._esp.active(True)
        try:
            self._esp.set_pmk(b"\x00" * 16)
        except Exception:
            pass

    @property
    def my_mac(self):
        if network is None:
            return b"\x00" * 6
        sta = network.WLAN(network.STA_IF)
        return sta.config("mac")

    def add_peer(self, mac_bytes, lmk=None):
        if self._esp is None:
            raise RuntimeError("ESPNowManager not initialised")
        kwargs = {}
        if lmk is not None:
            kwargs["lmk"] = lmk
        try:
            self._esp.add_peer(mac_bytes, **kwargs)
        except OSError:
            pass

    def remove_peer(self, mac_bytes):
        if self._esp is None:
            return
        try:
            self._esp.del_peer(mac_bytes)
        except OSError:
            pass

    def send(self, peer_mac, message):
        if self._esp is None:
            raise RuntimeError("ESPNowManager not initialised")
        if isinstance(message, str):
            message = message.encode()
        return self._esp.send(peer_mac, message)

    def recv(self):
        if self._esp is None:
            return None
        try:
            host, msg = self._esp.recv(0)
        except Exception:
            return None
        if msg is None:
            return None
        try:
            return host, self.decode(msg)
        except ValueError:
            return None
