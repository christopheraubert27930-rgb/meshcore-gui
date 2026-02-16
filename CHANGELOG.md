# CHANGELOG

<!-- CHANGED: Title changed from "CHANGELOG: Message & Metadata Persistence" to "CHANGELOG" — 
     a root-level CHANGELOG.md should be project-wide, not feature-specific. -->

All notable changes to MeshCore GUI are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/).

---

## [1.9.4] - 2026-02-16 — BLE Address Log Prefix & Entry Point Cleanup

### Added
- ✅ **BLE address prefix in log filename** — Log file is now named `<BLE_ADDRESS>_meshcore_gui.log` (e.g. `AA_BB_CC_DD_EE_FF_meshcore_gui.log`) instead of the generic `meshcore_gui.log`. Makes it easy to identify which device produced which log file when running multiple instances
  - New helper `_sanitize_ble_address()` strips `literal:` prefix and replaces colons with underscores
  - New function `configure_log_file(ble_address)` updates `LOG_FILE` at runtime before the logger is initialised
  - Rotated backups follow the same naming pattern automatically

### Removed
- ❌ **`meshcore_gui/meshcore_gui.py`** — Redundant copy of `main()` that was never imported. All three entry points (`meshcore_gui.py` root, `__main__.py`, and `meshcore_gui/meshcore_gui.py`) contained near-identical copies of the same logic, causing changes to be missed (as demonstrated by this fix). `__main__.py` is now the single source of truth; root `meshcore_gui.py` is a thin wrapper that imports from it

### Changed
- 🔄 `config.py`: Added `_sanitize_ble_address()` and `configure_log_file()`; version bumped to `1.9.4`
- 🔄 `__main__.py`: Added `config.configure_log_file(ble_address)` call before any debug output
- 🔄 `meshcore_gui.py` (root): Reduced to 4-line wrapper importing `main` from `__main__`

### Impact
- Log files are now identifiable per BLE device
- Single source of truth for `main()` eliminates future sync issues between entry points
- Both startup methods (`python meshcore_gui.py` and `python -m meshcore_gui`) remain functional
- No breaking changes — defaults and all existing behaviour unchanged

---

## [1.9.3] - 2026-02-16 — CLI Arguments & BLE PIN Fix

### Fixed
- 🛠 **BLE PIN not applied from CLI** — `ble/worker.py` imported `BLE_PIN` as a constant at module load time (`from config import BLE_PIN`), capturing the default value `"123456"` before CLI parsing could override `config.BLE_PIN`. Changed to runtime access via `config.BLE_PIN` so the `--ble-pin` parameter is correctly passed to the BLE agent

### Added
- ✅ **`--ble-pin` CLI argument** — All three entry points now accept `--ble-pin PIN` or `--ble-pin=PIN` to override the BLE pairing PIN at startup without editing `config.py`
- ✅ **`--port` CLI argument** — All three entry points now accept `--port PORT` or `--port=PORT` to set the web UI port (default: 8081). Previously hardcoded in `ui.run()`
- ✅ **Improved CLI argument parser** — Replaced simple flag list with a proper parser that handles both `--key value` and `--key=value` formats. Correctly skips flag values so they are not mistaken for positional arguments

### Changed
- 🔄 `ble/worker.py`: Removed `BLE_PIN` from value-imports; added `import meshcore_gui.config as _config`; `BleAgentManager` now reads `_config.BLE_PIN` at runtime instead of the import-time copy
- 🔄 `meshcore_gui.py` (root), `__main__.py`, `meshcore_gui/meshcore_gui.py`: Rewritten argument parser supporting `--key=value` format; added `--ble-pin` and `--port` arguments; startup banner now shows BLE PIN and port; `ui.run()` uses `ui_port` variable instead of hardcoded `8081`
- 🔄 `config.py`: Version bumped to `1.9.3`

### Impact
- BLE PIN from `--ble-pin` CLI argument is now correctly used for pairing
- Web UI port is configurable without code changes
- All `--key=value` and `--key value` formats work consistently
- No breaking changes — defaults unchanged (PIN: `123456`, port: `8081`)

---

## [1.9.2] - 2026-02-16 — Bugfix: Map Default Location & Payload Type Decoding

