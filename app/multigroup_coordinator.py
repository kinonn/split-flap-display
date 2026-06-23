import time
from espnow_manager import ESPNowManager


_TIMEOUT_MS = 30_000


class MultiGroupCoordinator:
    def __init__(self, esp):
        self.esp = esp
        self._dispatches = {}

    def dispatch(self, segments, peer_macs):
        msg_id = self.esp.next_msg_id()
        now = time.ticks_ms()
        for i, (text, mac) in enumerate(zip(segments, peer_macs)):
            self._dispatches[(msg_id, i)] = {
                "sent_at_ms": now,
                "status": "sent" if i == 0 else "pending",
            }
            if i == 0:
                continue
            try:
                self.esp.send(mac, self.esp.encode_display(msg_id, text))
                self._dispatches[(msg_id, i)]["status"] = "sent"
            except Exception:
                self._dispatches[(msg_id, i)]["status"] = "error"
        return msg_id

    def poll_acks(self):
        now = time.ticks_ms()
        while True:
            msg = self.esp.recv()
            if msg is None:
                break
            sender, payload = msg
            if payload.get("type") != "ack":
                continue
            ack_id = int(payload.get("msg_id", 0))
            status = "ok" if payload.get("status") == "ok" else "error"
            for key in list(self._dispatches.keys()):
                if key[0] == ack_id:
                    self._dispatches[key]["status"] = "acked" if status == "ok" else "error"

        for entry in self._dispatches.values():
            if entry["status"] in ("pending", "sent"):
                if time.ticks_diff(now, entry["sent_at_ms"]) > _TIMEOUT_MS:
                    entry["status"] = "timeout"
        return self._latest_status()

    def _latest_status(self):
        latest = {}
        for (msg_id, group_index), entry in self._dispatches.items():
            if group_index not in latest or latest[group_index][0] < msg_id:
                latest[group_index] = (msg_id, entry["status"])
        return {g: s for g, (_, s) in latest.items()}