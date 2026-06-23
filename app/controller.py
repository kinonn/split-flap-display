try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    from machine import reset
except ImportError:
    def reset():
        raise SystemExit

import time

import timekeeper
import wifi_manager
from display import MAX_RPM


MODE_SINGLE = 0
MODE_MULTI = 1
MODE_DATE = 2
MODE_TIME = 3
MODE_MULTI_GROUP = 4
MODE_RANDOM = 5


class DisplayController:
    def __init__(self, settings, display, mqtt):
        self.settings = settings
        self.display = display
        self.mqtt = mqtt

        self.centering = True
        self.input_string = ""
        self.multi_words = []
        self.multi_word_delay_ms = 1000
        self.multi_word_index = 0
        self.last_switch_multi = time.ticks_ms()
        self.multi_group_text = ""
        self.multi_group_segments = []
        self.multi_group_centering = True
        self.multi_group_coordinator = None
        self.last_check_datetime = time.ticks_ms()
        self.last_check_wifi = time.ticks_ms()
        self.written_string = ""

        self.check_datetime_interval_ms = 250
        self.wifi_check_interval_ms = 1000
        self.reboot_required = False

    def set_single_text(self, word, delay_ms=1000, centering=True):
        self.input_string = word
        self.multi_word_delay_ms = delay_ms
        self.centering = bool(centering)
        self.settings.set("mode", MODE_SINGLE)

    def set_multi_text(self, words, delay_ms=1000, centering=True):
        self.multi_words = list(words)
        self.multi_word_index = 0
        self.last_switch_multi = time.ticks_ms()
        self.multi_word_delay_ms = delay_ms
        self.centering = bool(centering)
        self.settings.set("mode", MODE_MULTI)

    def set_multi_group_text(self, text, centering=True):
        """Split text into per-group segments and store locally for the master."""
        text = str(text)
        counts = self.settings.get_int_vector(
            "groupModuleCounts", self.settings.get_int("numGroups"), fill=0
        )
        if not counts:
            counts = [self.display.num_modules]
        total = sum(counts)
        if total == 0:
            total = self.display.num_modules
            counts = [self.display.num_modules]

        if len(text) < total:
            text = text + " " * (total - len(text))
        elif len(text) > total:
            text = text[:total]

        segments = []
        offset = 0
        for c in counts:
            segments.append(text[offset:offset + c])
            offset += c

        self.multi_group_text = text
        self.multi_group_segments = segments
        self.multi_group_centering = bool(centering)
        self.settings.set("mode", MODE_MULTI_GROUP)

    def request_reconnect(self):
        wifi_manager.request_reconnect()

    def request_reboot(self):
        self.reboot_required = True

    async def run(self):
        while True:
            self.mqtt.loop()
            mode = self.settings.get_int("mode")

            if mode == MODE_SINGLE:
                self._single_input_mode()
            elif mode == MODE_MULTI:
                self._multi_input_mode()
            elif mode == MODE_DATE:
                self._date_mode()
            elif mode == MODE_TIME:
                self._time_mode()
            elif mode == MODE_MULTI_GROUP:
                self._multi_group_mode()
            elif mode == MODE_RANDOM:
                self.display.test_random()
                await _sleep_ms(2500)

            self._check_wifi()
            self._reconnect_if_needed()
            await self._reboot_if_needed()
            await _sleep_ms(20)

    def _single_input_mode(self):
        if self.input_string != self.written_string:
            self.display.write_string(
                self.input_string,
                MAX_RPM,
                centering=self.centering,
            )
            self.written_string = self.input_string

    def _multi_input_mode(self):
        if not self.multi_words:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_switch_multi) <= self.multi_word_delay_ms:
            return

        word = self.multi_words[self.multi_word_index]
        if word != self.written_string:
            self.display.write_string(word, MAX_RPM, centering=self.centering)
            self.written_string = word

        self.last_switch_multi = now
        self.multi_word_index = (self.multi_word_index + 1) % len(self.multi_words)

    def _date_mode(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_check_datetime) <= self.check_datetime_interval_ms:
            return

        self.last_check_datetime = now
        value = timekeeper.render_format(
            self.settings.get_string("dateFormat"),
            context="date",
            max_len=self.display.num_modules,
        )
        if value != self.written_string:
            self.display.write_string(value, MAX_RPM)
            self.written_string = value

    def _time_mode(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_check_datetime) <= self.check_datetime_interval_ms:
            return

        self.last_check_datetime = now
        value = timekeeper.render_format(
            self.settings.get_string("timeFormat"),
            context="time",
            max_len=self.display.num_modules,
        )
        if value != self.written_string:
            self.display.write_string(value, MAX_RPM)
            self.written_string = value

    def _multi_group_mode(self):
        if not self.multi_group_segments:
            return
        first = self.multi_group_segments[0]
        if first != self.written_string:
            self.display.write_string(first, MAX_RPM, centering=self.multi_group_centering)
            self.written_string = first
        if self.multi_group_coordinator is not None:
            self.multi_group_coordinator.poll_acks()

    def _check_wifi(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_check_wifi) <= self.wifi_check_interval_ms:
            return

        wifi_manager.check_wifi(self.settings)
        self.last_check_wifi = now

    def _reconnect_if_needed(self):
        if not wifi_manager.consume_reconnect_request():
            return

        self.display.write_string("")
        connected = wifi_manager.configure(self.settings)

        if connected:
            self.display.write_string("OK")
            self.written_string = "OK"
            time.sleep_ms(500)
            self.display.write_string("")
            self.written_string = ""
        else:
            if self.display.num_modules == 8:
                self.display.write_string("Wifi Err")
                self.written_string = "Wifi Err"
            else:
                self.display.write_char("X")
                self.written_string = "X"

        self.mqtt.setup()

    async def _reboot_if_needed(self):
        if not self.reboot_required:
            return

        print("Reboot required. Restarting.")
        await _sleep_ms(1000)
        reset()


async def _sleep_ms(ms):
    if hasattr(asyncio, "sleep_ms"):
        await asyncio.sleep_ms(ms)
    else:
        await asyncio.sleep(ms / 1000)