### Fixed
- 🛠 **Map centred on hardcoded Zwolle instead of device location** — All Leaflet maps used magic-number coordinates `(52.5, 6.0)` as initial centre and fallback. These are now replaced by a single configurable constant `DEFAULT_MAP_CENTER` in `config.py`. Once the device reports a valid `adv_lat`/`adv_lon`, maps re-centre on the actual device position (existing behaviour, unchanged)
- 🛠 **Payload type shown as raw integer** — Payload type is now retrieved from the decoded payload and translated to human-readable text using MeshCoreDecoder functions, instead of displaying the raw numeric type value

### Changed
- 🔄 `config.py`: Added `DEFAULT_MAP_CENTER` (default: `(52.5168, 6.0830)`) and `DEFAULT_MAP_ZOOM` (default: `9`) constants in new **MAP DEFAULTS** section. Version bumped to `1.9.2`
- 🔄 `gui/panels/map_panel.py`: Imports `DEFAULT_MAP_CENTER` and `DEFAULT_MAP_ZOOM` from config; `ui.leaflet(center=...)` uses config constants instead of hardcoded values
- 🔄 `gui/route_page.py`: Imports `DEFAULT_MAP_CENTER` and `DEFAULT_MAP_ZOOM` from config; fallback coordinates (`or 52.5` / `or 6.0`) replaced by `DEFAULT_MAP_CENTER[0]` / `[1]`; zoom uses `DEFAULT_MAP_ZOOM`

### Impact
- Map default location is now a single-point-of-change in `config.py`
- Payload type is displayed as readable text instead of a raw number
- No breaking changes — all existing map behaviour (re-centre on device position, contact markers) unchanged

---

## [1.9.1] - 2026-02-14 — Bugfix: Dual Reconnect Conflict

### Fixed
- 🛠 **Library reconnect interfered with application reconnect** — The meshcore library's internal `auto_reconnect` (visible in logs as `"Attempting reconnection 1/3"`) ran a fast 3-attempt reconnect cycle without bond cleanup. This prevented the application's own `reconnect_loop` (which does `remove_bond()` + backoff) from succeeding, because BlueZ retained a stale bond → `"failed to discover service"`

### Changed
- 🔄 `ble/worker.py`: Set `auto_reconnect=False` in both `MeshCore.create_ble()` call sites (`_connect()` and `_create_fresh_connection()`), so only the application's bond-aware `reconnect_loop` handles reconnection
- 🔄 `ble/worker.py`: Added `"failed to discover"` and `"service discovery"` to disconnect detection keywords for defensive coverage

### Impact
- Eliminates the ~9 second wasted library reconnect cycle after every BLE disconnect
- Application's `reconnect_loop` (with bond cleanup) now runs immediately after disconnect detection
- No breaking changes — the application reconnect logic was already fully functional

---

## [1.9.0] - 2026-02-14 — BLE Connection Stability

### Added
- ✅ **Built-in BLE PIN agent** — New `ble/ble_agent.py` registers a D-Bus agent with BlueZ to handle PIN pairing requests automatically. Eliminates the need for external `bt-agent.service` and `bluez-tools` package
  - Uses `dbus_fast` (already a dependency of `bleak`, no new packages)
  - Supports `RequestPinCode`, `RequestPasskey`, `DisplayPasskey`, `RequestConfirmation`, `AuthorizeService` callbacks
  - Configurable PIN via `BLE_PIN` in `config.py` (default: `123456`)
- ✅ **Automatic bond cleanup** — New `ble/ble_reconnect.py` provides `remove_bond()` function that removes stale BLE bonds via D-Bus, equivalent to `bluetoothctl remove <address>`. Called automatically on startup and before each reconnect attempt
- ✅ **Automatic reconnect after disconnect** — BLEWorker main loop now detects BLE disconnects (via connection error exceptions) and automatically triggers a reconnect sequence: bond removal → linear backoff wait → fresh connection → re-wire handlers → reload device data
  - Configurable via `RECONNECT_MAX_RETRIES` (default: 5) and `RECONNECT_BASE_DELAY` (default: 5.0s)
  - After all retries exhausted: waits 60s then starts a new retry cycle (infinite recovery)
- ✅ **Generic install script** — `install_ble_stable.sh` auto-detects user, project directory, venv path and entry point to generate systemd service and D-Bus policy. Supports `--uninstall` flag

### Changed
- 🔄 **`ble/worker.py`** — `_async_main()` rewritten with three phases: (1) start PIN agent, (2) remove stale bond, (3) connect + main loop with disconnect detection. Reconnect logic re-wires all event handlers and reloads device data after successful reconnection
- 🔄 **`config.py`** — Added `BLE_PIN`, `RECONNECT_MAX_RETRIES`, `RECONNECT_BASE_DELAY` constants

