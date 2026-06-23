import sys, os, types

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, APP_DIR)

# ---- Stub MicroPython-only modules so controller.py imports on CPython ----
for name in ("machine", "micropython", "utime", "urandom", "network", "ntptime"):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

mp = sys.modules["micropython"]
mp.const = lambda x: x
for _attr in ("native", "viper", "asm_thumb", "opt_level"):
    setattr(mp, _attr, lambda *a, **k: (lambda f: f))

sys.modules["machine"].I2C = None
sys.modules["machine"].Pin = None

# ---- Stub MicroPython-style time functions on the real `time` module so
#      `controller.__init__` can call `time.ticks_ms()` / `time.ticks_diff()`.
import time as _time
_t_time = _time.time


def _ticks_ms():
    return int(_t_time() * 1000)


def _ticks_diff(a, b):
    return a - b


def _sleep_ms(ms):
    _time.sleep(ms / 1000.0)


_time.ticks_ms = _ticks_ms
_time.ticks_diff = _ticks_diff
_time.sleep_ms = _sleep_ms

# ---- splitflap_module.py uses @micropython.native but only does
#      `from micropython import const`, which leaves `micropython` unbound in
#      its module globals. Wrap SourceFileLoader.exec_module to inject
#      `micropython` into every loaded module's namespace before exec.
import importlib.machinery as _ilm
_original_exec = _ilm.SourceFileLoader.exec_module


def _patched_exec(self, module):
    module.__dict__.setdefault("micropython", mp)
    _original_exec(self, module)


_ilm.SourceFileLoader.exec_module = _patched_exec


from controller import DisplayController  # noqa: E402


class FakeSettings:
    def __init__(self, counts):
        self._counts = counts
        self._mode = 0

    def get_int(self, key):
        if key == "numGroups":
            return len(self._counts)
        return 0

    def get_int_vector(self, key, length=None, fill=0):
        vals = list(self._counts)
        if length is not None:
            while len(vals) < length:
                vals.append(fill)
            return vals[:length]
        return vals

    def set(self, key, value):
        if key == "mode":
            self._mode = value


class FakeDisplay:
    num_modules = 0


def make_controller(counts):
    s = FakeSettings(counts)
    return DisplayController(s, FakeDisplay(), None)


def test_split_three_groups():
    c = make_controller([4, 3, 7])
    c.set_multi_group_text("HELLWORLD12345")
    assert c.multi_group_segments == ["HELL", "WOR", "LD12345"]


def test_split_pads_short_text():
    c = make_controller([3, 3])
    c.set_multi_group_text("HI")
    assert c.multi_group_segments == ["HI ", "   "]


def test_split_truncates_long_text():
    c = make_controller([2, 2])
    c.set_multi_group_text("TOOLONG")
    assert c.multi_group_segments == ["TO", "OL"]


def test_sets_mode_to_multi_group():
    c = make_controller([4])
    c.set_multi_group_text("OK")
    assert c.multi_group_segments == ["OK  "]
    from controller import MODE_MULTI_GROUP
    assert c.settings._mode == MODE_MULTI_GROUP
