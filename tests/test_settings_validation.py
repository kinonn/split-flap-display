import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from settings import Settings, ValidationError


def _new_settings(tmp_path):
    return Settings(path=str(tmp_path / "c.json"))


def test_num_groups_too_high(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({"numGroups": 7})


def test_num_groups_zero(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({"numGroups": 0})


def test_group_index_too_high(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({"numGroups": 3, "groupIndex": 5})


def test_group_index_out_of_range(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({"numGroups": 3, "groupIndex": 3})


def test_csv_lengths_mismatch(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({
            "numGroups": 3,
            "groupModuleCounts": "8, 6",
            "groupMacAddresses": "aa:bb, cc:dd, ee:ff",
        })


def test_module_count_too_high(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({"numGroups": 1, "groupModuleCounts": "9"})


def test_bad_mac_format(tmp_path):
    s = _new_settings(tmp_path)
    with pytest.raises(ValidationError):
        s.update({"numGroups": 1, "groupMacAddresses": "not-a-mac"})


def test_valid_multigroup_passes(tmp_path):
    s = _new_settings(tmp_path)
    s.update({
        "numGroups": 2, "groupIndex": 1,
        "groupModuleCounts": "8, 4",
        "groupMacAddresses": "aa:bb:cc:dd:ee:ff, 11:22:33:44:55:66",
    })
    assert s.get_int("numGroups") == 2