### Removed
- ❌ **`bt-agent.service` dependency** — No longer needed; PIN pairing is handled by the built-in agent
- ❌ **`bluez-tools` system package** — No longer needed
- ❌ **`~/.meshcore-ble-pin` file** — No longer needed
- ❌ **Manual `bluetoothctl remove` before startup** — Handled automatically
- ❌ **`ExecStartPre` in systemd service** — Bond cleanup is internal

### Impact
- Zero external dependencies for BLE pairing on Linux
- Automatic recovery from the T1000e ~2 hour BLE disconnect issue
- No manual intervention needed after BLE connection loss
- Single systemd service (`meshcore-gui.service`) manages everything
- No breaking changes to existing functionality

---

## [1.8.0] - 2026-02-14 — DRY Message Construction & Archive Layout Unification

### Fixed
- 🛠 **Case-sensitive prefix matching** — `get_contact_name_by_prefix()` and `get_contact_by_prefix()` in `shared_data.py` failed to match path hashes (uppercase, e.g. `'B8'`) against contact pubkeys (lowercase, e.g. `'b8a3f2...'`). Added `.lower()` to both sides of the comparison, consistent with `_resolve_path_names()` which already had it
- 🛠 **Route page 404 from archive** — Archive page linked to `/route/{hash}` but route was registered as `/route/{msg_index:int}`, causing a JSON parse error for hex hash strings. Route parameter changed to `str` with 3-strategy lookup (index → memory hash → archive fallback)
- 🛠 **Three entry points out of sync** — `meshcore_gui.py` (root), `meshcore_gui/meshcore_gui.py` (inner) and `meshcore_gui/__main__.py` had diverging route registrations. All three now use identical `/route/{msg_key}` with `str` parameter

### Changed
- 🔄 **`core/models.py` — DRY factory methods and formatting**
  - `Message.now_timestamp()`: static method replacing 7× hardcoded `datetime.now().strftime('%H:%M:%S')` across `events.py` and `commands.py`
  - `Message.incoming()`: classmethod factory for received messages (`direction='in'`, auto-timestamp)
  - `Message.outgoing()`: classmethod factory for sent messages (`sender='Me'`, `direction='out'`, auto-timestamp)
  - `Message.format_line(channel_names)`: single-line display formatting (`"12:34:56 ← [Public] [2h✓] PE1ABC: Hello mesh!"`), replacing duplicate inline formatting in `messages_panel.py` and `archive_page.py`
- 🔄 **`ble/events.py`** — 4× `Message(...)` constructors replaced by `Message.incoming()`; `datetime` import removed
- 🔄 **`ble/commands.py`** — 3× `Message(...)` constructors replaced by `Message.outgoing()`; `datetime` import removed
- 🔄 **`gui/panels/messages_panel.py`** — 15 lines inline formatting replaced by single `msg.format_line(channel_names)` call
- 🔄 **`gui/archive_page.py` — Layout unified with main page**
  - Multi-row card layout replaced by single-line `msg.format_line()` in monospace container (same style as main page)
  - DM added to channel filter dropdown (post-filter on `channel is None`)
  - Message click opens `/route/{message_hash}` in new tab (was: no click handler on archive messages)
  - Removed `_render_message_card()` (98 lines) and `_render_archive_route()` (75 lines)
  - Removed `RouteBuilder` dependency and `TYPE_LABELS` import
  - File reduced from 445 to 267 lines
- 🔄 **`gui/route_page.py`** — `render(msg_index: int)` → `render(msg_key: str)` with 3-strategy message lookup: (1) numeric index from in-memory list, (2) hash match in memory, (3) `archive.get_message_by_hash()` fallback
- 🔄 **`services/message_archive.py`** — New method `get_message_by_hash(hash)` for single-message lookup by packet hash
- 🔄 **`__main__.py` + `meshcore_gui.py` (both)** — Route changed from `/route/{msg_index}` (int) to `/route/{msg_key}` (str)

### Impact
- DRY: timestamp formatting 7→1 definition, message construction 7→2 factories, line formatting 2→1 method
- Archive page visually consistent with main messages panel (single-line, monospace)
- Archive messages now clickable to open route visualization (was: only in-memory messages)
- Case-insensitive prefix matching fixes path name resolution for contacts with uppercase path hashes
- No breaking changes to BLE protocol handling, dedup, bot, or data storage

### Known Limitations
- DM filter in archive uses post-filtering (query without channel filter + filter on `channel is None`); becomes exact when `query_messages()` gets native DM support

