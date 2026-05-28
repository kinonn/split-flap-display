try:
    import ujson as json
except ImportError:
    import json

try:
    from umqtt.simple import MQTTClient
except ImportError:
    MQTTClient = None

import time


class SplitFlapMqtt:
    def __init__(self, settings):
        self.settings = settings
        self.display = None
        self.client = None
        self.enabled = False
        self.connected = False
        self.last_attempt = 0

        self.topic_command = ""
        self.topic_state = ""
        self.topic_availability = ""
        self.topic_config_text = ""
        self.topic_config_sensor = ""

    def set_display(self, display):
        self.display = display

    def setup(self):
        self.disconnect()

        server = self.settings.get_string("mqtt_server")
        if not server:
            self.enabled = False
            return

        if MQTTClient is None:
            print("MQTT disabled: umqtt.simple is not installed")
            self.enabled = False
            return

        mdns = self.settings.get_string("mdns") or "splitflap"
        port = self.settings.get_int("mqtt_port")
        user = self.settings.get_string("mqtt_user") or None
        password = self.settings.get_string("mqtt_pass") or None

        self.topic_command = "splitflap/%s/set" % mdns
        self.topic_state = "splitflap/%s/state" % mdns
        self.topic_availability = "splitflap/%s/availability" % mdns
        self.topic_config_text = "homeassistant/text/splitflap_text_%s/config" % mdns
        self.topic_config_sensor = "homeassistant/sensor/splitflap_sensor_%s/config" % mdns

        self.client = MQTTClient(mdns, server, port=port, user=user, password=password)
        self.client.set_callback(self._on_message)
        self.enabled = True
        self._connect()

    def disconnect(self):
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.connected = False

    def loop(self):
        if not self.enabled:
            return

        if not self.connected:
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_attempt) > 5000:
                self._connect()
            return

        try:
            self.client.check_msg()
        except Exception as exc:
            print("[MQTT] check failed:", exc)
            self.connected = False

    def publish_state(self, message):
        if not self.connected:
            return
        self._publish(self.topic_state, message, retain=True)

    def is_connected(self):
        return self.connected

    def _connect(self):
        self.last_attempt = time.ticks_ms()
        if self.client is None:
            return

        try:
            print("[MQTT] Connecting")
            self.client.connect()
            self.connected = True
            self.client.subscribe(self.topic_command)
            self._publish(self.topic_availability, "online", retain=True)
            self._publish(self.topic_state, "", retain=True)
            self._publish_discovery()
            print("[MQTT] Connected")
        except Exception as exc:
            self.connected = False
            print("[MQTT] Connection failed:", exc)

    def _publish(self, topic, payload, retain=False):
        try:
            self.client.publish(topic, payload, retain=retain)
        except Exception as exc:
            self.connected = False
            print("[MQTT] Publish failed:", exc)

    def _publish_discovery(self):
        mdns = self.settings.get_string("mdns") or "splitflap"
        name = self.settings.get_string("name") or "Split Flap"
        device = {
            "identifiers": ["splitflap_" + mdns],
            "name": name,
            "manufacturer": "SplitFlap",
            "model": "SplitFlap Display",
            "sw_version": "1.0.0-micropython",
        }

        text_entity = {
            "name": "Display",
            "unique_id": "text_" + mdns,
            "command_topic": self.topic_command,
            "availability_topic": self.topic_availability,
            "device": device,
        }
        sensor_entity = {
            "name": "Currently Displayed",
            "unique_id": "sensor_" + mdns,
            "state_topic": self.topic_state,
            "availability_topic": self.topic_availability,
            "entity_category": "diagnostic",
            "device": device,
        }

        self._publish(self.topic_config_text, json.dumps(text_entity), retain=True)
        self._publish(self.topic_config_sensor, json.dumps(sensor_entity), retain=True)

    def _on_message(self, topic, payload):
        try:
            message = payload.decode()
        except AttributeError:
            message = str(payload)

        print("[MQTT] Message received:", message)
        if self.display is not None:
            self.display.write_string(
                message,
                self.settings.get_float("maxVel"),
                centering=False,
            )
