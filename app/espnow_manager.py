try:
    import ujson as json
except ImportError:
    import json


MAX_FRAME_SIZE = 256
ESPNOW_PORT = 8432
FRAME_VERSION = 1


class EspNowError(Exception):
    pass


class SlaveRegistry:
    def __init__(self):
        self.slaves = {}
        self._mac_list = []
        self._next_gid = 0

    def register(self, mac_string, module_count):
        if len(mac_string) != 17:
            raise EspNowError("Malformed MAC")
        if module_count < 1 or module_count > 8:
            raise EspNowError("Module count must be 1-8")
        gid = self._next_gid
        d = {"count": module_count, "group_id": gid}
        self.slaves[mac_string] = d
        if mac_string not in self._mac_list:
            self._mac_list.append(mac_string)
        self._next_gid += 1
        return gid

    def remove(self, mac_string):
        if mac_string in self.slaves:
            del self.slaves[mac_string]
            self._mac_list = [m for m in self._mac_list if m in self.slaves]

    def get_count(self):
        return len(self.slaves)

    def iter_slaves(self):
        for mac_str in self._mac_list:
            if mac_str in self.slaves:
                info = self.slaves[mac_str]
                yield mac_str, info["count"], info["group_id"]

    def items(self):
        out = []
        for mac, mc, gid in self.iter_slaves():
            out.append({"mac": mac, "modules": mc, "group_id": gid})
        return out

    def get_group_id(self, mac_string):
        if mac_string in self.slaves:
            return self.slaves[mac_string]["group_id"]
        return None


class EspNowManager:
    def __init__(self, settings=None):
        self.settings = settings
        self.station = None
        self.mac_bytes = b'\x00' * 6
        self.registry = SlaveRegistry()
        self._ip_address = "0.0.0.0"
        self.receive_frame = None
        self.on_ack_received = None

    def start_master(self):
        try:
            import network as _net
            self.station = _net.WLAN(_net.STA_IF)
            if not self.station.active():
                self.station.active(True)
        except Exception:
            raise EspNowError("Failed to start station")
        self.mac_bytes = bytes(self.station.config('mac')[:6])
        ip_info = self.station.ifconfig()
        if len(ip_info) >= 1:
            self._ip_address = str(ip_info[0])

    def start_slave(self):
        try:
            import network as _net
            self.station = _net.WLAN(_net.STA_IF)
            if not self.station.active():
                self.station.active(True)
        except Exception:
            raise EspNowError("Failed to start station")
        self.mac_bytes = bytes(self.station.config('mac')[:6])

    def register_slave(self, mac_string, module_count):
        return self.registry.register(mac_string, module_count)

    def remove_slave(self, mac_string):
        self.registry.remove(mac_string)

    def get_registered_mac_strings(self):
        return list(self.registry.slaves.keys())

    def iter_slaves(self):
        for mac, mc, gid in self.registry.iter_slaves():
            yield mac, mc, gid

    def items(self):
        return self.registry.items()

    def broadcast_command(self, command_dict):
        try:
            import socket as _sock
            payload_json = json.dumps(command_dict).encode('utf-8')[:256]
            plen = len(payload_json)
            if plen == 0:
                return False
            buf = bytearray(10 + plen)
            idx = 0
            buf[idx] = 0xAA; idx += 1
            buf[idx] = 0xBB; idx += 1
            buf[idx] = FRAME_VERSION; idx += 1
            buf[idx] = plen; idx += 1
            for b in self.mac_bytes:
                buf[idx] = b; idx += 1
            for i, pb in enumerate(payload_json):
                buf[idx + i] = pb
            target_ip = "255.255.255.255"
            sock = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
            sock.setblocking(True)
            try:
                sock.sendto(buf[:10 + plen], (target_ip, 8432))
                sock.close()
                return True
            except Exception:
                return False
        except Exception:
            return False

    def build_display_frame(self, group_index, text):
        d = {"cmd": "display", "group_id": group_index}
        d["data"] = text[:8]
        d["version"] = FRAME_VERSION
        return d

    def build_ack_payload(self):
        return {"cmd": "ack", "status": "ok"}

    def parse_frame(self, data_array):
        try:
            if len(data_array) < 4:
                return None
            if data_array[0] != 0xAA:
                return None
            if data_array[1] != 0xBB:
                return None
            plen = int(data_array[3])
            dbuf = bytes(data_array[4:])
            if len(dbuf) < plen:
                return None
            pstr = dbuf[:plen].decode('utf-8')
            cmd_dict = json.loads(pstr)
            frame_type = cmd_dict.get('cmd', '')
            if frame_type in ('display', 'home', 'test'):
                if self.receive_frame is not None:
                    try:
                        self.receive_frame(cmd_dict)
                    except Exception:
                        pass
            elif frame_type == 'ack':
                if self.on_ack_received is not None:
                    try:
                        self.on_ack_received('unknown_mac', cmd_dict)
                    except Exception:
                        pass
            return frame_type
        except Exception:
            return None
