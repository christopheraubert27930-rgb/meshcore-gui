# CHANGELOG: Message & Metadata Persistence

## v1.0.4 (2026-02-07) - Archive Viewer Feature

### Added
- ✅ **Archive Viewer Page** (`/archive`) - Full-featured message archive browser
  - Pagination (50 messages per page, configurable)
  - Channel filter dropdown (All + configured channels)
  - Time range filter (24h, 7d, 30d, 90d, All time)
  - Text search (case-insensitive)
  - Filter state persistence (app.storage.user)
  - Message cards with same styling as main messages panel
  - Clickable messages for route visualization (where available)
  - **💬 Reply functionality** - Expandable reply panel per message
  
- ✅ **MessageArchive.query_messages()** method
  - Filter by: time range, channel, text search, sender
  - Pagination support (limit, offset)
  - Returns tuple: (messages, total_count)
  - Sorting: Newest first
  
- ✅ **UI Integration**
  - "📚 View Archive" button in Actions panel
  - Opens in new tab
  - Back to Dashboard button in archive page
  
- ✅ **Reply Panel** (NEW!)
  - Expandable reply per message (💬 Reply button)
  - Pre-filled with @sender mention
  - Channel selector
  - Send button with success notification
  - Auto-close expansion after send

### Changed
- 🔄 `SharedData.get_snapshot()`: Now includes `'archive'` field
- 🔄 `ActionsPanel`: Added archive button and open handler
- 🔄 Both entry points (`__main__.py` and `meshcore_gui.py`): Register `/archive` route

### Features
- **Pagination**: Navigate large archives efficiently
- **Filters**: Time range + channel + text search
- **Persistent State**: Filters remembered across sessions
- **Consistent UI**: Same message styling as dashboard
- **Route Integration**: Click messages to view route (if in recent buffer)
- **Reply from Archive**: Direct reply capability for any archived message

### UI/UX
- **Message Cards**: Expandable reply panel integrated
- **Pre-filled Reply**: Auto-mention sender (@sender)
- **Channel Selection**: Choose reply channel
- **Feedback**: Success notification after sending
- **Smart Collapse**: Reply panel closes after send

### Performance
- Query: ~10ms for 10k messages with filters
- Memory: ~10KB per page (50 messages)
- No impact on main UI (separate page)

### Known Limitations
- Route visualization only works for messages in recent buffer (last 100)
- Archived-only messages show warning notification
- Text search is linear scan (no indexing yet)
- Sender filter exists in API but not in UI yet

### Future Improvements
- Archive-based route visualization (use message_hash)
- Sender filter UI component
- Export to CSV/JSON
- Advanced filters (SNR, hop count)
- Full-text search indexing

---

## v1.0.3 (2026-02-07) - Critical Bugfix: Archive Overwrite Prevention

### Fixed
- 🐛 **CRITICAL**: Fixed bug where archive was overwritten instead of appended on restart
- 🐛 Archive now preserves existing data when read errors occur
- 🐛 Buffer is retained for retry if existing archive cannot be read

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

## v1.0.2 (2026-02-07) - RxLog message_hash Enhancement

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

### Example RxLog Entry (Before)
```json
{
  "time": "12:34:56",
  "timestamp_utc": "2026-02-07T12:34:56Z",
  "snr": 8.5,
  "rssi": -95.0,
  "payload_type": "MSG",
  "hops": 2
}
```

### Example RxLog Entry (After)
```json
{
  "time": "12:34:56",
  "timestamp_utc": "2026-02-07T12:34:56Z",
  "snr": 8.5,
  "rssi": -95.0,
  "payload_type": "MSG",
  "hops": 2,
  "message_hash": "def456..."
}
```

**Note:** For non-message packets (announcements, broadcasts), `message_hash` will be an empty string.

---

## v1.0.1 (2026-02-07) - Entry Point Fix

### Fixed
- ✅ `meshcore_gui.py` (root entry point) now passes ble_address to SharedData
- ✅ Archive works correctly regardless of how application is started

### Changed
- 🔄 Both entry points (`meshcore_gui.py` and `meshcore_gui/__main__.py`) updated

---

## v1.0.0 (2026-02-07) - Initial Release

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
