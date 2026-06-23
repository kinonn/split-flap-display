try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from display import SplitFlapDisplay
from espnow_manager import ESPNowManager
from settings import Settings


class SlaveGroup:
    def __init__(self, settings):
        self.settings = settings
        self.display = SplitFlapDisplay(settings)
        self.esp = ESPNowManager()

    def _module_count_for_this_group(self):
        counts = self.settings.get_int_vector(
            "groupModuleCounts", self.settings.get_int("numGroups"), fill=0
        )
        idx = self.settings.get_int("groupIndex")
        if idx < len(counts):
            return counts[idx]
        return self.settings.get_int("moduleCount")

    def _override_module_count(self, count):
        if count <= 0:
            return
        original = self.settings.get_int

        def patched(key):
            if key == "moduleCount":
                return count
            return original(key)

        self.settings.get_int = patched

    async def run(self):
        count = self._module_count_for_this_group()
        self._override_module_count(count)

        self.display.init()
        self.display.home_to_string("S")

        self.esp.init()
        print("Slave MAC:", ESPNowManager.format_mac(self.esp.my_mac))

        while True:
            msg = self.esp.recv()
            if msg is None:
                await _sleep_ms(50)
                continue

            sender_mac, payload = msg
            if payload.get("type") != "display":
                continue

            text = str(payload.get("text", ""))
            msg_id = int(payload.get("msg_id", 0))

            try:
                self.display.write_string(text, centering=False)
                ack = self.esp.encode_ack(msg_id, "ok")
            except Exception as exc:
                print("Slave display error:", exc)
                ack = self.esp.encode_ack(msg_id, "error")

            try:
                self.esp.send(sender_mac, ack)
            except Exception as exc:
                print("Slave ACK send failed:", exc)


async def _sleep_ms(ms):
    if hasattr(asyncio, "sleep_ms"):
        await asyncio.sleep_ms(ms)
    else:
        await asyncio.sleep(ms / 1000)
