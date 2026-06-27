# MicroPython Port

This directory contains the MicroPython version of the split-flap display firmware.
The source firmware lives in `app/`. Copy the contents of `app/` to the root of
the ESP32 filesystem, or run `build.py` and copy the generated `build/`
directory contents instead.

## Files

- `boot.py` loads saved settings and brings up Wi-Fi. If station mode cannot connect, it starts the `Split Flap Display` access point.
- `main.py` starts the display controller, MQTT client, and Microdot web server.
- `controller.py` manages display modes and routes text to the local display or ESP-NOW groups.
- `display.py` and `splitflap_module.py` drive the physical split-flap modules.
- `espnow_manager.py` coordinates multi-group displays using ESP-NOW.
- `settings.py` loads, validates, and saves `config.json`.
- `static/*` contains the HTML, CSS, JS, and Alpine/Tailwind assets for the web interface.

## Dependencies

Install or copy these MicroPython libraries to the device:

- Microdot core package.
- `umqtt.simple` if MQTT support is needed.
- A MicroPython firmware build with `network` support.
- A MicroPython ESP32 firmware build with `espnow` support if multi-group displays are needed.

Microdot's MicroPython installation docs recommend copying the required source files from its GitHub repository to the device. This app needs the base Microdot package.

For local build packaging, install `mpy-cross` on the development machine. The
current `build.py` compiles selected files with `-march=rv32imc`; update that
target if your MicroPython board uses a different architecture.

## Building and Installing

The simplest installation is to copy `app/` directly to the ESP32 filesystem.
For a smaller deployment, build the packaged output:

```sh
python build.py
```

Then copy the contents of `build/` to the root of the ESP32 filesystem.

The web assets in `app/static/` are already committed in this repository. There
is no npm build step in this checkout.

## Display Groups and ESP-NOW

One controller can drive up to 8 split-flap modules directly. To build a larger
display, configure one controller as the master and register up to 6 total
groups. The master runs on group 1, displays the first segment of the message on
its own modules, then sends the remaining message segments to the other groups
using ESP-NOW. Each remote group displays only the number of characters assigned
to that group and sends an acknowledgement back to the master when its movement
has completed.

The same firmware is used for a single group, the master group, and remote
groups. Configure the ESP-NOW settings from `settings.html` or directly in
`config.json`.

### ESP-NOW Settings

- `masterEnabled`: Set to `0` for a normal standalone group or remote group. Set
  to `1` only on the master controller.
- `groupId`: The identity of this controller's group, from `1` to `6`. The
  master must be group `1`. Remote groups should use `2`, `3`, and so on.
- `masterGroupCount`: The total number of groups in the full display, including
  the master group. Valid values are `1` to `6`.
- `masterGroupMacs`: Semicolon-separated ESP-NOW MAC addresses for the groups.
  Group 1 is local to the master, so leave the first entry empty. Remote group
  MAC addresses start at the second entry. MAC addresses may be entered as
  `AA:BB:CC:DD:EE:FF` or `AABBCCDDEEFF`.
- `masterGroupModules`: Comma-separated module counts for each group. Each
  group can have `1` to `8` modules. The master uses the normal `moduleCount`
  setting for group 1; remote group entries tell the master how many characters
  to send to each remote group.

Remote groups still need their own local hardware settings, including
`moduleCount`, module I2C addresses, offsets, pins, and character set.

### One Group Configuration

Use this when the display has 1 to 8 modules connected to a single controller.
ESP-NOW is not used.

```json
{
  "moduleCount": 7,
  "masterEnabled": 0,
  "groupId": 1,
  "masterGroupCount": 1,
  "masterGroupMacs": "",
  "masterGroupModules": "7"
}
```

With this configuration, text entered on the web page is written only to the
local modules.

### Multiple Group Configuration

In this example the full display has 20 modules split across three groups:

- Group 1: 7 modules, master controller, local display segment.
- Group 2: 8 modules, remote controller.
- Group 3: 5 modules, remote controller.

Configure the master controller on group 1 like this:

```json
{
  "moduleCount": 7,
  "masterEnabled": 1,
  "groupId": 1,
  "masterGroupCount": 3,
  "masterGroupMacs": ";AA:BB:CC:DD:EE:02;AA:BB:CC:DD:EE:03",
  "masterGroupModules": "7,8,5"
}
```

Configure the group 2 controller like this:

```json
{
  "moduleCount": 8,
  "masterEnabled": 0,
  "groupId": 2
}
```

Configure the group 3 controller like this:

```json
{
  "moduleCount": 5,
  "masterEnabled": 0,
  "groupId": 3
}
```

For the message `HELLO SPLIT FLAP`, the master pads or truncates the message to
the total configured width, then sends:

- Characters 1-7 to group 1.
- Characters 8-15 to group 2.
- Characters 16-20 to group 3.

After each remote group finishes displaying its segment, it replies to the
master with an ESP-NOW acknowledgement. The master status can be read from
`/master/status`.

## Notes

The Arduino OTA flow does not have a direct standard MicroPython equivalent, so the `otaPass` setting is preserved for API compatibility but is not used by this port.

The `mdns` value is applied as the network hostname when the MicroPython port supports it. Full `.local` mDNS resolution depends on the firmware build and network environment.

MicroPython does not provide the ESP-IDF POSIX timezone support used by Arduino `configTzTime()`. The port reads the same timezone setting and applies the base POSIX offset for date/time display; daylight-saving transition rules are ignored.
