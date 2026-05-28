try:
    import ujson as json
except ImportError:
    import json

from microdot import Microdot, Response, abort
from microdot.utemplate import Template

from settings import ValidationError
import timekeeper
import wifi_manager


STATIC_TYPES = {
    "index.css": "text/css",
    "index.js": "application/javascript",
    "timezones.json": "application/json",
}


def create_app(settings, controller, mqtt):
    app = Microdot()
    Template.initialize(template_dir="templates")

    @app.get("/")
    async def root(request):
        return Response.redirect("/index.html")

    @app.get("/index.html")
    async def index(request):
        return _html("index.tpl", settings)

    @app.get("/settings.html")
    async def settings_page(request):
        return _html("settings.tpl", settings)

    @app.get("/settings")
    async def get_settings(request):
        return _json(settings.to_dict())

    @app.post("/settings/reset")
    async def reset_settings(request):
        settings.reset()
        controller.request_reconnect()
        return _json(
            {
                "message": "Settings reset successfully! Reconnect to the %s network"
                % wifi_manager.AP_SSID,
                "type": "success",
                "persistent": True,
            }
        )

    @app.post("/settings")
    async def post_settings(request):
        payload = request.json
        if not isinstance(payload, dict):
            return _json({"message": "Expected a JSON object", "type": "error"}, 400)

        before = settings.to_dict()
        response = {"message": "Settings saved successfully!"}
        reconnect = False
        reboot = False

        if _changed(before, payload, "ssid") or _changed(before, payload, "password"):
            reconnect = True
            response["message"] = (
                "Settings updated successfully, Network settings have changed, "
                "reconnect to the %s network" % payload.get("ssid", settings.get_string("ssid"))
            )

        if _changed(before, payload, "otaPass"):
            reboot = True
            response["message"] = (
                "Settings updated successfully, OTA password has changed. Rebooting..."
            )

        if _changed(before, payload, "mdns"):
            reconnect = True
            mdns = str(payload.get("mdns") or "splitflap")
            response["message"] = (
                "Settings updated successfully, mDNS name has changed, "
                "automatically redirecting to http://%s.local..." % mdns
            )
            response["redirect"] = "http://%s.local/settings.html" % mdns

        mqtt_keys = ("mqtt_server", "mqtt_port", "mqtt_user", "mqtt_pass")
        if any(_changed(before, payload, key) for key in mqtt_keys):
            reconnect = True
            response["message"] = "MQTT settings have changed, reconnecting..."

        try:
            changed = settings.update(payload)
        except ValidationError as exc:
            return _json(
                {
                    "message": "Failed to save settings",
                    "type": "error",
                    "errors": {"key": exc.key, "message": exc.message},
                },
                400,
            )

        if "timezone" in changed:
            timekeeper.configure(settings)

        if reconnect:
            controller.request_reconnect()
        if reboot:
            controller.request_reboot()

        response["type"] = "success"
        response["persistent"] = reconnect or reboot
        return _json(response)

    @app.post("/text")
    async def post_text(request):
        payload = request.json
        if not isinstance(payload, dict):
            return _json({"message": "Expected a JSON object", "type": "error"}, 400)

        error = _validate_text_payload(payload)
        if error:
            return _json({"message": error, "type": "error"}, 400)

        delay_ms = int(float(payload["delay"]) * 1000)
        centering = bool(payload["center"])
        mode = payload["mode"]
        words = [_percent_decode(str(word)) for word in payload["words"]]

        if mode == "single":
            controller.set_single_text(words[0], delay_ms, centering)
        elif mode == "multiple":
            controller.set_multi_text(words, delay_ms, centering)

        return _json({"message": "Text updated successfully!", "type": "success"})

    @app.get("/<path:filename>")
    async def static_file(request, filename):
        if filename not in STATIC_TYPES:
            abort(404)

        return Response.send_file(
            "static/" + filename,
            content_type=STATIC_TYPES[filename],
            max_age=600,
        )

    @app.errorhandler(404)
    async def not_found(request):
        return "Not found", 404

    return app


def _html(template_name, settings):
    title = settings.get_string("name") or "Split Flap"
    body = Template(template_name).render(title=title)
    return Response(body, headers={"Content-Type": "text/html; charset=utf-8"})


def _json(data, status=200):
    return Response(
        json.dumps(data),
        status_code=status,
        headers={"Content-Type": "application/json"},
    )


def _changed(before, payload, key):
    return key in payload and str(payload[key]) != str(before.get(key, ""))


def _validate_text_payload(payload):
    mode = payload.get("mode")
    if mode not in ("single", "multiple"):
        return "Invalid mode type"

    words = payload.get("words")
    if not isinstance(words, list):
        return "Invalid words array"

    if mode == "single" and (not words or str(words[0]).strip() == ""):
        return "Single word cannot be empty"

    if mode == "multiple" and not words:
        return "Word list cannot be empty"

    try:
        delay = float(payload.get("delay"))
    except (TypeError, ValueError):
        return "Invalid delay type / value"

    if delay < 1:
        return "Invalid delay type / value"

    if not isinstance(payload.get("center"), bool):
        return "Invalid center type"

    return None


def _percent_decode(value):
    result = []
    index = 0

    while index < len(value):
        char = value[index]
        if char == "%" and index + 2 < len(value):
            try:
                result.append(chr(int(value[index + 1 : index + 3], 16)))
                index += 3
                continue
            except ValueError:
                pass
        if char == "+":
            result.append(" ")
        else:
            result.append(char)
        index += 1

    return "".join(result)
