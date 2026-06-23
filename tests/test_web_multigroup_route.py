import sys, os, types, json, asyncio

# Stub MicroPython modules so web_app can import on CPython
for n in ("machine", "micropython", "utime", "urandom"):
    sys.modules.setdefault(n, types.ModuleType(n))
sys.modules["micropython"].const = lambda x: x

# Stub time module to provide MicroPython-style ticks helpers
import time as _time_mod
if not hasattr(_time_mod, "ticks_ms"):
    _time_mod.ticks_ms = lambda: 0
if not hasattr(_time_mod, "ticks_diff"):
    _time_mod.ticks_diff = lambda a, b: a - b

# Stub microdot
fake_md = types.ModuleType("microdot")

class FakeMicrodot:
    def __init__(self):
        self.routes = []

    def get(self, path):
        def deco(fn):
            self.routes.append(("GET", path, fn))
            return fn
        return deco

    def post(self, path):
        def deco(fn):
            self.routes.append(("POST", path, fn))
            return fn
        return deco

    def before_request(self, fn):
        pass

    def errorhandler(self, code):
        def deco(fn):
            return fn
        return deco


class FakeResponse:
    def __init__(self, body="", status_code=200, headers=None):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}


def fake_abort(code):
    raise Exception("abort %d" % code)


fake_md.Microdot = FakeMicrodot
fake_md.Response = FakeResponse
fake_md.abort = fake_abort
sys.modules["microdot"] = fake_md

# Stub wifi_manager
fake_wm = types.ModuleType("wifi_manager")
fake_wm.AP_SSID = "test"
fake_wm.state = {"configured": True}
for n in ("configure", "is_connected", "request_reconnect",
          "check_wifi", "consume_reconnect_request"):
    setattr(fake_wm, n, lambda *a, **k: None)
sys.modules["wifi_manager"] = fake_wm

# Stub timekeeper
fake_tk = types.ModuleType("timekeeper")
fake_tk.render_format = lambda *a, **k: ""
fake_tk.configure = lambda *a, **k: None
sys.modules["timekeeper"] = fake_tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import multigroup_coordinator as mgc
import web_app


class FakeSettings:
    def __init__(self, num_groups, counts):
        self._num = num_groups
        self._counts = counts

    def get_int(self, key):
        if key == "numGroups":
            return self._num
        if key == "mode":
            return 4
        return 0

    def get_int_vector(self, key, length=None, fill=0):
        vals = list(self._counts)
        if length is not None:
            while len(vals) < length:
                vals.append(fill)
            return vals[:length]
        return vals


class FakeESP:
    def __init__(self):
        self._n = 1
    def next_msg_id(self):
        v = self._n; self._n += 1; return v
    def encode_display(self, msg_id, text):
        return "D"
    def send(self, *a, **k): pass
    def recv(self): return None


class FakeController:
    def __init__(self, num_groups, counts):
        self.multi_group_coordinator = mgc.MultiGroupCoordinator(FakeESP())
        self._settings = FakeSettings(num_groups, counts)
        self._settings_obj = self._settings

    @property
    def settings(self):
        return self._settings


def _find_route(app, kind, path):
    for k, p, fn in app.routes:
        if k == kind and p == path:
            return fn
    raise KeyError("route %s %s not found" % (kind, path))


def test_multigroup_status_no_groups_returns_empty():
    ctrl = FakeController(0, [])
    # settings returns numGroups=0 from FakeSettings, but the route should
    # gracefully return an empty groups array even then
    app = web_app.create_app(ctrl._settings, ctrl, None)
    fn = _find_route(app, "GET", "/multigroup/status")
    resp = asyncio.run(fn(object()))
    data = json.loads(resp.body)
    assert "groups" in data
    assert isinstance(data["groups"], list)


def test_multigroup_status_returns_per_group_state():
    ctrl = FakeController(3, [4, 3, 5])
    # Seed a dispatch so there's at least one entry in the coordinator
    ctrl.multi_group_coordinator.dispatch(
        ["AAAA", "BBB", "CCCCC"],
        [None, b"\x11"*6, b"\x22"*6],
    )
    app = web_app.create_app(ctrl._settings, ctrl, None)
    fn = _find_route(app, "GET", "/multigroup/status")
    resp = asyncio.run(fn(object()))
    data = json.loads(resp.body)
    assert data["mode"] == 4
    assert len(data["groups"]) == 3
    g = data["groups"]
    assert g[0]["group"] == 0 and g[0]["modules"] == 4 and g[0]["status"] == "sent"
    assert g[1]["group"] == 1 and g[1]["modules"] == 3
    assert g[2]["group"] == 2 and g[2]["modules"] == 5


def test_multigroup_status_route_is_registered():
    ctrl = FakeController(2, [4, 4])
    app = web_app.create_app(ctrl._settings, ctrl, None)
    paths = [p for k, p, fn in app.routes if k == "GET"]
    assert "/multigroup/status" in paths