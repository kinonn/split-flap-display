try:
    import ujson as json
except ImportError:
    import json

import time


TIMEZONE_FILE = "static/timezones.json"

_offset_seconds = 0
_posix_timezone = "UTC0"

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def configure(settings):
    global _offset_seconds, _posix_timezone

    configured = settings.get_string("timezone") or "UTC0"
    _posix_timezone = _lookup_posix_timezone(configured)
    _offset_seconds = _parse_posix_offset(_posix_timezone)
    print("Timezone:", configured, "=>", _posix_timezone)


def localtime():
    return time.localtime(time.time() + _offset_seconds)


def render_format(user_format, context="date", max_len=None):
    if not user_format:
        user_format = "{HH}:{mm}" if context == "time" else "{dd}-{mm}-{yy}"

    rendered = str(user_format)
    values = _format_values(localtime(), context)
    for token in sorted(values, key=len, reverse=True):
        rendered = rendered.replace(token, values[token])

    if max_len is not None and len(rendered) > max_len:
        rendered = rendered[:max_len]
    return rendered


def _lookup_posix_timezone(configured):
    try:
        with open(TIMEZONE_FILE, "r") as handle:
            zones = json.loads(handle.read())
    except (OSError, ValueError):
        zones = {}

    if configured in zones:
        return zones[configured]

    for label, posix in zones.items():
        if configured == posix:
            return posix

    return configured or "UTC0"


def _parse_posix_offset(posix_timezone):
    text = posix_timezone or "UTC0"
    index = 0

    if text.startswith("<"):
        index = text.find(">") + 1
    else:
        while index < len(text) and not _is_offset_char(text[index]):
            index += 1

    if index >= len(text):
        return 0

    sign = 1
    if text[index] == "-":
        sign = -1
        index += 1
    elif text[index] == "+":
        index += 1

    hours = 0
    while index < len(text) and text[index].isdigit():
        hours = hours * 10 + int(text[index])
        index += 1

    minutes = 0
    if index < len(text) and text[index] == ":":
        index += 1
        while index < len(text) and text[index].isdigit():
            minutes = minutes * 10 + int(text[index])
            index += 1

    posix_offset = sign * ((hours * 3600) + (minutes * 60))
    return -posix_offset


def _is_offset_char(char):
    return char == "+" or char == "-" or char.isdigit()


def _format_values(tm, context):
    year, month, day, hour, minute, second, weekday, yearday = tm[:8]
    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    month_text = MONTHS[month]
    day_text = WEEKDAYS[weekday]
    minute_token = "%02d" % minute if context == "time" else "%02d" % month

    return {
        "{yyyy}": "%04d" % year,
        "{yy}": "%02d" % (year % 100),
        "{dddd}": day_text,
        "{ddd}": day_text[:3],
        "{mmmm}": month_text,
        "{mmm}": month_text[:3],
        "{dd}": "%02d" % day,
        "{d}": str(day),
        "{mm}": minute_token,
        "{M}": str(month),
        "{ww}": "%02d" % _iso_week(year, yearday, weekday),
        "{D}": "%03d" % yearday,
        "{HH}": "%02d" % hour,
        "{hh}": "%02d" % hour_12,
        "{MM}": "%02d" % minute,
        "{ss}": str(second // 10),
        "{AM}": "AM" if hour < 12 else "PM",
        "{AMPM}": "AM" if hour < 12 else "PM",
    }


def _iso_week(year, yearday, weekday):
    week = (yearday - weekday + 10) // 7
    if week < 1:
        return _iso_weeks_in_year(year - 1)
    if week > _iso_weeks_in_year(year):
        return 1
    return week


def _iso_weeks_in_year(year):
    jan_1 = _jan_1_weekday(year)
    if jan_1 == 3 or (jan_1 == 2 and _is_leap_year(year)):
        return 53
    return 52


def _jan_1_weekday(year):
    previous = year - 1
    return (previous + previous // 4 - previous // 100 + previous // 400) % 7


def _is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
