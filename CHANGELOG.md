# CHANGELOG

<!-- CHANGED: Title changed from "CHANGELOG: Message & Metadata Persistence" to "CHANGELOG" — 
     a root-level CHANGELOG.md should be project-wide, not feature-specific. -->

All notable changes to MeshCore GUI are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/).

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
- Route visualization only works for messages in recent buffer (last 100)
- Archived-only messages show warning notification
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
