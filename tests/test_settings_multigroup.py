import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from settings import Settings, DEFAULT_SETTINGS, SETTING_TYPES


def test_multigroup_defaults_present():
    for key in ("groupMode", "numGroups", "groupIndex",
                "groupModuleCounts", "groupMacAddresses"):
        assert key in DEFAULT_SETTINGS, f"missing default for {key}"


def test_setting_types_for_multigroup():
    assert SETTING_TYPES["groupMode"] == "int"
    assert SETTING_TYPES["numGroups"] == "int"
    assert SETTING_TYPES["groupIndex"] == "int"
    assert SETTING_TYPES["groupModuleCounts"] == "int_csv"
    assert SETTING_TYPES["groupMacAddresses"] == "str_csv"


def test_settings_roundtrip(tmp_path):
    cfg = tmp_path / "c.json"
    s = Settings(path=str(cfg))
    s.update({
        "groupMode": 1, "numGroups": 3, "groupIndex": 0,
        "groupModuleCounts": "8, 6, 4",
        "groupMacAddresses": "aa:bb:cc:dd:ee:ff, 11:22:33:44:55:66, 22:33:44:55:66:77",
    })
    s2 = Settings(path=str(cfg))
    assert s2.get_int("groupMode") == 1
    assert s2.get_int("numGroups") == 3
    assert s2.get_int_vector("groupModuleCounts", 3) == [8, 6, 4]
    assert s2.get_string_vector("groupMacAddresses", 3) == [
        "aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66", "22:33:44:55:66:77"
    ]