### Parked for later
- Multi-path tracking (enrich RxLogEntry with multiple path observations)
- Events correlation improvements (only if proven data loss after `.lower()` fix)

---

## [1.7.0] - 2026-02-13 — Archive Channel Name Persistence

### Added
- ✅ **Channel name stored in archive** — Messages now persist `channel_name` alongside the numeric `channel` index in `<ADDRESS>_messages.json`, so archived messages retain their human-readable channel name even when the device is not connected
  - `Message` dataclass: new field `channel_name: str` (default `""`, backward compatible)
  - `SharedData.add_message()`: automatically resolves `channel_name` from the live channels list when not already set (new helper `_resolve_channel_name()`)
  - `MessageArchive.add_message()`: writes `channel_name` to the JSON dict
- ✅ **Archive channel selector built from archived data** — Channel filter dropdown on `/archive` now populated via `SELECT DISTINCT channel_name` on the archive instead of the live BLE channels list
  - New method `MessageArchive.get_distinct_channel_names()` returns sorted unique channel names from stored messages
  - Selector shows only channels that actually have archived messages
- ✅ **Archive filter on channel name** — `MessageArchive.query_messages()` parameter changed from `channel: Optional[int]` to `channel_name: Optional[str]` (exact match on name string)

### Changed
- 🔄 `core/models.py`: Added `channel_name` field to `Message` dataclass and `from_dict()`
- 🔄 `core/shared_data.py`: `add_message()` resolves channel name; added `_resolve_channel_name()` helper
- 🔄 `services/message_archive.py`: `channel_name` persisted in JSON; `query_messages()` filters by name; new `get_distinct_channel_names()` method
- 🔄 `gui/archive_page.py`: Channel selector built from `archive.get_distinct_channel_names()`; filter state changed from `_channel_filter` (int) to `_channel_name_filter` (str); message cards show `channel_name` directly from archive

### Fixed
- 🛠 **Main page empty after startup** — After a restart the messages panel showed no messages until new live BLE traffic arrived. `SharedData.load_recent_from_archive()` now loads up to 100 recent archived messages during the cache-first startup phase, so historical messages are immediately visible
  - New method `SharedData.load_recent_from_archive(limit)` — reads from `MessageArchive.query_messages()` and populates the in-memory list without re-archiving
  - `BLEWorker._apply_cache()` calls `load_recent_from_archive()` at the end of cache loading

### Impact
- Archived messages now self-contained — channel name visible without live BLE connection
- Main page immediately shows historical messages after startup (no waiting for live BLE traffic)
- Backward compatible — old archive entries without `channel_name` fall back to `"Ch <idx>"`
- No breaking changes to existing functionality

---

## [1.6.0] - 2026-02-13 — Dashboard Layout Consolidation

### Changed
- 🔄 **Messages panel consolidated** — Filter checkboxes (DM + channels) and message input (text field, channel selector, Send button) are now integrated into the Messages panel, replacing the separate Filter and Input panels
  - DM + channel checkboxes displayed centered in the Messages header row, between the "💬 Messages" label and the "📚 Archive" button
  - Message input row (text field, channel selector, Send button) placed below the message list within the same card
  - `messages_panel.py`: Constructor now accepts `put_command` callable; added `update_filters(data)`, `update_channel_options(channels)` methods and `channel_filters`, `last_channels` properties (all logic 1:1 from FilterPanel/InputPanel); `update()` signature unchanged
- 🔄 **Actions panel expanded** — BOT toggle checkbox moved from Filter panel to Actions panel, below the Refresh/Advert buttons
  - `actions_panel.py`: Constructor now accepts `set_bot_enabled` callable; added `update(data)` method for BOT state sync; `_on_bot_toggle()` logic 1:1 from FilterPanel
- 🔄 **Dashboard layout simplified** — Centre column reduced from 4 panels (Map → Input → Filter → Messages) to 2 panels (Map → Messages)
  - `dashboard.py`: FilterPanel and InputPanel no longer rendered; all dependencies rerouted to MessagesPanel and ActionsPanel; `_update_ui()` call-sites updated accordingly

### Removed (from layout, files retained)
- ❌ **Filter panel** no longer rendered as separate panel — `filter_panel.py` retained in codebase but not instantiated in dashboard
- ❌ **Input panel** no longer rendered as separate panel — `input_panel.py` retained in codebase but not instantiated in dashboard

