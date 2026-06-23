# MicroPython Port

This directory contains the MicroPython version of the split-flap display firmware.
Copy the contents of `micropython/app` to the root of the ESP32 filesystem.

## Files

- `boot.py` loads saved settings and brings up Wi-Fi. If station mode cannot connect, it starts the `Split Flap Display` access point.
- `main.py` starts the display controller, MQTT client, and Microdot web server.
- `static/*` contains the HTML, CSS, JS, and Alpine/Tailwind assets for the web interface.

## Dependencies

Install or copy these MicroPython libraries to the device:

- Microdot core package.
- `umqtt.simple` if MQTT support is needed.

Microdot's MicroPython installation docs recommend copying the required source files from its GitHub repository to the device. This app needs the base Microdot package.

## Updating Web Assets

From the repository root:

```sh
npm run assets
node micropython/tools/stage_web_assets.mjs
```

The existing `npm run assets:micropython` script runs those steps together.


## Notes

The Arduino OTA flow does not have a direct standard MicroPython equivalent, so the `otaPass` setting is preserved for API compatibility but is not used by this port.

The `mdns` value is applied as the network hostname when the MicroPython port supports it. Full `.local` mDNS resolution depends on the firmware build and network environment.

MicroPython does not provide the ESP-IDF POSIX timezone support used by Arduino `configTzTime()`. The port reads the same timezone setting and applies the base POSIX offset for date/time display; daylight-saving transition rules are ignored.

## Multi-Group ESP-NOW (optional)

Up to **6 groups** of split-flap modules (each group up to 8 modules) can be coordinated by one master ESP32 over **ESP-NOW**, giving a total capacity of up to **48 characters**.

The same firmware image is flashed to every device; each device's role is selected via the `groupMode` setting:

| `groupMode` | Role |
|---|---|
| `0` | Single device (legacy behaviour — web UI, MQTT, no ESP-NOW) |
| `1` | Master controller — runs web UI + MQTT, displays its own segment, sends the other segments over ESP-NOW |
| `2` | Slave — listens for ESP-NOW `display` packets, renders them, ACKs back to the master. No web UI, no MQTT. |

### Flash a slave

1. Open `http://<device>.local/settings.html`, set:
   - `groupMode` = `2` (Slave)
   - `numGroups` = total groups (e.g. `2`)
   - `groupIndex` = this slave's index (e.g. `1` for the first slave)
   - `groupModuleCounts` = CSV of module counts per group, e.g. `"7,4"` (sum must equal the master's local modules + each slave's local modules)
   - `groupMacAddresses` = CSV of MAC addresses — index 0 is the master's own MAC (can be left blank), index N is this slave's MAC (also can be left blank on the slave itself)
2. Save. The slave reboots and prints its MAC to the REPL.
3. Note the slave's MAC for the master configuration.

### Configure the master

1. On the master device (the one whose `groupMode=1`), open the settings page and:
   - Set `groupMode` = `1` (Master)
   - Set `numGroups` and `groupModuleCounts` to match the slaves
   - In `groupMacAddresses`, paste each slave's MAC at its corresponding index
2. Save. The master reboots; the **Multi-Group (Master)** option now appears in the main UI's mode dropdown.

### Sending a message

1. Select `Multi-Group (Master)` from the mode dropdown on the master's web UI.
2. Type up to **48 characters** (the sum of every group's module counts).
3. Click **Update Display**. The master displays its own segment locally and unicasts the rest to each slave over ESP-NOW.
4. Each slave renders its segment, then sends an `ack` back. The master's UI shows per-group status (`sent` → `acked`/`error`/`timeout` after 30 s).

### Constraints

- **Same Wi-Fi channel.** ESP-NOW piggybacks on the active STA/AP association. All devices must join the same AP — this puts them on the same channel automatically.
- **No MQTT or web UI on slaves.** Slaves are dumb terminals.
- **Synchronisation.** A slave must finish its segment at roughly the same time as the master. If a slave's `maxVel` is much slower than the master's, characters will visibly lag. Use the same `maxVel` and `charset` across all devices.
- **ACK timeout.** 30 s; status shows `timeout` if a slave doesn't reply. No automatic retry — re-send by clicking Update Display again.

### File layout (multi-group files)

| File | Purpose |
|---|---|
| `app/espnow_manager.py` | ESP-NOW transport (JSON-encoded `display` and `ack` messages, MAC helpers) |
| `app/slave_group.py` | Slave firmware: init display, recv `display` packets, render, send `ack` |
| `app/multigroup_coordinator.py` | Master-side ACK state tracker |
| `app/controller.py` | `MODE_MULTI_GROUP = 4`, `set_multi_group_text()`, `_multi_group_mode()` |
| `app/web_app.py` | `GET /multigroup/status`, extended `POST /text` for `mode:"multigroup"` |
| `app/main.py` | Early-return branch when `groupMode == 2` to run slave firmware |
