# Multi-Group Split-Flap Display System

## Overview

This project extends the single-group split-flap display firmware into a scalable master-slave architecture. A **master** controller distributes text across up to 6 configurable groups (8 modules per group each) using ESP-NOW-based UDP broadcast, with ACK-driven status tracking.

## Architecture

```
[Master Group]                         [Slave Group 1]            [Slave Group N]
+-------------------+                  +----------------+        +----------------+
| web_app.py        |  ESP-NOW (UDP)   | boot.py /      |        | slave_group.py |
| /api/display POST |-- -> broadcast --|-- slave_group   |   ...  | + receiver     |
| /api/slaves CRUD  |                  | + espnow_mgr   |        | + ACK sender   |
+-------------------+                  +----------------+        +----------------+
       |                                      |                           |
  Alpine.js UI                            Display modules         Display modules
```

### Core Components

- **`espnow_manager.py`** - UDP-based ESP-NOW protocol layer (frame routing, slave registry, ACK tracking)
- **`slave_group.py`** - Standalone slave firmware for reception + ACK relay
- **`multigroup_controller.py`** - Text splitter, broadcast sequencer, master controller
- **`boot_slave.py`** - Standalone slave entry point (flashed to each slave ESP32)
- **`web_app.py`** - Microdot REST API with multi-group endpoints

## File Reference

| File | Size | Purpose |
|------|------|---------|
| `app/espnow_manager.py` | 5606B | UDP peer protocol + frame routing |
| `app/slave_group.py` | 3157B | Slave receiver + ACK sender logic |
| `app/multigroup_controller.py` | 4057B | MultiGroupDisplayController class |
| `app/boot_slave.py` | 1764B | Standalone slave boot entry point |
| `app/web_app.py` | 5645B | Microdot REST API (updated for MG) |
| `app/static/multigroup.html` | 3425B | Alpine.js UI for multi-group config |
| `app/static/multigroup.js` | 4404B | Alpine.js component logic |

## How It Works

1. **Slave Registration**: Each slave group is configured via `/api/slaves POST` with MAC address and module count (1–8 per group). Up to 6 groups total.
2. **Message Broadcast**: The master receives text via `/api/display POST {mode: "multi_group"}`, splits it into character segments sized for each group's module count, then UDP-broadcasts the frame set.
3. **ACK Tracking**: Slave groups receive frames from the broadcast channel and send back an ACK per group/sequence-pair. Master tracks pending/complete ACK status via REST API polling (every 5 seconds by default).

### Frame Format

ESP-NOW frames use a simple JSON over UDP on port **8432** (`ESPNOW_PORT`):
```json
{
    "version": 1,
    "seq_id": 42,
    "master_cmd": "multi_display",
    "num_groups": 2,
    "frames": [
        {"group_id": 0, "data": "AAAA", "cmd": "display", "version": 1},
        {"group_id": 1, "data": "BBBB", "cmd": "display", "version": 1}
    ]
}
```

### Display Flow

1. User enters text in master web UI → clicks `SEND TO GROUPS`  
2. Master splits text into segments → broadcasts to all configured slaves  
3. Each slave group receives its segment, updates the display, sends ACK back  
4. Master shows ACK status (WAITING/ACKED) with auto-refresh  

## Deployment Steps

### 1. Configure Slave Groups

Via web UI at `http://<ESP_IP>/`:
- Navigate to `/static/multigroup.html` 
- Enter slave MAC addresses (`AA:BB:CC:DD:EE:FF`) and module counts (1–8 each)  
- Click `+ ADD GROUP` for each slave, then `CLEAR ALL GROUPS` to reset

Or via API directly:
```bash
curl -X POST http://<ESP_IP>/api/slaves \
  -H 'Content-Type: application/json' \
  -d '{"mac":"AA:BB:CC:DD:EE:FF","modules":4}'

curl -X DELETE http://<ESP_IP>/api/slaves \
  -H 'Content-Type: application/json' \
  -d '{"index":-1}'
```

### 2. Flash Master Firmware

Use `boot.py` as the default boot entry point on one ESP32 device (the master):
```bash
# Compile and flash to master node
ampy --port /dev/ttyUSB0 put app/boot.py
```

### 3. Flash Slave Firmware

Deploy `boot_slave.py` to each slave group:
```bash
# Compile for slave mode only  
amPy --port /dev/ttyS2 put app/boot_slave.py
```

## API Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/display` | POST | Set text (single or multi_group mode) |
| `/api/slaves` | GET/POST/DELETE | Slave group CRUD operations |
| `/api/commands/home` | POST | Homing all groups to initial position |
| `/api/confirm/<mac>` | POST | Manual ACK confirmation for a group |

### Example: Multi-Group Broadcast

```bash
curl -X POST http://<ESP_IP>/api/display \
  -H 'Content-Type: application/json' \
  -d '{"text":"HELLO WORLD","mode":"multi_group"}'
```

Response:
```json
{"ok": true, "type": "multi_group", "acks": [101]}
```

## Configuration

Add slave groups to `Settings` via the web UI or configure directly. Each slave is represented by a dictionary entry in `slaves`:

```python
settings.set("slaves", [
    {"mac": "AA:BB:CC:DD:EE:FF", "modules": 4},
    {"mac": "11:22:33:44:55:66", "modules": 8}
])
```

The master controller will automatically distribute text across these groups based on their configured module count. Maximum **6 slave groups** with up to **8 modules per group**.

## Limitations and Notes

- **UDP Only**: No TCP handshake or connection — ESP-NOW broadcasts are best-effort delivery  
- **ACK Polling**: Master polls ACK status every 5 seconds via `/api/slaves` endpoint (auto-refresh from the web UI)  
- **Broadcast Timeout**: If no ACK arrives within 30 seconds, assume frame dropped and await manual re-transmission  
- **Single Display on Master**: The master group's own display shares one group's module slot for the first segment