### Impact
- Cleaner, more compact dashboard: 2 fewer panels in the centre column
- All functionality preserved — message filtering, send, BOT toggle, archive all work identically
- No breaking changes to BLE, services, core or other panels

---

<!-- ADDED: v1.5.0 feature + bugfix entry -->

## [1.5.0] - 2026-02-11 — Room Server Support, Dynamic Channel Discovery & Contact Management

### Added
- ✅ **Room Server panel** — Dedicated per-room-server message panel in the centre column below Messages. Each Room Server (type=3 contact) gets its own `ui.card()` with login/logout controls and message display
  - Click a Room Server contact to open an add/login dialog with password field
  - After login: messages are displayed in the room card; send messages directly from the room panel
  - Password row + login button automatically replaced by Logout button after successful login
  - Room Server author attribution via `signature` field (txt_type=2) — real message author is resolved from the 4-byte pubkey prefix, not the room server pubkey
  - New panel: `gui/panels/room_server_panel.py` — per-room card management with login state tracking
- ✅ **Room Server password store** — Passwords stored outside the repository in `~/.meshcore-gui/room_passwords/<ADDRESS>.json`
  - New service: `services/room_password_store.py` — JSON-backed persistent password storage per BLE device, analogous to `PinStore`
  - Room panels are restored from stored passwords on app restart
- ✅ **Dynamic channel discovery** — Channels are now auto-discovered from the device at startup via `get_channel()` BLE probing, replacing the hardcoded `CHANNELS_CONFIG`
  - Single-attempt probe per channel slot with early stop after 2 consecutive empty slots
  - Channel name and encryption key extracted in a single pass (combined discovery + key loading)
  - Configurable channel caching via `CHANNEL_CACHE_ENABLED` (default: `False` — always fresh from device)
  - `MAX_CHANNELS` setting (default: 8) controls how many slots are probed
- ✅ **Individual contact deletion** — 🗑️ delete button per unpinned contact in the contacts list, with confirmation dialog
  - New command: `remove_single_contact` in BLE command handler
  - Pinned contacts are protected (no delete button shown)
- ✅ **"Also delete from history" option** — Checkbox in the Clean up confirmation dialog to also remove locally cached contact data

<!-- ADDED: Research document reference -->
- ✅ **Room Server protocol research** — `RoomServer_Companion_App_Onderzoek.md` documents the full companion app message flow (login, push protocol, signature mechanism, auto_message_fetching)

### Changed
- 🔄 `config.py`: Removed `CHANNELS_CONFIG` constant; added `MAX_CHANNELS` (default: 8) and `CHANNEL_CACHE_ENABLED` (default: `False`)
- 🔄 `ble/worker.py`: Replaced hardcoded channel loading with `_discover_channels()` method; added `_try_get_channel_info()` helper; `_apply_cache()` respects `CHANNEL_CACHE_ENABLED` setting; removed `_load_channel_keys()` (integrated into discovery pass)
- 🔄 `ble/commands.py`: Added `login_room`, `send_room_msg` and `remove_single_contact` command handlers
- 🔄 `gui/panels/contacts_panel.py`: Contact click now dispatches by type — type=3 (Room Server) opens room dialog, others open DM dialog; added `on_add_room` callback parameter; added 🗑️ delete button per unpinned contact
- 🔄 `gui/panels/messages_panel.py`: Room Server messages filtered from general message view via `_is_room_message()` with prefix matching; `update()` accepts `room_pubkeys` parameter
- 🔄 `gui/dashboard.py`: Added `RoomServerPanel` in centre column; `_update_ui()` passes `room_pubkeys` to Messages panel; added `_on_add_room_server` callback
- 🔄 `gui/panels/filter_panel.py`: Channel filter checkboxes now built dynamically from discovered channels (no hardcoded references)
- 🔄 `services/bot.py`: Removed stale comment referencing hardcoded channels

### Fixed
- 🛠 **Room Server messages appeared as DM** — Messages from Room Servers (txt_type=2) were displayed in the general Messages panel as direct messages. They are now filtered out and shown exclusively in the Room Server panel
- 🛠 **Historical room messages not shown after login** — Post-login fetch loop was polling `get_msg()` before room server had time to push messages over LoRa RF (10–75s per message). Removed redundant fetch loop; the library's `auto_message_fetching` handles `MESSAGES_WAITING` events correctly and event-driven
- 🛠 **Author attribution incorrect for room messages** — Room server messages showed the room server name as sender instead of the actual message author. Now correctly resolved from the `signature` field (4-byte pubkey prefix) via contact lookup

