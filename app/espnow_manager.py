try:
    import ujson as json
except ImportError:
    import json

try:
    import network
    import espnow
except ImportError:
    network = None
    espnow = None

from settings import parse_int_csv, parse_string_list


MAX_ESPNOW_GROUPS = 6
MAX_GROUP_MODULES = 8


class EspNowCoordinator:
    def __init__(self, settings, display):
        self.settings = settings
        self.display = display
        self.enabled = False
        self.esp = None
        self.wlan = None
        self.txn = 0
        self.pending = {}
        self.last_status = {
            "enabled": False,
            "message": "",
            "groups": [],
        }

    def setup(self):
        self.enabled = False
        self.esp = None
        self.pending = {}

        if espnow is None or network is None:
            print("[ESP-NOW] Not available in this firmware")
            return

        try:
            self.wlan = network.WLAN(network.STA_IF)
            self.wlan.active(True)
            self.esp = espnow.ESPNow()
            self.esp.active(True)
            self.enabled = True
            self._register_peers()
            print("[ESP-NOW] Ready")
        except Exception as exc:
            self.enabled = False
            print("[ESP-NOW] Setup failed:", exc)

    def is_master(self):
        return bool(self.settings.get_int("masterEnabled"))

    def status(self):
        return self.last_status.copy()

    def poll(self):
        if not self.enabled or self.esp is None:
            return

        while True:
            try:
                peer, payload = self.esp.recv(0)
            except Exception as exc:
                print("[ESP-NOW] Receive failed:", exc)
                return

            if not peer:
                return

            self._handle_packet(peer, payload)

    def display_message(self, message, speed, centering=True):
        if not self.is_master():
            self.display.write_string(message, speed, centering=centering)
            return

        groups = self._groups()
        if not groups:
            self.display.write_string(message, speed, centering=centering)
            return

        prepared = self._prepare_message(message, groups, centering)
        offset = 0
        self.txn = (self.txn + 1) % 1000000
        txn = self.txn
        statuses = []

        for group in groups:
            segment = prepared[offset : offset + group["modules"]]
            offset += group["modules"]

            entry = {
                "id": group["id"],
                "modules": group["modules"],
                "segment": segment,
                "ack": group["local"],
                "error": "",
            }

            if group["local"]:
                self.display.write_string(segment, speed, centering=False)
            elif self.enabled and group["mac"]:
                entry["ack"] = False
                self.pending[group["id"]] = txn
                try:
                    self.esp.send(
                        group["mac"],
                        json.dumps(
                            {
                                "type": "display",
                                "id": txn,
                                "group": group["id"],
                                "segment": segment,
                            }
                        ).encode(),
                    )
                except Exception as exc:
                    entry["error"] = str(exc)
                    print("[ESP-NOW] Send failed:", exc)
            else:
                entry["error"] = "ESP-NOW is not ready"

            statuses.append(entry)

        self.last_status = {
            "enabled": True,
            "message": message,
            "transaction": txn,
            "groups": statuses,
        }

    def _handle_packet(self, peer, payload):
        try:
            if isinstance(payload, bytes):
                payload = payload.decode()
            data = json.loads(payload)
        except Exception as exc:
            print("[ESP-NOW] Ignoring invalid packet:", exc)
            return

        packet_type = data.get("type")
        if packet_type == "ack":
            self._handle_ack(data)
        elif packet_type == "display":
            self._handle_display(peer, data)

    def _handle_ack(self, data):
        group_id = int(data.get("group", 0))
        txn = int(data.get("id", -1))
        if self.pending.get(group_id) != txn:
            return

        self.pending.pop(group_id, None)
        for group in self.last_status.get("groups", []):
            if group.get("id") == group_id:
                group["ack"] = True
                group["error"] = ""
                break

    def _handle_display(self, peer, data):
        if self.is_master():
            return

        group_id = int(data.get("group", 0))
        if group_id != self.settings.get_int("groupId"):
            return

        segment = str(data.get("segment", ""))
        self.display.write_string(
            segment,
            self.settings.get_float("maxVel"),
            centering=False,
        )

        try:
            try:
                self.esp.add_peer(peer)
            except OSError:
                pass
            self.esp.send(
                peer,
                json.dumps(
                    {
                        "type": "ack",
                        "id": int(data.get("id", 0)),
                        "group": group_id,
                    }
                ).encode(),
            )
        except Exception as exc:
            print("[ESP-NOW] Ack failed:", exc)

    def _register_peers(self):
        if not self.is_master() or self.esp is None:
            return

        for group in self._groups():
            if group["local"] or not group["mac"]:
                continue
            try:
                self.esp.add_peer(group["mac"])
            except OSError:
                pass
            except Exception as exc:
                print("[ESP-NOW] Peer add failed:", exc)

    def _groups(self):
        group_count = min(
            MAX_ESPNOW_GROUPS,
            max(1, self.settings.get_int("masterGroupCount")),
        )
        modules = parse_int_csv(self.settings.get("masterGroupModules", ""))
        macs = parse_string_list(self.settings.get_string("masterGroupMacs"))

        groups = []
        for index in range(group_count):
            if index == 0:
                module_count = self.display.num_modules
            elif index < len(modules):
                module_count = modules[index]
            else:
                module_count = MAX_GROUP_MODULES
            module_count = min(MAX_GROUP_MODULES, max(1, int(module_count)))

            mac = None
            if index < len(macs) and macs[index]:
                mac = _mac_to_bytes(macs[index])

            groups.append(
                {
                    "id": index + 1,
                    "modules": module_count,
                    "mac": mac,
                    "local": index == 0,
                }
            )

        return groups

    def _prepare_message(self, message, groups, centering):
        total_modules = sum(group["modules"] for group in groups)
        text = str(message)[:total_modules]

        if centering:
            total_padding = total_modules - len(text)
            left = total_padding // 2
            right = total_padding - left
            return (" " * left) + text + (" " * right)

        return text + (" " * (total_modules - len(text)))


def _mac_to_bytes(value):
    compact = str(value).replace(":", "").replace("-", "")
    mac = bytearray()
    for index in range(0, 12, 2):
        mac.append(int(compact[index : index + 2], 16))
    return bytes(mac)
