"""
Thread-safe shared data container for MeshCore GUI.

SharedData is the central data store shared between the BLE worker thread
and the GUI main thread.  All access goes through methods that acquire a
threading.Lock so both threads can safely read and write.

v4.1 changes
~~~~~~~~~~~~~
- ``messages`` is now ``List[Message]`` (was ``List[Dict]``).
- ``rx_log`` is now ``List[RxLogEntry]`` (was ``List[Dict]``).
- ``DeviceInfo`` dataclass replaces loose scalar fields.
- ``get_snapshot()`` returns typed objects; UI code accesses attributes
  directly (``msg.sender``) instead of dict keys (``msg['sender']``).
"""

import queue
import threading
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from meshcore_gui.config import debug_print
from meshcore_gui.core.models import DeviceInfo, Message, RxLogEntry
from meshcore_gui.services.message_archive import MessageArchive


class SharedData:
    """
    Thread-safe container for shared data between BLE worker and GUI.

    Implements all four Protocol interfaces defined in ``protocols.py``.
    """

    def __init__(self, ble_address: Optional[str] = None) -> None:
        self.lock = threading.Lock()

        # Device info (typed)
        self.device = DeviceInfo()

        # Connection status
        self.connected: bool = False
        self.status: str = "Starting..."

        # Data collections (typed)
        self.contacts: Dict = {}
        self.channels: List[Dict] = []
        self.messages: List[Message] = []
        self.rx_log: List[RxLogEntry] = []

        # Command queue (GUI → BLE)
        self.cmd_queue: queue.Queue = queue.Queue()

        # Update flags — initially True so first GUI render shows data
        self.device_updated: bool = True
        self.contacts_updated: bool = True
        self.channels_updated: bool = True
        self.rxlog_updated: bool = True

        # Flag to track if GUI has done first render
        self.gui_initialized: bool = False

        # BOT enabled flag (toggled from GUI)
        self.bot_enabled: bool = False

        # Auto-add contacts flag (synced with device)
        self.auto_add_enabled: bool = False

        # Message archive (persistent storage)
        self.archive: Optional[MessageArchive] = None
        if ble_address:
            self.archive = MessageArchive(ble_address)
            debug_print(f"MessageArchive initialized for {ble_address}")

    # ------------------------------------------------------------------
    # Device info updates
    # ------------------------------------------------------------------

    def update_from_appstart(self, payload: Dict) -> None:
        """Update device info from send_appstart response."""
        with self.lock:
            d = self.device
            d.name = payload.get('name', d.name)
            d.public_key = payload.get('public_key', d.public_key)
            d.radio_freq = payload.get('radio_freq', d.radio_freq)
            d.radio_sf = payload.get('radio_sf', d.radio_sf)
            d.radio_bw = payload.get('radio_bw', d.radio_bw)
            d.tx_power = payload.get('tx_power', d.tx_power)
            d.adv_lat = payload.get('adv_lat', d.adv_lat)
            d.adv_lon = payload.get('adv_lon', d.adv_lon)
            self.device_updated = True
            debug_print(f"Device info updated: {d.name}")

    def update_from_device_query(self, payload: Dict) -> None:
        """Update firmware version from send_device_query response."""
        with self.lock:
            self.device.firmware_version = payload.get(
                'ver', self.device.firmware_version,
            )
            self.device_updated = True
            debug_print(f"Firmware version: {self.device.firmware_version}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def set_status(self, status: str) -> None:
        with self.lock:
            self.status = status

    def set_connected(self, connected: bool) -> None:
        with self.lock:
            self.connected = connected

    # ------------------------------------------------------------------
    # BOT
    # ------------------------------------------------------------------

    def set_bot_enabled(self, enabled: bool) -> None:
        with self.lock:
            self.bot_enabled = enabled
            debug_print(f"BOT {'enabled' if enabled else 'disabled'}")

    def is_bot_enabled(self) -> bool:
        with self.lock:
            return self.bot_enabled

    # ------------------------------------------------------------------
    # Auto-add contacts
    # ------------------------------------------------------------------

    def set_auto_add_enabled(self, enabled: bool) -> None:
        """Set auto-add contacts flag (thread-safe)."""
        with self.lock:
            self.auto_add_enabled = enabled
            debug_print(f"Auto-add {'enabled' if enabled else 'disabled'}")

    def is_auto_add_enabled(self) -> bool:
        """Get auto-add contacts flag (thread-safe)."""
        with self.lock:
            return self.auto_add_enabled

    # ------------------------------------------------------------------
    # Command queue
    # ------------------------------------------------------------------

    def put_command(self, cmd: Dict) -> None:
        self.cmd_queue.put(cmd)

    def get_next_command(self) -> Optional[Dict]:
        try:
            return self.cmd_queue.get_nowait()
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    def set_contacts(self, contacts_dict: Dict) -> None:
        with self.lock:
            self.contacts = contacts_dict.copy()
            self.contacts_updated = True
            debug_print(f"Contacts updated: {len(self.contacts)} contacts")

    def set_channels(self, channels: List[Dict]) -> None:
        with self.lock:
            self.channels = channels.copy()
            self.channels_updated = True
            debug_print(f"Channels updated: {[c['name'] for c in channels]}")

    def add_message(self, msg: Message) -> None:
        """Add a Message to the store (max 100)."""
        with self.lock:
            self.messages.append(msg)
            if len(self.messages) > 100:
                self.messages.pop(0)
            debug_print(
                f"Message added: {msg.sender}: {msg.text[:30]}"
            )
            
            # Archive message for persistent storage
            if self.archive:
                self.archive.add_message(msg)

    def add_rx_log(self, entry: RxLogEntry) -> None:
        """Add an RxLogEntry (max 50, newest first)."""
        with self.lock:
            self.rx_log.insert(0, entry)
            if len(self.rx_log) > 50:
                self.rx_log.pop()
            self.rxlog_updated = True
            
            # Archive entry for persistent storage
            if self.archive:
                self.archive.add_rx_log(entry)

    # ------------------------------------------------------------------
    # Snapshot and flags
    # ------------------------------------------------------------------

    def get_snapshot(self) -> Dict:
        """Create a complete snapshot of all data for the GUI.

        Returns a plain dict with typed objects inside.  The
        ``messages`` and ``rx_log`` values are lists of dataclass
        instances (not dicts).
        """
        with self.lock:
            d = self.device
            return {
                # DeviceInfo fields (flat for backward compat)
                'name': d.name,
                'public_key': d.public_key,
                'radio_freq': d.radio_freq,
                'radio_sf': d.radio_sf,
                'radio_bw': d.radio_bw,
                'tx_power': d.tx_power,
                'adv_lat': d.adv_lat,
                'adv_lon': d.adv_lon,
                'firmware_version': d.firmware_version,
                # Status
                'connected': self.connected,
                'status': self.status,
                # Collections (typed copies)
                'contacts': self.contacts.copy(),
                'channels': self.channels.copy(),
                'messages': self.messages.copy(),
                'rx_log': self.rx_log.copy(),
                # Flags
                'device_updated': self.device_updated,
                'contacts_updated': self.contacts_updated,
                'channels_updated': self.channels_updated,
                'rxlog_updated': self.rxlog_updated,
                'gui_initialized': self.gui_initialized,
                'bot_enabled': self.bot_enabled,
                'auto_add_enabled': self.auto_add_enabled,
                # Archive (for archive viewer)
                'archive': self.archive,
            }

    def clear_update_flags(self) -> None:
        with self.lock:
            self.device_updated = False
            self.contacts_updated = False
            self.channels_updated = False
            self.rxlog_updated = False

    def mark_gui_initialized(self) -> None:
        with self.lock:
            self.gui_initialized = True
            debug_print("GUI marked as initialized")

    # ------------------------------------------------------------------
    # Contact lookups
    # ------------------------------------------------------------------

    def get_contact_by_prefix(self, pubkey_prefix: str) -> Optional[Dict]:
        if not pubkey_prefix:
            return None
        with self.lock:
            for key, contact in self.contacts.items():
                if key.startswith(pubkey_prefix) or pubkey_prefix.startswith(key):
                    return contact.copy()
        return None

    def get_contact_name_by_prefix(self, pubkey_prefix: str) -> str:
        if not pubkey_prefix:
            return ""
        with self.lock:
            for key, contact in self.contacts.items():
                if key.startswith(pubkey_prefix):
                    name = contact.get('adv_name', '')
                    if name:
                        return name
        return pubkey_prefix[:8]

    def get_contact_by_name(self, name: str) -> Optional[Tuple[str, Dict]]:
        if not name:
            return None
        with self.lock:
            # Strategy 1: exact match
            for key, contact in self.contacts.items():
                if contact.get('adv_name', '') == name:
                    return (key, contact.copy())
            # Strategy 2: case-insensitive
            name_lower = name.lower()
            for key, contact in self.contacts.items():
                if contact.get('adv_name', '').lower() == name_lower:
                    return (key, contact.copy())
            # Strategy 3: prefix match
            for key, contact in self.contacts.items():
                adv = contact.get('adv_name', '')
                if not adv:
                    continue
                if name.startswith(adv) or adv.startswith(name):
                    return (key, contact.copy())
        return None

    # ------------------------------------------------------------------
    # Archive stats
    # ------------------------------------------------------------------

    def get_archive_stats(self) -> Optional[Dict]:
        """Get statistics from the message archive.
        
        Returns:
            Dict with archive stats, or None if archive not initialized.
        """
        if self.archive:
            return self.archive.get_stats()
        return None