### Impact
- Room Servers are now first-class citizens in the GUI with dedicated panels
- Channel configuration no longer requires manual editing of `config.py`
- Contact list management is more granular with per-contact deletion
- No breaking changes to existing functionality (messages, DM, map, archive, bot, etc.)

---

## [1.4.0] - 2026-02-09 — SDK Event Race Condition Fix

### Fixed
- 🛠 **BLE startup delay of ~2 minutes eliminated** — The meshcore Python SDK (`commands/base.py`) dispatched device response events before `wait_for_events()` registered its subscription. On busy networks with frequent `RX_LOG_DATA` events, this caused `send_device_query()` and `get_channel()` to fail repeatedly with `no_event_received`, wasting 110+ seconds in timeouts

### Changed
- 📄 `meshcore` SDK `commands/base.py`: Rewritten `send()` method to subscribe to expected events **before** transmitting the BLE command (subscribe-before-send pattern), matching the approach used by the companion apps (meshcore.js, iOS, Android). Submitted upstream as [meshcore_py PR #52](https://github.com/meshcore-dev/meshcore_py/pull/52)

### Impact
- Startup time reduced from ~2+ minutes to ~10 seconds on busy networks
- All BLE commands (`send_device_query`, `get_channel`, `get_bat`, `send_appstart`, etc.) now succeed on first attempt instead of requiring multiple retries
- No changes to meshcore_gui code required — the fix is entirely in the meshcore SDK

### Temporary Installation
Until the fix is merged upstream, install the patched meshcore SDK:
```bash
pip install --force-reinstall git+https://github.com/PE1HVH/meshcore_py.git@fix/event-race-condition
```

---

<!-- ADDED: v1.3.2 bugfix entry -->

## [1.3.2] - 2026-02-09 — Bugfix: Bot Device Name Restoration After Restart

### Fixed
- 🛠 **Bot device name not properly restored after restart/crash** — After a restart or crash with bot mode previously active, the original device name was incorrectly stored as the bot name (e.g. `NL-OV-ZWL-STDSHGN-WKC Bot`) instead of the real device name (e.g. `PE1HVH T1000e`). The original device name is now correctly preserved and restored when bot mode is disabled

### Changed
- 🔄 `commands.py`: `set_bot_name` handler now verifies that the stored original name is not already the bot name before saving
- 🔄 `shared_data.py`: `original_device_name` is only written when it differs from `BOT_DEVICE_NAME` to prevent overwriting with the bot name on restart

---

<!-- ADDED: v1.3.1 bugfix entry -->

## [1.3.1] - 2026-02-09 — Bugfix: Auto-add AttributeError

### Fixed
- 🛠 **Auto-add error on first toggle** — Setting auto-add for the first time raised `AttributeError: 'telemetry_mode_base'`. The `set_manual_add_contacts()` SDK call now handles missing `telemetry_mode_base` attribute gracefully

### Changed
- 🔄 `commands.py`: `set_auto_add` handler wraps `set_manual_add_contacts()` call with attribute check and error handling for missing `telemetry_mode_base`

---

<!-- ADDED: New v1.3.0 entry at top -->

## [1.3.0] - 2026-02-08 — Bot Device Name Management

### Added
- ✅ **Bot device name switching** — When the BOT checkbox is enabled, the device name is automatically changed to a configurable bot name; when disabled, the original name is restored
  - Original device name is saved before renaming so it can be restored on BOT disable
  - Device name written to device via BLE `set_name()` SDK call
  - Graceful handling of BLE failures during name change
- ✅ **`BOT_DEVICE_NAME` constant** in `config.py` — Configurable fixed device name used when bot mode is active (default: `;NL-OV-ZWL-STDSHGN-WKC Bot`)

### Changed
- 🔄 `config.py`: Added `BOT_DEVICE_NAME` constant for bot mode device name
- 🔄 `bot.py`: Removed hardcoded `BOT_NAME` prefix ("Zwolle Bot") from bot reply messages — bot replies no longer include a name prefix
- 🔄 `filter_panel.py`: BOT checkbox toggle now triggers device name save/rename via command queue
- 🔄 `commands.py`: Added `set_bot_name` and `restore_name` command handlers for device name switching
- 🔄 `shared_data.py`: Added `original_device_name` field for storing the pre-bot device name

### Removed
- ❌ `BOT_NAME` constant from `bot.py` — bot reply prefix removed; replies no longer prepend a bot display name

---

## [1.2.0] - 2026-02-08 — Contact Maintenance Feature

### Added
- ✅ **Pin/Unpin contacts** (Iteration A) — Toggle to pin individual contacts, protecting them from bulk deletion
  - Persistent pin state stored in `~/.meshcore-gui/cache/<ADDRESS>_pins.json`
  - Pinned contacts visually marked with yellow background
  - Pinned contacts sorted to top of contact list
  - Pin state survives app restart
  - New service: `services/pin_store.py` — JSON-backed persistent pin storage

- ✅ **Bulk delete unpinned contacts** (Iteration B) — Remove all unpinned contacts from device in one action
  - "🧹 Clean up" button in contacts panel with confirmation dialog
  - Shows count of contacts to be removed vs. pinned contacts kept
  - Progress status updates during removal
  - Automatic device resync after completion
  - New service: `services/contact_cleaner.py` — ContactCleanerService with purge statistics

- ✅ **Auto-add contacts toggle** (Iteration C) — Control whether device automatically adds new contacts from mesh adverts
  - "📥 Auto-add" checkbox in contacts panel (next to Clean up button)
  - Syncs with device via `set_manual_add_contacts()` SDK call
  - Inverted logic handled internally (UI "Auto-add ON" = `set_manual_add_contacts(false)`)
  - Optimistic update with automatic rollback on BLE failure
  - State synchronized from device on each GUI update cycle

### Changed
- 🔄 `contacts_panel.py`: Added pin checkbox per contact, purge button, auto-add toggle, DM dialog (all existing functionality preserved)
- 🔄 `commands.py`: Added `purge_unpinned` and `set_auto_add` command handlers
- 🔄 `shared_data.py`: Added `auto_add_enabled` field with thread-safe getter/setter
- 🔄 `protocols.py`: Added `set_auto_add_enabled` and `is_auto_add_enabled` to Writer and Reader protocols
- 🔄 `dashboard.py`: Passes `PinStore` and `set_auto_add_enabled` callback to ContactsPanel
- 🔄 **UI language**: All Dutch strings in `contacts_panel.py` and `commands.py` translated to English

---

### Fixed
- 🛠 **Route table names and IDs not displayed** — Route tables in both current messages (RoutePage) and archive messages (ArchivePage) now correctly show node names and public key IDs for sender, repeaters and receiver

### Changed
- 🔄 **CHANGELOG.md**: Corrected version numbering to semantic versioning, fixed inaccurate references (archive button location, filter state persistence)
- 🔄 **README.md**: Added Message Archive feature, updated project structure, configuration table and architecture diagram
- 🔄 **MeshCore_GUI_Design.docx**: Added ArchivePage, MessageArchive, Models components; updated project structure, protocols, configuration and version history

---

## [1.1.0] - 2026-02-07 — Archive Viewer Feature


### Added
- ✅ **Archive Viewer Page** (`/archive`) — Full-featured message archive browser
  - Pagination (50 messages per page, configurable)
  - Channel filter dropdown (All + configured channels)
  - Time range filter (24h, 7d, 30d, 90d, All time)
  - Text search (case-insensitive)
  - Filter state stored in instance variables (reset on page reload)
  - Message cards with same styling as main messages panel
  - Clickable messages for route visualization (where available)
  - **💬 Reply functionality** — Expandable reply panel per message
  - **🗺️ Inline route table** — Expandable route display per archive message with sender, repeaters and receiver (names, IDs, node types)
  - *(Note: Reply panels and inline route tables removed in v1.8.0, replaced by click-to-route navigation via message hash)*

<!-- CHANGED: "Filter state persistence (app.storage.user)" replaced with "Filter state stored in 
     instance variables" — the code (archive_page.py:36-40) uses self._current_page etc., 
     not app.storage.user. The comment in the code is misleading. -->

<!-- ADDED: "Inline route table" entry — _render_archive_route() in archive_page.py:333-407 
     was not documented. -->
  
- ✅ **MessageArchive.query_messages()** method
  - Filter by: time range, channel, text search, sender
  - Pagination support (limit, offset)
  - Returns tuple: (messages, total_count)
  - Sorting: Newest first
  
- ✅ **UI Integration**
  - "📚 Archive" button in Messages panel header (opens in new tab)
  - Back to Dashboard button in archive page

<!-- CHANGED: "📚 View Archive button in Actions panel" corrected — the button is in 
     MessagesPanel (messages_panel.py:25), not in ActionsPanel (actions_panel.py). 
     ActionsPanel only contains Refresh and Advert buttons. -->

- ✅ **Reply Panel**
  - Expandable reply per message (💬 Reply button)
  - Pre-filled with @sender mention
  - Channel selector
  - Send button with success notification
  - Auto-close expansion after send

### Changed
- 🔄 `SharedData.get_snapshot()`: Now includes `'archive'` field
- 🔄 `MessagesPanel`: Added archive button in header row
- 🔄 Both entry points (`__main__.py` and `meshcore_gui.py`): Register `/archive` route

<!-- CHANGED: "ActionsPanel: Added archive button" corrected to "MessagesPanel" -->

### Performance
- Query: ~10ms for 10k messages with filters
- Memory: ~10KB per page (50 messages)
- No impact on main UI (separate page)

### Known Limitations
- ~~Route visualization only works for messages in recent buffer (last 100)~~ — Fixed in v1.8.0: archive messages now support click-to-route via `get_message_by_hash()` fallback
- Text search is linear scan (no indexing yet)
- Sender filter exists in API but not in UI yet

---

## [1.0.3] - 2026-02-07 — Critical Bugfix: Archive Overwrite Prevention


### Fixed
- 🛠 **CRITICAL**: Fixed bug where archive was overwritten instead of appended on restart
- 🛠 Archive now preserves existing data when read errors occur
- 🛠 Buffer is retained for retry if existing archive cannot be read

### Changed
- 🔄 `_flush_messages()`: Early return on read error instead of overwriting
- 🔄 `_flush_rxlog()`: Early return on read error instead of overwriting
- 🔄 Better error messages for version mismatch and JSON decode errors

### Details
**Problem:** If the existing archive file had a JSON parse error or version mismatch, 
the flush operation would proceed with `existing_messages = []`, effectively 
overwriting all historical data with only the new buffered messages.

**Solution:** The flush methods now:
1. Try to read existing archive first
2. If read fails (JSON error, version mismatch, IO error), abort the flush
3. Keep buffer intact for next retry
4. Only clear buffer after successful write

**Impact:** No data loss on restart or when archive files have issues.

### Testing
- ✅ Added `test_append_on_restart_not_overwrite()` integration test
- ✅ Verifies data is appended across multiple sessions
- ✅ All existing tests still pass

---

## [1.0.2] - 2026-02-07 — RxLog message_hash Enhancement


### Added
- ✅ `message_hash` field added to `RxLogEntry` model
- ✅ RxLog entries now include message_hash for correlation with messages
- ✅ Archive JSON includes message_hash in rxlog entries

### Changed
- 🔄 `events.py`: Restructured `on_rx_log()` to extract message_hash before creating RxLogEntry
- 🔄 `message_archive.py`: Updated rxlog archiving to include message_hash field
- 🔄 Tests updated to verify message_hash persistence

### Benefits
- **Correlation**: Link RX log entries to their corresponding messages
- **Analysis**: Track which packets resulted in messages
- **Debugging**: Better troubleshooting of packet processing

---

## [1.0.1] - 2026-02-07 — Entry Point Fix


### Fixed
- ✅ `meshcore_gui.py` (root entry point) now passes ble_address to SharedData
- ✅ Archive works correctly regardless of how application is started

### Changed
- 🔄 Both entry points (`meshcore_gui.py` and `meshcore_gui/__main__.py`) updated

---

## [1.0.0] - 2026-02-07 — Message & Metadata Persistence


### Added
- ✅ MessageArchive class for persistent storage
- ✅ Configurable retention periods (MESSAGE_RETENTION_DAYS, RXLOG_RETENTION_DAYS, CONTACT_RETENTION_DAYS)
- ✅ Automatic daily cleanup of old data
- ✅ Batch writes for performance
- ✅ Thread-safe with separate locks
- ✅ Atomic file writes
- ✅ Contact retention in DeviceCache
- ✅ Archive statistics API
- ✅ Comprehensive tests (20+ unit, 8+ integration)
- ✅ Full documentation

### Storage Locations
- `~/.meshcore-gui/archive/<ADDRESS>_messages.json`
- `~/.meshcore-gui/archive/<ADDRESS>_rxlog.json`

### Requirements Completed
- R1: All incoming messages persistent ✅
- R2: All incoming RxLog entries persistent ✅
- R3: Configurable retention ✅
- R4: Automatic cleanup ✅
- R5: Backward compatibility ✅
- R6: Contact retention ✅
- R7: Archive stats API ✅
