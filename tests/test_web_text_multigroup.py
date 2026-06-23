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

import web_app


class FakeSettings:
    def to_dict(self):
        return {}
    def get_int(self, key):
        return 0


class FakeController:
    def __init__(self):
        self.calls = []
    def set_single_text(self, text, delay_ms, centering):
        self.calls.append(("single", text, delay_ms, centering))
    def set_multi_text(self, words, delay_ms, centering):
        self.calls.append(("multi", list(words), delay_ms, centering))
    def set_multi_group_text(self, text, centering):
        self.calls.append(("multigroup", text, centering))
    def request_reconnect(self):
        pass
    def request_reboot(self):
        pass


class FakeRequest:
    def __init__(self, payload):
        self.json = payload


def _make_app_pair():
    """Returns (app, controller)."""
    controller = FakeController()
    app = web_app.create_app(FakeSettings(), controller, None)
    return app, controller


def _find_route(app, kind, path):
    for k, p, fn in app.routes:
        if k == kind and p == path:
            return fn
    raise KeyError("route %s %s not found" % (kind, path))


def test_multigroup_mode_calls_set_multi_group_text():
    app, ctrl = _make_app_pair()
    fn = _find_route(app, "POST", "/text")
    resp = asyncio.run(fn(FakeRequest({
        "mode": "multigroup",
        "text": "HELLO WORLD",
        "center": True,
    })))
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["type"] == "success"
    assert ("multigroup", "HELLO WORLD", True) in ctrl.calls


def test_multigroup_mode_centering_false():
    app, ctrl = _make_app_pair()
    fn = _find_route(app, "POST", "/text")
    resp = asyncio.run(fn(FakeRequest({
        "mode": "multigroup",
        "text": "OK",
        "center": False,
    })))
    assert resp.status_code == 200
    assert ("multigroup", "OK", False) in ctrl.calls


def test_multigroup_mode_missing_text_returns_400():
    app, ctrl = _make_app_pair()
    fn = _find_route(app, "POST", "/text")
    resp = asyncio.run(fn(FakeRequest({
        "mode": "multigroup",
        "center": True,
    })))
    assert resp.status_code == 400
    data = json.loads(resp.body)
    assert data["type"] == "error"


def test_multigroup_mode_empty_text_returns_400():
    app, ctrl = _make_app_pair()
    fn = _find_route(app, "POST", "/text")
    resp = asyncio.run(fn(FakeRequest({
        "mode": "multigroup",
        "text": "   ",
        "center": True,
    })))
    assert resp.status_code == 400


def test_existing_single_mode_still_works():
    app, ctrl = _make_app_pair()
    fn = _find_route(app, "POST", "/text")
    resp = asyncio.run(fn(FakeRequest({
        "mode": "single",
        "words": ["HELLO"],
        "delay": 5,
        "center": True,
    })))
    assert resp.status_code == 200
    assert any(c[0] == "single" for c in ctrl.calls)


def test_invalid_mode_returns_400():
    app, ctrl = _make_app_pair()
    fn = _find_route(app, "POST", "/text")
    resp = asyncio.run(fn(FakeRequest({
        "mode": "made_up_mode",
        "text": "x",
        "center": True,
    })))
    assert resp.status_code == 400
    assert ctrl.calls == []