# MeshCore GUI
![Status](https://img.shields.io/badge/Status-Production-green.svg)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-orange.svg)

A graphical user interface for MeshCore mesh network devices via Bluetooth Low Energy (BLE) for on your desktop.

## Why This Project Exists

MeshCore devices like the SenseCAP T1000-E can be managed through two interfaces: USB serial and BLE (Bluetooth Low Energy). The official companion apps communicate with devices over BLE, but they are mobile-only. If you want to manage your MeshCore device from a desktop or laptop, the usual approach is to **flash USB-serial firmware** via the web flasher. However, this replaces the BLE Companion firmware, which means you can no longer use the device with mobile companion apps (Android/iOS).

This project provides a **native desktop GUI** that connects to your MeshCore device over BLE — no firmware changes required. Your device stays on BLE Companion firmware and remains fully compatible with the mobile apps. The application is written in Python using cross-platform libraries and runs on **Linux, macOS and Windows**.

> **Note:** This application has only been tested on Linux (Ubuntu 24.04). macOS and Windows should work since all dependencies (`bleak`, `nicegui`, `meshcore`) are cross-platform, but this has not been verified. Feedback and contributions for other platforms are welcome.

Under the hood it uses `bleak` for Bluetooth Low Energy (which talks to BlueZ on Linux, CoreBluetooth on macOS, and WinRT on Windows), `meshcore` as the protocol layer, `meshcoredecoder` for raw LoRa packet decryption and route extraction, and `NiceGUI` for the web-based interface.

> **Linux users:** BLE on Linux can be temperamental. BlueZ occasionally gets into a bad state, especially after repeated connect/disconnect cycles. If you run into connection issues, see the [Troubleshooting Guide](docs/TROUBLESHOOTING.md). On macOS and Windows, BLE is generally more stable out of the box.


## Features

- **Real-time Dashboard** — Device info, contacts, messages and RX log
- **Interactive Map** — Leaflet map with markers for own position and contacts
- **Channel Messages** — Send and receive messages on channels
- **Direct Messages** — Click on a contact to send a DM
- **Contact Maintenance** — Pin/unpin contacts to protect them from deletion, bulk-delete unpinned contacts from the device, and toggle automatic contact addition from mesh adverts
- **Message Filtering** — Filter messages per channel via checkboxes
- **Message Route Visualization** — Click any message to open a detailed route page showing the path (hops) through the mesh network on an interactive map, with a hop summary, route table and reply panel
- **Message Archive** — All messages and RX log entries are persisted to disk with configurable retention. Browse archived messages via the archive viewer with filters (channel, time range, text search), pagination and inline route tables
<!-- ADDED: Message Archive feature was missing from features list -->
- **Room Server Support** — Login to Room Servers directly from the GUI. Each Room Server gets a dedicated panel with message display, send functionality and login/logout controls. Passwords are stored securely outside the repository. Message author attribution correctly resolves the real sender from signed messages
<!-- ADDED: Room Server feature (v5.7.0) -->
- **Dynamic Channel Discovery** — Channels are automatically discovered from the device at startup via BLE probing, eliminating the need to manually configure `CHANNELS_CONFIG`
<!-- ADDED: Dynamic channel discovery (v5.7.0) -->
- **Keyword Bot** — Built-in auto-reply bot that responds to configurable keywords on selected channels, with cooldown and loop prevention
- **Packet Decoding** — Raw LoRa packets from RX log are decoded and decrypted using channel keys, providing message hashes, path hashes and hop data
- **Message Deduplication** — Dual-strategy dedup (hash-based and content-based) prevents duplicate messages from appearing
- **Local Cache** — Device info, contacts and channel keys are cached to disk (`~/.meshcore-gui/cache/`) so the GUI is instantly populated on startup from the last known state, even before BLE connects. Contacts from the device are merged with cached contacts so offline nodes are preserved. Channel keys that fail to load at startup are retried in the background every 30 seconds
- **Periodic Contact Refresh** — Contacts are automatically refreshed from the device at a configurable interval (default: 5 minutes) and merged with the cache
- **Threaded Architecture** — BLE communication in separate thread for stable UI

## Screenshots

<img width="1628" height="844" alt="Screenshot from 2026-02-08 21-43-29" src="https://github.com/user-attachments/assets/1246f899-9d3a-4750-90cb-b5b26a4493d9" />
<img width="681" height="820" alt="Screenshot from 2026-02-05 12-23-24" src="https://github.com/user-attachments/assets/c8fba47a-470d-4c21-8ac2-48547bfeae3e" />
<img width="1601" height="1020" alt="Screenshot from 2026-02-08 21-45-32" src="https://github.com/user-attachments/assets/65e4588c-4340-46e5-a649-b01b9019e7bf" />


## Requirements

- Python 3.10+
- Bluetooth Low Energy compatible adapter (built-in or USB)
- MeshCore device with BLE Companion firmware

### Platform support

| Platform | BLE Backend | Status |
|---|---|---|
| Linux (Ubuntu/Debian) | BlueZ/D-Bus | ✅ Tested |
| macOS | CoreBluetooth | ⬜ Untested |
| Windows 10/11 | WinRT | ⬜ Untested |

## Installation

### 1. System dependencies

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3-pip python3-venv bluetooth bluez
```

**macOS:**
```bash
# Python 3.10+ via Homebrew (if not already installed)
brew install python
```
No additional Bluetooth packages needed — macOS has CoreBluetooth built in.

**Windows:**
- Install [Python 3.10+](https://www.python.org/downloads/) (check "Add to PATH" during installation)
- No additional Bluetooth packages needed — Windows 10/11 has WinRT built in.

### 2. Clone the repository

```bash
git clone https://github.com/pe1hvh/meshcore-gui.git
cd meshcore-gui
```

### 3. Create virtual environment

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 4. Install Python packages

```bash
pip install nicegui meshcore bleak meshcoredecoder
```

## Usage

### 1. Activate the virtual environment

**Linux / macOS:**
```bash
cd meshcore-gui
source venv/bin/activate
```

**Windows:**
```cmd
cd meshcore-gui
venv\Scripts\activate
```

### 2. Find your BLE device address

**Linux:**
```bash
bluetoothctl scan on
```
Look for your MeshCore device and note the MAC address (e.g., `AA:BB:CC:DD:EE:FF`).

**macOS / Windows:**
```bash
python -c "
import asyncio
from bleak import BleakScanner
async def scan():
    devices = await BleakScanner.discover(5.0)
    for d in devices:
        if 'MeshCore' in (d.name or ''):
            print(f'{d.address}  {d.name}')
asyncio.run(scan())
"
```
On macOS the address will be a UUID (e.g., `12345678-ABCD-...`) rather than a MAC address.

### 3. Configure channels (optional)

Channels are automatically discovered from the device at startup via BLE. No manual configuration is required.

If you want to cache the discovered channel list to disk (for faster startup), set `CHANNEL_CACHE_ENABLED = True` in `meshcore_gui/config.py`. By default, channels are always fetched fresh from the device.

> **Note:** The maximum number of channel slots probed can be adjusted via `MAX_CHANNELS` in `config.py` (default: 8, which matches the MeshCore protocol limit).

### 4. Start the GUI

```bash
python meshcore_gui.py AA:BB:CC:DD:EE:FF
```

Replace `AA:BB:CC:DD:EE:FF` with the MAC address of your device.

For verbose debug logging:

```bash
python meshcore_gui.py AA:BB:CC:DD:EE:FF --debug-on
```

### 5. Open the interface

The GUI opens automatically in your browser at `http://localhost:8080`

## Configuration

| Setting | Location | Description |
|---------|----------|-------------|
| `DEBUG` | `meshcore_gui/config.py` | Set to `True` for verbose logging (or use `--debug-on`) |
| `MAX_CHANNELS` | `meshcore_gui/config.py` | Maximum channel slots to probe on device (default: 8) |
<!-- CHANGED: Replaced CHANNELS_CONFIG with MAX_CHANNELS (v5.7.0) -->
| `CHANNEL_CACHE_ENABLED` | `meshcore_gui/config.py` | Cache discovered channels to disk for faster startup (default: `False` — always fresh from device) |
<!-- ADDED: CHANNEL_CACHE_ENABLED setting (v5.7.0) -->
| `CONTACT_REFRESH_SECONDS` | `meshcore_gui/config.py` | Interval between periodic contact refreshes (default: 300s / 5 minutes) |
| `MESSAGE_RETENTION_DAYS` | `meshcore_gui/config.py` | Retention period for archived messages (default: 30 days) |
| `RXLOG_RETENTION_DAYS` | `meshcore_gui/config.py` | Retention period for archived RX log entries (default: 7 days) |
| `CONTACT_RETENTION_DAYS` | `meshcore_gui/config.py` | Retention period for cached contacts (default: 90 days) |
<!-- ADDED: Three retention settings above were missing from config table -->
| `KEY_RETRY_INTERVAL` | `meshcore_gui/ble/worker.py` | Interval between background retry attempts for missing channel keys (default: 30s) |
| `BOT_DEVICE_NAME` | `meshcore_gui/config.py` | Device name set when bot mode is active (default: `;NL-OV-ZWL-STDSHGN-WKC Bot`) |
<!-- ADDED: BOT_DEVICE_NAME setting added in v5.5.0 -->
| `BOT_CHANNELS` | `meshcore_gui/services/bot.py` | Channel indices the bot listens on |
<!-- CHANGED: BOT_NAME removed in v5.5.0 — bot replies no longer include a name prefix -->
| `BOT_COOLDOWN_SECONDS` | `meshcore_gui/services/bot.py` | Minimum seconds between bot replies |
| `BOT_KEYWORDS` | `meshcore_gui/services/bot.py` | Keyword → reply template mapping |
| Room passwords | `~/.meshcore-gui/room_passwords/<ADDRESS>.json` | Per-device Room Server passwords (managed via GUI, stored outside repository) |
<!-- ADDED: Room password store location (v5.7.0) -->
| BLE Address | Command line argument | |

## Functionality

### Device Info
- Name, frequency, SF/BW, TX power, location, firmware version

### Contacts
- List of known nodes with type and location
- Click on a contact to send a DM (or add a Room Server panel for type=3 contacts)
<!-- CHANGED: Contact click now dispatches by type (v5.7.0) -->
- **Pin/Unpin**: Checkbox per contact to pin it — pinned contacts are sorted to the top and visually marked with a yellow background. Pin state is persisted locally and survives app restart.
- **Individual delete**: 🗑️ button per unpinned contact to remove a single contact from the device with confirmation dialog. Pinned contacts are protected.
<!-- ADDED: Individual contact deletion (v5.7.0) -->
- **Bulk delete**: "🧹 Clean up" button removes all unpinned contacts from the device in one action, with a confirmation dialog showing how many will be removed vs. kept. Optional "Also delete from history" checkbox to clear locally cached data.
<!-- CHANGED: Added "Also delete from history" option (v5.7.0) -->
- **Auto-add toggle**: "📥 Auto-add" checkbox controls whether the device automatically adds new contacts when it receives adverts from other mesh nodes. Disabled by default to prevent the contact list from filling up.

### Map
- OpenStreetMap with markers for own position and contacts
- Shows your own position (blue marker)
- Automatically centers on your own position

### Channel Messages
- Select a channel in the dropdown
- Type your message and click "Send"
- Received messages appear in the messages list
- Filter messages via the checkboxes

### Direct Messages (DM)
- Click on a contact in the contacts list
- A dialog opens where you can type your message
- Click "Send" to send the DM

### Message Route Visualization

Click on any message in the messages list to open a route page in a new tab. The route page shows:

- **Hop summary** — Number of hops and SNR
- **Interactive map** — Leaflet map with markers for sender, repeaters and receiver, connected by a polyline showing the message path
- **Route table** — Detailed table with each hop: name, ID (first byte of public key), node type and GPS coordinates
- **Reply panel** — Pre-filled reply message with route acknowledgement (sender, path length, repeater IDs)

Route data is resolved from two sources (in priority order):
1. **RX log packet decode** — Path hashes extracted from the raw LoRa packet via `meshcoredecoder`
2. **Contact out_path** — Stored route from the sender's contact record (fallback)

<!-- ADDED: Room Server section (v5.7.0) -->
### Room Server

Room Servers (type=3 contacts) allow group-style messaging via a shared server node in the mesh network.

**Adding a Room Server:** Click on any Room Server contact (🏠 icon) in the contacts list. A dialog opens where you enter the room password. Click "Add & Login" to create a dedicated room panel and log in.

**Room panel features:**
- Each Room Server gets its own card in the centre column below the Messages panel
- After login: the password field is replaced by a Logout button
- Messages from the room are displayed in the card with correct author attribution (the real sender, not the room server)
- Send messages to the room via the input field and Send button
- Room panels are restored from stored passwords on app restart

**How it works under the hood:**
- Login via `send_login(pubkey, password)` — the Room Server authenticates and starts pushing messages over LoRa RF
- Messages arrive asynchronously via `MESSAGES_WAITING` events (event-driven, no polling)
- Room messages use `txt_type=2` (signed), where the `signature` field contains the 4-byte pubkey prefix of the real author
- The first message may take 10–75 seconds to arrive after login (inherent LoRa RF latency)
- Passwords are stored in `~/.meshcore-gui/room_passwords/` outside the repository

**Note:** The Room Server pushes messages round-robin to all logged-in clients. With many clients or large message buffers, it can take several minutes to receive all historical messages.

### Message Archive

All incoming messages and RX log entries are automatically persisted to disk in `~/.meshcore-gui/archive/`. One JSON file per data type per BLE device address.

Click the **📚 Archive** button in the Messages panel header to open the archive viewer in a new tab. The archive viewer provides:

- **Pagination** — 50 messages per page, with Previous/Next navigation
- **Channel filter** — Filter by specific channel or view all
- **Time range filter** — Last 24 hours, 7 days, 30 days, 90 days, or all time
- **Text search** — Case-insensitive search in message text
- **Inline route tables** — Expandable route display per message (sender, repeaters, receiver with names and IDs)
- **Reply from archive** — Expandable reply panel per message with pre-filled @sender mention

Old data is automatically cleaned up based on configurable retention periods (`MESSAGE_RETENTION_DAYS`, `RXLOG_RETENTION_DAYS` in `config.py`).

### Local Cache

Device info, contacts and channel keys are automatically cached to disk in `~/.meshcore-gui/cache/`. One JSON file is created per BLE device address.

**Startup behaviour:**
1. Cache is loaded first — GUI is immediately populated with the last known state
2. BLE connection is established in the background
3. Fresh data from the device updates both the GUI and the cache

**Channel key loading:**

Channel key loading uses a cache-first strategy with BLE fallback:

1. Cached keys are loaded first and never overwritten by name-derived fallbacks
2. Each channel is queried from the device at startup
3. Channels that fail are retried in the background every 30 seconds
4. Successfully loaded keys are immediately written to the cache for next startup

> **Note:** Prior to v5.6.0, BLE commands frequently timed out due to a race condition in the meshcore SDK. The patched SDK resolves this — see [Known Limitations](#known-limitations) for installation instructions. Since v5.7.0, channels are discovered dynamically from the device, eliminating the need for manual `CHANNELS_CONFIG` setup.

**Contact merge strategy:**
- New contacts from the device are added to the cache with a `last_seen` timestamp
- Existing contacts are updated (fresh data wins)
- Contacts only in cache (node offline) are preserved

If BLE connection fails, the GUI remains usable with cached data and shows an offline status.

### Keyword Bot

The built-in bot automatically replies to messages containing recognised keywords. Enable or disable it via the 🤖 BOT checkbox in the filter bar.

<!-- CHANGED: Bot device name switching feature added in v5.5.0 -->
**Device name switching:** When the BOT checkbox is enabled, the device name is automatically changed to the configured `BOT_DEVICE_NAME` (default: `;NL-OV-ZWL-STDSHGN-WKC Bot`). The original device name is saved and restored when bot mode is disabled. This allows the mesh network to identify the node as a bot by its name.

**Default keywords:**

<!-- CHANGED: Removed "Zwolle Bot:" prefix from example replies — bot replies no longer include a name prefix (v5.5.0) -->

| Keyword | Reply |
|---------|-------|
| `test` | `<sender>, rcvd \| SNR <snr> \| path(<hops>); <repeaters>` |
| `ping` | `Pong!` |
| `help` | `test, ping, help` |

**Safety guards:**
- Only replies on configured channels (`BOT_CHANNELS`)
- Ignores own messages and messages from other bots (names ending in "Bot")
- Cooldown period between replies (default: 5 seconds)

**Customisation:** Edit `BOT_KEYWORDS` in `meshcore_gui/services/bot.py`. Templates support `{sender}`, `{snr}` and `{path}` variables.

### RX Log
- Received packets with SNR and type

### Actions
- Refresh data
- Send advertisement

## Architecture

<!-- CHANGED: Architecture diagram updated — added RoomServerPanel and RoomPasswordStore (v5.7.0) -->

```
┌─────────────────┐     ┌─────────────────┐
│   Main Thread   │     │   BLE Thread    │
│   (NiceGUI)     │     │   (asyncio)     │
│                 │     │                 │
│  ┌───────────┐  │     │  ┌───────────┐  │
│  │ Dashboard │◄─┼──┬──┼─►│ BLEWorker │  │
│  └───────────┘  │  │  │  └─────┬─────┘  │
│        │        │  │  │        │        │
│        ▼        │  │  │   ┌────┴────┐   │
│  ┌───────────┐  │  │  │   │Commands │   │
│  │  Timer    │  │  │  │   │Events   │   │
│  │  (500ms)  │  │  │  │   │Decoder  │   │
│  └───────────┘  │  │  │   └────┬────┘   │
│        │        │  │  │        │        │
│  ┌─────┴─────┐  │  │  │   ┌────┴────┐   │
│  │  Panels   │  │  │  │   │   Bot   │   │
│  │  RoutePage│  │  │  │   │  Dedup  │   │
│  │ ArchivePg │  │  │  │   │  Cache  │   │
│  │ RoomSrvPnl│  │  │  │   └─────────┘   │
│  └───────────┘  │  │  └─────────────────┘
└─────────────────┘  │
              ┌──────┴──────┐
              │ SharedData  │     ┌───────────────┐
              │ (thread-    │     │ DeviceCache   │
              │  safe)      │     │ (~/.meshcore- │
              └──────┬──────┘     │  gui/cache/)  │
                     │            └───────────────┘
              ┌──────┴──────┐     ┌───────────────┐
              │ Message     │     │ PinStore      │
              │ Archive     │     │ Contact       │
              │ (~/.meshcore│     │  Cleaner      │
              │ -gui/       │     │ RoomPassword  │
              │  archive/)  │     │  Store        │
              └─────────────┘     └───────────────┘
```
```

- **BLEWorker**: Runs in separate thread with its own asyncio loop, with background retry for missing channel keys
- **CommandHandler**: Executes commands (send message, advert, refresh, purge unpinned, set auto-add, set bot name, restore name, login room, send room msg, remove single contact)
<!-- CHANGED: Added room server and single contact commands (v5.7.0) -->
- **EventHandler**: Processes incoming BLE events (messages, RX log)
- **PacketDecoder**: Decodes raw LoRa packets and extracts route data
- **MeshBot**: Keyword-triggered auto-reply on configured channels with automatic device name switching
<!-- CHANGED: Added device name switching to MeshBot description (v5.5.0) -->
- **DualDeduplicator**: Prevents duplicate messages (hash-based + content-based)
- **DeviceCache**: Local JSON cache per device for instant startup and offline resilience
- **MessageArchive**: Persistent storage for messages and RX log with configurable retention and automatic cleanup
<!-- ADDED: MessageArchive component description -->
- **PinStore**: Persistent pin state storage per device (JSON-backed)
- **ContactCleanerService**: Bulk-delete logic for unpinned contacts with statistics
- **RoomServerPanel**: Per-room-server card management with login/logout, message display and send functionality
<!-- ADDED: RoomServerPanel component (v5.7.0) -->
- **RoomPasswordStore**: Persistent Room Server password storage per device in `~/.meshcore-gui/room_passwords/` (JSON-backed, analogous to PinStore)
<!-- ADDED: RoomPasswordStore component (v5.7.0) -->
- **SharedData**: Thread-safe data sharing between BLE and GUI via Protocol interfaces
- **DashboardPage**: Main GUI with modular panels (device, contacts, map, messages, etc.)
- **RoutePage**: Standalone route visualization page opened per message
- **ArchivePage**: Archive viewer with filters, pagination and inline route tables
<!-- ADDED: ArchivePage component description -->
- **Communication**: Via command queue (GUI→BLE) and shared state with flags (BLE→GUI)

## Known Limitations

1. **Channel discovery timing** — Dynamic channel discovery probes the device at startup; on very slow BLE connections, some channels may be missed on first attempt. Channels are retried in the background and cached for subsequent startups when `CHANNEL_CACHE_ENABLED = True`
<!-- CHANGED: Replaced "Channels hardcoded" with dynamic discovery note (v5.7.0) -->
2. **BLE command reliability** — Resolved in v5.6.0. The meshcore SDK previously had a race condition where device responses were missed. The patched SDK ([PR #52](https://github.com/meshcore-dev/meshcore_py/pull/52)) uses subscribe-before-send to eliminate this. Until merged upstream, install the patched version: `pip install --force-reinstall git+https://github.com/PE1HVH/meshcore_py.git@fix/event-race-condition`
3. **Initial load time** — GUI waits for BLE data before the first render is complete (mitigated by cache: if cached data exists, the GUI populates instantly)
4. **Archive route visualization** — Route data for archived messages depends on contacts currently in memory; archived-only messages without recent contact data may show incomplete routes
<!-- ADDED: Archive-related limitation -->
5. **Room Server message latency** — Room Server messages travel over LoRa RF and arrive asynchronously (10–75 seconds per message). With many logged-in clients, receiving all historical messages can take 10+ minutes due to the round-robin push protocol
<!-- ADDED: Room Server latency limitation (v5.7.0) -->

## Troubleshooting

### Linux

For comprehensive Linux BLE troubleshooting (including the `EOFError` / `start_notify` issue), see [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

#### Quick fixes

##### GUI remains empty / BLE connection fails

1. First disconnect any existing BLE connections:
   ```bash
   bluetoothctl disconnect AA:BB:CC:DD:EE:FF
   ```
2. Wait 2 seconds:
   ```bash
   sleep 2
   ```
3. Restart the GUI:
   ```bash
   python meshcore_gui.py AA:BB:CC:DD:EE:FF
   ```

##### Bluetooth permissions

```bash
sudo usermod -a -G bluetooth $USER
# Log out and back in
```

### macOS

- Make sure Bluetooth is enabled in System Settings
- Grant your terminal app Bluetooth access when prompted
- Use the UUID address from BleakScanner, not a MAC address

### Windows

- Make sure Bluetooth is enabled in Settings → Bluetooth & devices
- Run the terminal as a regular user (not as Administrator — WinRT BLE can behave unexpectedly with elevated privileges)

### All platforms

#### Device not found

Make sure the MeshCore device is powered on and in BLE Companion mode. Run the BleakScanner script from the Usage section to verify it is visible.

#### Messages not arriving

- Check if your channels are correctly configured
- Use `meshcli` to verify that messages are arriving

#### Clearing the cache

If cached data causes issues (e.g. stale contacts), delete the cache file:

```bash
rm ~/.meshcore-gui/cache/*.json
```

The cache will be recreated on the next successful BLE connection.

## Development

### Debug mode

Enable via command line flag:

```bash
python meshcore_gui.py AA:BB:CC:DD:EE:FF --debug-on
```

Or set `DEBUG = True` in `meshcore_gui/config.py`.

### Project structure

<!-- CHANGED: Project structure updated — added archive_page.py and message_archive.py -->

```
meshcore-gui/
├── meshcore_gui.py                  # Entry point
├── meshcore_gui/                    # Application package
│   ├── __init__.py
│   ├── __main__.py                  # Alternative entry: python -m meshcore_gui
│   ├── config.py                    # DEBUG flag, channel discovery settings (MAX_CHANNELS, CHANNEL_CACHE_ENABLED), refresh interval, retention settings, BOT_DEVICE_NAME
<!-- CHANGED: Updated config.py description — removed CHANNELS_CONFIG, added dynamic channel settings (v5.7.0) -->
│   ├── ble/                         # BLE communication layer
│   │   ├── __init__.py
│   │   ├── worker.py                # BLE thread, connection lifecycle, cache-first startup, background key retry
│   │   ├── commands.py              # Command execution (send, refresh, advert)
│   │   ├── events.py                # Event callbacks (messages, RX log)
│   │   └── packet_decoder.py        # Raw LoRa packet decoding via meshcoredecoder
│   ├── core/                        # Domain models and shared state
│   │   ├── __init__.py
│   │   ├── models.py                # Dataclasses: Message, Contact, DeviceInfo, RxLogEntry, RouteNode
│   │   ├── shared_data.py           # Thread-safe shared data store
│   │   └── protocols.py             # Protocol interfaces (ISP/DIP)
│   ├── gui/                         # NiceGUI web interface
│   │   ├── __init__.py
│   │   ├── constants.py             # UI display constants
│   │   ├── dashboard.py             # Main dashboard page orchestrator
│   │   ├── route_page.py            # Message route visualization page
│   │   ├── archive_page.py          # Message archive viewer with filters and pagination
│   │   └── panels/                  # Modular UI panels
│   │       ├── __init__.py
│   │       ├── device_panel.py      # Device info display
│   │       ├── contacts_panel.py    # Contacts list with DM, pin/unpin, bulk delete, auto-add toggle
│   │       ├── map_panel.py         # Leaflet map
│   │       ├── input_panel.py       # Message input and channel select
│   │       ├── filter_panel.py      # Channel filters and bot toggle
│   │       ├── messages_panel.py    # Filtered message display with archive button
│   │       ├── actions_panel.py     # Refresh and advert buttons
│   │       ├── room_server_panel.py # Per-room-server card with login/logout and messages
<!-- ADDED: room_server_panel.py (v5.7.0) -->
│   │       └── rxlog_panel.py       # RX log table
│   └── services/                    # Business logic
│       ├── __init__.py
│       ├── bot.py                   # Keyword-triggered auto-reply bot
│       ├── cache.py                 # Local JSON cache per BLE device
│       ├── contact_cleaner.py       # Bulk-delete logic for unpinned contacts
│       ├── dedup.py                 # Message deduplication
│       ├── message_archive.py       # Persistent message and RX log archive
│       ├── pin_store.py             # Persistent pin state storage per device
│       ├── room_password_store.py   # Persistent Room Server password storage per device
<!-- ADDED: room_password_store.py (v5.7.0) -->
│       └── route_builder.py         # Route data construction
├── docs/
│   ├── TROUBLESHOOTING.md           # BLE troubleshooting guide (Linux)
│   ├── MeshCore_GUI_Design.docx     # Design document
│   ├── ble_capture_workflow_t_1000_e_explanation.md
│   └── ble_capture_workflow_t_1000_e_uitleg.md
├── .gitattributes
├── .gitignore
├── LICENSE
├── CHANGELOG.md
└── README.md
```

## Disclaimer

This is an **independent community project** and is not affiliated with or endorsed by the official [MeshCore](https://github.com/meshcore-dev) development team. It is built on top of the open-source `meshcore` Python library and `bleak` BLE library.

## License

MIT License - see LICENSE file

## Author

**PE1HVH** — [GitHub](https://github.com/pe1hvh)

## Acknowledgments

- [MeshCore](https://github.com/meshcore-dev) — Mesh networking firmware and protocol
- [meshcore_py](https://github.com/meshcore-dev/meshcore_py) — Python bindings for MeshCore
- [meshcore-cli](https://github.com/meshcore-dev/meshcore-cli) — Command line interface
- [meshcoredecoder](https://github.com/meshcore-dev/meshcoredecoder) — LoRa packet decoder and channel crypto
- [NiceGUI](https://nicegui.io/) — Python GUI framework
- [Bleak](https://github.com/hbldh/bleak) — Cross-platform Bluetooth Low Energy library
