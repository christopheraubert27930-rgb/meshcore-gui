# MeshCore GUI - BLE Troubleshooting Guide

## The Problem

BLE connection to MeshCore device fails with `EOFError` during `start_notify` on the UART TX characteristic. The error originates in `dbus_fast` (the D-Bus library used by `bleak`) and looks like this:

```
File "src/dbus_fast/_private/unmarshaller.py", line 395, in dbus_fast._private.unmarshaller.Unmarshaller._read_sock_with_fds
EOFError
```

Basic BLE connect works fine, but subscribing to notifications (`start_notify`) crashes.

## Diagnostic Steps

### 1. Check adapter status

```bash
hciconfig -a
```

Expected: `UP RUNNING`. If it shows `DOWN`, reset with:

```bash
sudo hciconfig hci0 down
sudo hciconfig hci0 up
```

### 2. Check if adapter is detected

```bash
lsusb | grep -i blue
```

### 3. Test basic BLE connection (without notify)

```bash
python -c "
import asyncio
from bleak import BleakClient
async def test():
    async with BleakClient('literal:AA:BB:CC:DD:EE:FF') as c:
        print('Connected:', c.is_connected)
asyncio.run(test())
"
```

If this works but meshcli/meshcore_gui fails, the problem is specifically `start_notify`.

### 4. Test start_notify in isolation

```bash
python -c "
import asyncio
from bleak import BleakClient
UART_TX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'
async def test():
    async with BleakClient('literal:AA:BB:CC:DD:EE:FF') as c:
        def cb(s, d): print(f'RX: {d.hex()}')
        await c.start_notify(UART_TX, cb)
        print('Notify OK!')
        await asyncio.sleep(2)
asyncio.run(test())
"
```

If this also fails with `EOFError`, the issue is confirmed at the BlueZ/D-Bus level.

### 5. Test notifications via bluetoothctl (outside Python)

```bash
bluetoothctl
scan on
# Wait for device to appear
connect literal:AA:BB:CC:DD:EE:FF
# Wait for "Connection successful"
menu gatt
select-attribute 6e400003-b5a3-f393-e0a9-e50e24dcca9e
notify on
```

If `connect` fails with `le-connection-abort-by-local`, the problem is at the BlueZ or device level. No Python fix will help.

## The Solution

In our case, the root cause was a stale BLE pairing state between the Linux adapter and the T1000-e device. The fix requires a clean reconnect sequence:

### Step 1 - Remove the device from BlueZ

```bash
bluetoothctl
remove literal:AA:BB:CC:DD:EE:FF
exit
```

### Step 2 - Hard power cycle the MeshCore device

Physically power off the T1000-e (not just a software reset). Wait 10 seconds, then power it back on.

### Step 3 - Scan and reconnect from scratch

```bash
bluetoothctl
scan on
```

Wait until the device appears: `[NEW] Device literal:AA:BB:CC:DD:EE:FF MeshCore-PE1HVH T1000e`

Then immediately connect:

```
connect literal:AA:BB:CC:DD:EE:FF
```

### Step 4 - Verify notifications work

```
menu gatt
select-attribute 6e400003-b5a3-f393-e0a9-e50e24dcca9e
notify on
```

If this succeeds, disconnect cleanly:

```
notify off
back
disconnect literal:AA:BB:CC:DD:EE:FF
exit
```

### Step 5 - Verify channels with meshcli

```bash
meshcli -d literal:AA:BB:CC:DD:EE:FF
> get_channels
```

Confirm output matches `CHANNELS_CONFIG` in `meshcore_gui.py`, then:

```
> exit
```

### Step 6 - Start the GUI

```bash
cd ~/Documents/Share/Web/meshcore-linux
source venv/bin/activate
python meshcore_gui.py literal:AA:BB:CC:DD:EE:FF
```

## Things That Did NOT Help

| Action | Result |
|---|---|
| `sudo systemctl restart bluetooth` | No effect |
| `sudo hciconfig hci0 down/up` | No effect |
| `sudo rmmod btusb && sudo modprobe btusb` | No effect |
| `sudo usbreset "8087:0026"` | No effect |
| `sudo reboot` | No effect |
| Clearing BlueZ cache (`/var/lib/bluetooth/*/cache`) | No effect |
| Recreating Python venv | No effect |
| Downgrading `dbus_fast` / `bleak` | No effect |
| Downgrading `linux-firmware` | No effect |

## Key Takeaway

When `start_notify` fails with `EOFError` but basic BLE connect works, the issue is almost always a stale BLE state between the host adapter and the peripheral device. The fix is:

1. **Remove** the device from bluetoothctl
2. **Hard power cycle** the peripheral device
3. **Re-scan** and reconnect from scratch

## Recommended Startup Sequence

For the most reliable BLE connection, always follow this order:

1. Ensure no other application holds the BLE connection (BT manager, bluetoothctl, meshcli)
2. Verify the device is visible: `bluetoothctl scan on`
3. Check channels: `meshcli -d <BLE_ADDRESS>` → `get_channels` → `exit`
4. Start the GUI: `python meshcore_gui.py <BLE_ADDRESS>`
