try:
    import network
except ImportError:
    network = None

try:
    import ntptime
except ImportError:
    ntptime = None

import time

import timekeeper


AP_SSID = "Split Flap Display"
CONNECT_TIMEOUT_MS = 20000

state = {
    "configured": False,
    "connection_mode": 0,  # 0 = AP, 1 = station
    "ip": "0.0.0.0",
    "attempt_reconnect": False,
}


def configure(settings):
    timekeeper.configure(settings)

    if network is None:
        state["configured"] = True
        state["connection_mode"] = 0
        return False

    ssid = settings.get_string("ssid")
    password = settings.get_string("password")
    hostname = settings.get_string("mdns") or "splitflap"

    if ssid and password and _connect_station(ssid, password, hostname):
        state["configured"] = True
        state["connection_mode"] = 1
        _sync_clock()
        return True

    start_access_point()
    state["configured"] = True
    return False


def is_connected():
    if network is None:
        return False
    return network.WLAN(network.STA_IF).isconnected()


def device_info():
    info = {
        "ip": state.get("ip", "0.0.0.0"),
        "mac": "",
    }

    if network is None:
        return info

    wlan = _active_interface()
    ip = _interface_ip(wlan)
    mac = _interface_mac(wlan)

    if ip:
        info["ip"] = ip
    if mac:
        info["mac"] = mac

    return info


def check_wifi(settings):
    if network is None or state["connection_mode"] != 1:
        return

    station = network.WLAN(network.STA_IF)
    if station.isconnected():
        return

    print("Wi-Fi lost, reconnecting")
    try:
        station.disconnect()
    except Exception:
        pass

    ssid = settings.get_string("ssid")
    password = settings.get_string("password")
    if ssid and password:
        station.connect(ssid, password)


def request_reconnect():
    state["attempt_reconnect"] = True


def consume_reconnect_request():
    requested = state["attempt_reconnect"]
    state["attempt_reconnect"] = False
    return requested


def start_access_point():
    if network is None:
        return

    state["connection_mode"] = 0
    station = network.WLAN(network.STA_IF)
    access_point = network.WLAN(network.AP_IF)

    try:
        station.active(False)
    except Exception:
        pass

    access_point.active(True)
    access_point.config(essid=AP_SSID)
    state["ip"] = access_point.ifconfig()[0]
    print("AP mode started:", AP_SSID)
    print("AP IP address: http://%s" % state["ip"])


def _connect_station(ssid, password, hostname):
    station = network.WLAN(network.STA_IF)
    access_point = network.WLAN(network.AP_IF)

    access_point.active(False)
    station.active(True)
    _set_hostname(station, hostname)

    if not station.isconnected():
        print("Connecting to Wi-Fi:", ssid)
        station.connect(ssid, password)

    start = time.ticks_ms()
    while not station.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) >= CONNECT_TIMEOUT_MS:
            print("Wi-Fi connection failed")
            return False
        time.sleep_ms(250)

    state["ip"] = station.ifconfig()[0]
    print("Connected to Wi-Fi: http://%s" % state["ip"])
    return True


def _set_hostname(station, hostname):
    try:
        network.hostname(hostname)
        return
    except Exception:
        pass

    try:
        station.config(dhcp_hostname=hostname)
    except Exception:
        pass


def _sync_clock():
    if ntptime is None:
        return

    try:
        ntptime.settime()
        print("NTP time synchronized")
    except Exception as exc:
        print("NTP sync failed:", exc)


def _active_interface():
    if state.get("connection_mode") == 1:
        return network.WLAN(network.STA_IF)
    return network.WLAN(network.AP_IF)


def _interface_ip(wlan):
    try:
        return wlan.ifconfig()[0]
    except Exception:
        return ""


def _interface_mac(wlan):
    try:
        mac = wlan.config("mac")
    except Exception:
        return ""

    if not mac:
        return ""

    try:
        return ":".join("%02X" % byte for byte in mac)
    except Exception:
        return str(mac)
