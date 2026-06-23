try:
    import ujson as json
except ImportError:
    import json

try:
    import uos as os
except ImportError:
    import os


CONFIG_FILE = "config.json"

DEFAULT_SETTINGS = {
    # General settings
    "name": "My Display",
    "mdns": "splitflap",
    "otaPass": "",
    "timezone": "UTC0",
    "dateFormat": "{dd}-{mm}-{yy}",
    "timeFormat": "{HH}:{mm}",
    # Wi-Fi settings
    "ssid": "",
    "password": "",
    # MQTT settings
    "mqtt_server": "",
    "mqtt_port": 1883,
    "mqtt_user": "",
    "mqtt_pass": "",
    # Hardware settings
    "moduleCount": 7,
    "moduleAddresses": "32, 33, 34, 35, 36, 37, 38",
    "magnetPosition": 615,
    "moduleOffsets": "23, 12, 50, 0, 0, 6, 12",
    "displayOffset": 0,
    "sdaPin": 8,
    "sclPin": 9,
    "stepsPerRot": 2048,
    "maxVel": 20,
    "charset": 48,
    # Multi-group ESP-NOW settings
    "groupMode": 0,            # 0 = single-device, 1 = master, 2 = slave
    "numGroups": 1,            # 1..6 (master + up to 5 slaves)
    "groupIndex": 0,           # 0..5 — which group this device is
    "groupModuleCounts": "",   # CSV of module counts, e.g. "8,6,4"
    "groupMacAddresses": "",   # CSV of MAC addresses, one per slave
    # Operational state
    "mode": 0,
}

SETTING_TYPES = {
    "name": "str",
    "mdns": "str",
    "otaPass": "str",
    "timezone": "str",
    "dateFormat": "str",
    "timeFormat": "str",
    "ssid": "str",
    "password": "str",
    "mqtt_server": "str",
    "mqtt_port": "int",
    "mqtt_user": "str",
    "mqtt_pass": "str",
    "moduleCount": "int",
    "moduleAddresses": "int_csv",
    "magnetPosition": "int",
    "moduleOffsets": "int_csv",
    "displayOffset": "int",
    "sdaPin": "int",
    "sclPin": "int",
    "stepsPerRot": "int",
    "maxVel": "float",
    "charset": "int",
    "groupMode": "int",
    "numGroups": "int",
    "groupIndex": "int",
    "groupModuleCounts": "int_csv",
    "groupMacAddresses": "str_csv",
    "mode": "int",
}


class ValidationError(Exception):
    def __init__(self, key, message):
        super().__init__(message)
        self.key = key
        self.message = message


def parse_int_csv(value):
    if isinstance(value, list):
        return [int(item) for item in value]

    value = str(value).strip()
    if not value:
        return []

    result = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError("Empty integer value found")
        result.append(int(part))
    return result


def int_csv_to_string(value):
    return ",".join(str(int(item)) for item in value)


def parse_str_csv(value):
    if isinstance(value, list):
        return [str(item) for item in value]
    value = str(value).strip()
    if not value:
        return []
    return [part.strip() for part in value.split(",")]


def str_csv_to_string(value):
    return ",".join(str(item) for item in value)


class Settings:
    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self._data = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        try:
            with open(self.path, "r") as handle:
                raw = json.loads(handle.read())
        except (OSError, ValueError):
            return False

        if not isinstance(raw, dict):
            return False

        for key, value in raw.items():
            if key in DEFAULT_SETTINGS:
                self._data[key] = self._coerce(key, value)
        return True

    def save(self):
        temp_path = self.path + ".tmp"
        with open(temp_path, "w") as handle:
            handle.write(json.dumps(self._data))

        try:
            os.remove(self.path)
        except OSError:
            pass
        os.rename(temp_path, self.path)

    def reset(self):
        self._data = DEFAULT_SETTINGS.copy()
        self.save()

    def to_dict(self):
        return self._data.copy()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_string(self, key):
        return str(self._data.get(key, ""))

    def get_int(self, key):
        return int(self._data.get(key, 0))

    def get_float(self, key):
        return float(self._data.get(key, 0.0))

    def get_int_vector(self, key, length=None, fill=0):
        values = parse_int_csv(self._data.get(key, ""))
        if length is not None:
            while len(values) < length:
                values.append(fill)
            values = values[:length]
        return values

    def get_string_vector(self, key, length=None, fill=""):
        values = parse_str_csv(self._data.get(key, ""))
        if length is not None:
            while len(values) < length:
                values.append(fill)
            values = values[:length]
        return values

    def set(self, key, value):
        self.update({key: value})

    def update(self, patch):
        if not isinstance(patch, dict):
            raise ValidationError("", "Expected a JSON object")

        next_data = self._data.copy()
        changed = []

        for key, value in patch.items():
            if key not in DEFAULT_SETTINGS:
                raise ValidationError(key, "Unknown setting")
            coerced = self._coerce(key, value)
            if next_data.get(key) != coerced:
                changed.append(key)
            next_data[key] = coerced

        self._data = next_data
        self.save()
        return changed

    def _coerce(self, key, value):
        setting_type = SETTING_TYPES[key]

        if setting_type == "str":
            return "" if value is None else str(value)

        if setting_type == "int":
            try:
                return int(value)
            except (TypeError, ValueError):
                raise ValidationError(key, "Expected an integer value")

        if setting_type == "float":
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValidationError(key, "Expected a numeric value")

        if setting_type == "int_csv":
            try:
                return int_csv_to_string(parse_int_csv(value))
            except (TypeError, ValueError):
                raise ValidationError(key, "Non-integer value found")

        if setting_type == "str_csv":
            return str_csv_to_string(parse_str_csv(value))

        raise ValidationError(key, "Unsupported setting type")
