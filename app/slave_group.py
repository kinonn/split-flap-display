"""Slave group firmware for split-flap multi-group display coordination.
Each slave listens on UDP port ESP-NOW_PORT, displays its segment, then ACKs."""


class SlaveGroupState:
    manager = None
    display = None
    settings = None
    my_mac_string = "unknown"
    last_command = None
    status = "idle"


class SlaveGroupManager:
    def __init__(self, manager, display=None, settings=None):
        self.manager = manager
        self.display = display
        self.settings = settings
        self.my_mac = "unknown"
        self.last_cmd = None
        self.status = "idle"

    def start(self):
        pass

    def set_mac(self, mac_str_or_bytes):
        if isinstance(mac_str_or_bytes, bytes) and len(mac_str_or_bytes) == 6:
            parts = ["%02x" % b for b in mac_str_or_bytes]
            self.my_mac = ":".join(parts)
        elif isinstance(mac_str_or_bytes, str):
            self.my_mac = mac_str_or_bytes

    def on_frame_received(self, cmd_dict):
        cmd = cmd_dict.get("cmd", "")
        if cmd == "display":
            data = cmd_dict.get("data", "")
            gid = cmd_dict.get("group_id", 0)
            self._dispatch_display(data, int(gid))
        elif cmd == "home":
            self._dispatch_home()
        elif cmd == "test":
            self._dispatch_test()

    def _send_ack(self):
        try:
            if SlaveGroupState.manager is not None:
                ack = {"cmd": "ack", "status": "ok"}
                SlaveGroupState.manager.broadcast_command(ack)
        except Exception:
            pass

    def _dispatch_display(self, text, group_id):
        try:
            if self.display is None:
                return False
            seg = str(text)[:8]
            for char in seg:
                print("[Group %d]" % group_id, repr(char))
            self.status = "done"
            self._send_ack()
            return True
        except Exception as e:
            try:
                print("Display error:", str(e))
            except Exception:
                pass
            self.status = "error"
            return False

    def _dispatch_home(self):
        try:
            if self.display is None:
                return False
            print("[Group %04s]" % self.my_mac, "Homing...")
            self.status = "done"
            self._send_ack()
            return True
        except Exception:
            self.status = "error"
            return False

    def _dispatch_test(self):
        try:
            if self.display is None:
                return False
            print("[Group %04s]" % self.my_mac, "Test pattern...")
            self.status = "done"
            self._send_ack()
            return True
        except Exception:
            self.status = "error"
            return False

    def check_all_acked(self):
         return SlaveGroupState.manager is not None

    def send_ack(self):
        try:
            if self.display is None:
                return False
            print("ACK sent to master from", self.my_mac)
            self.status = "done"
            return True
        except Exception:
            pass
        return False
