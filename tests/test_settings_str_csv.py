import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from settings import parse_str_csv, str_csv_to_string


def test_parse_str_csv_basic():
    assert parse_str_csv("aa:bb:cc:dd:ee:ff,11:22:33:44:55:66") == [
        "aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"
    ]


def test_parse_str_csv_strips_whitespace():
    assert parse_str_csv("  aa:bb , 11:22 ") == ["aa:bb", "11:22"]


def test_parse_str_csv_empty():
    assert parse_str_csv("") == []


def test_str_csv_to_string_roundtrip():
    src = ["aa:bb", "11:22", ""]
    assert parse_str_csv(str_csv_to_string(src)) == src
