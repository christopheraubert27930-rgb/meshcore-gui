#!/usr/bin/env python3
"""

MeshCore GUI - Threaded BLE Edition
====================================

A graphical user interface for MeshCore mesh network devices.
Communicates via Bluetooth Low Energy (BLE) with a MeshCore companion device.

Architecture:
    - BLE communication runs in a separate thread with its own asyncio event loop
    - NiceGUI web interface runs in the main thread
    - Thread-safe SharedData class for communication between threads
    - Command queue for GUI -> BLE communication

Requirements:
    pip install meshcore nicegui bleak

Usage:
    python meshcore_gui_v2.py <BLE_ADDRESS>
    python meshcore_gui_v2.py literal:AA:BB:CC:DD:EE:FF

                   Author: PE1HVH
                  Version: 2.0
  SPDX-License-Identifier: MIT
                Copyright: (c) 2026 PE1HVH
"""

import asyncio
import sys
import threading
import queue
from datetime import datetime
from typing import Optional, Dict, List

from nicegui import ui, app

try:
    from meshcore import MeshCore, EventType
except ImportError:
    print("ERROR: meshcore library not found")
    print("Install with: pip install meshcore")
    sys.exit(1)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Debug mode: set to True for verbose logging
DEBUG = False

# Hardcoded channels configuration
# Determine your channels with meshcli:
#   meshcli -d <BLE_ADDRESS>
#   > get_channels
# Output: 0: Public [...], 1: #test [...], etc.
CHANNELS_CONFIG = [
    {'idx': 0, 'name': 'Public'},
    {'idx': 1, 'name': '#test'},
    {'idx': 2, 'name': '#zwolle'},
    {'idx': 3, 'name': 'RahanSom'},
]


def debug_print(msg: str) -> None:
    """
    Print debug message if DEBUG mode is enabled.
    
    Args:
        msg: The message to print
    """
    if DEBUG:
        print(f"DEBUG: {msg}")


# ==============================================================================
# SHARED DATA - Thread-safe data container
# ==============================================================================

class SharedData:
    """
    Thread-safe container for shared data between BLE worker and GUI.
    
    All access to data goes through methods that use a threading.Lock
    to prevent race conditions.
    
    Attributes:
        lock: Threading lock for thread-safe access
        name: Device name
        public_key: Device public key
        radio_freq: Radio frequency in MHz
        radio_sf: Spreading factor
        radio_bw: Bandwidth in kHz
        tx_power: Transmit power in dBm
        adv_lat: Advertised latitude
        adv_lon: Advertised longitude
        firmware_version: Firmware version string
        connected: Boolean whether device is connected
        status: Status text for UI
        contacts: Dict of contacts {key: {adv_name, type, lat, lon, ...}}
        channels: List of channels [{idx, name}, ...]
        messages: List of messages
        rx_log: List of RX log entries
    """
    
    def __init__(self):
        """Initialize SharedData with empty values and flags set to True."""
        self.lock = threading.Lock()
        
        # Device info
        self.name: str = ""
        self.public_key: str = ""
        self.radio_freq: float = 0.0
        self.radio_sf: int = 0
        self.radio_bw: float = 0.0
        self.tx_power: int = 0
        self.adv_lat: float = 0.0
        self.adv_lon: float = 0.0
        self.firmware_version: str = ""
        
        # Connection status
        self.connected: bool = False
        self.status: str = "Starting..."
        
        # Data collections
        self.contacts: Dict = {}
        self.channels: List[Dict] = []
        self.messages: List[Dict] = []
        self.rx_log: List[Dict] = []
        
        # Command queue (GUI -> BLE)
        self.cmd_queue: queue.Queue = queue.Queue()
        
        # Update flags - INITIALLY TRUE so first GUI render shows data
        self.device_updated: bool = True
        self.contacts_updated: bool = True
        self.channels_updated: bool = True
        self.rxlog_updated: bool = True
        
        # Flag to track if GUI has done first render
        self.gui_initialized: bool = False
    
    def update_from_appstart(self, payload: Dict) -> None:
        """
        Update device info from send_appstart response.
        
        Args:
            payload: Response payload from send_appstart command
        """
        with self.lock:
            self.name = payload.get('name', self.name)
            self.public_key = payload.get('public_key', self.public_key)
            self.radio_freq = payload.get('radio_freq', self.radio_freq)
            self.radio_sf = payload.get('radio_sf', self.radio_sf)
            self.radio_bw = payload.get('radio_bw', self.radio_bw)
            self.tx_power = payload.get('tx_power', self.tx_power)
            self.adv_lat = payload.get('adv_lat', self.adv_lat)
            self.adv_lon = payload.get('adv_lon', self.adv_lon)
            self.device_updated = True
            debug_print(f"Device info updated: {self.name}")
    
    def update_from_device_query(self, payload: Dict) -> None:
        """
        Update firmware version from send_device_query response.
        
        Args:
            payload: Response payload from send_device_query command
        """
        with self.lock:
            self.firmware_version = payload.get('ver', self.firmware_version)
            self.device_updated = True
            debug_print(f"Firmware version: {self.firmware_version}")
    
    def set_status(self, status: str) -> None:
        """
        Update status text.
        
        Args:
            status: New status text
        """
        with self.lock:
            self.status = status
    
    def set_contacts(self, contacts_dict: Dict) -> None:
        """
        Update contacts dictionary.
        
        Args:
            contacts_dict: Dictionary with contacts {key: contact_data}
        """
        with self.lock:
            self.contacts = contacts_dict.copy()
            self.contacts_updated = True
            debug_print(f"Contacts updated: {len(self.contacts)} contacts")
    
    def set_channels(self, channels: List[Dict]) -> None:
        """
        Update channels list.
        
        Args:
            channels: List of channel dictionaries [{idx, name}, ...]
        """
        with self.lock:
            self.channels = channels.copy()
            self.channels_updated = True
            debug_print(f"Channels updated: {[c['name'] for c in channels]}")
    
    def add_message(self, msg: Dict) -> None:
        """
        Add a message to the messages list.
        
        Args:
            msg: Message dictionary with time, sender, text, channel, direction
        """
        with self.lock:
            self.messages.append(msg)
            # Limit to last 100 messages
            if len(self.messages) > 100:
                self.messages.pop(0)
            debug_print(f"Message added: {msg.get('sender', '?')}: {msg.get('text', '')[:30]}")
    
    def add_rx_log(self, entry: Dict) -> None:
        """
        Add an RX log entry.
        
        Args:
            entry: RX log entry with time, snr, rssi, payload_type
        """
        with self.lock:
            self.rx_log.insert(0, entry)
            # Limit to last 50 entries
            if len(self.rx_log) > 50:
                self.rx_log.pop()
            self.rxlog_updated = True
    
    def get_snapshot(self) -> Dict:
        """
        Create a snapshot of all data for the GUI.
        
        Returns:
            Dictionary with copies of all data and update flags
        """
        with self.lock:
            return {
                'name': self.name,
                'public_key': self.public_key,
                'radio_freq': self.radio_freq,
                'radio_sf': self.radio_sf,
                'radio_bw': self.radio_bw,
                'tx_power': self.tx_power,
                'adv_lat': self.adv_lat,
                'adv_lon': self.adv_lon,
                'firmware_version': self.firmware_version,
                'connected': self.connected,
                'status': self.status,
                'contacts': self.contacts.copy(),
                'channels': self.channels.copy(),
                'messages': self.messages.copy(),
                'rx_log': self.rx_log.copy(),
                'device_updated': self.device_updated,
                'contacts_updated': self.contacts_updated,
                'channels_updated': self.channels_updated,
                'rxlog_updated': self.rxlog_updated,
                'gui_initialized': self.gui_initialized,
            }
    
    def clear_update_flags(self) -> None:
        """Reset all update flags to False."""
        with self.lock:
            self.device_updated = False
            self.contacts_updated = False
            self.channels_updated = False
            self.rxlog_updated = False
    
    def mark_gui_initialized(self) -> None:
        """Mark that the GUI has completed its first render."""
        with self.lock:
            self.gui_initialized = True
            debug_print("GUI marked as initialized")


# ==============================================================================
# BLE WORKER - Runs in separate thread
# ==============================================================================

class BLEWorker:
    """
    BLE communication worker that runs in a separate thread.
    
    This class handles all Bluetooth Low Energy communication with the
    MeshCore device. It runs in a separate thread with its own asyncio
    event loop to avoid conflicts with NiceGUI's event loop.
    
    Attributes:
        address: BLE MAC address of the device
        shared: SharedData instance for thread-safe communication
        mc: MeshCore instance after connection
        running: Boolean to control the worker loop
    """
    
    def __init__(self, address: str, shared: SharedData):
        """
        Initialize the BLE worker.
        
        Args:
            address: BLE MAC address (e.g. "literal:AA:BB:CC:DD:EE:FF")
            shared: SharedData instance for data exchange
        """
        self.address = address
        self.shared = shared
        self.mc: Optional[MeshCore] = None
        self.running = True
    
    def start(self) -> None:
        """Start the worker in a new daemon thread."""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        debug_print("BLE worker thread started")
    
    def _run(self) -> None:
        """Entry point for the worker thread. Starts asyncio event loop."""
        asyncio.run(self._async_main())
    
    async def _async_main(self) -> None:
        """
        Main async loop of the worker.
        
        Connects to the device and then continuously processes commands
        from the GUI via the command queue.
        """
        await self._connect()
        
        if self.mc:
            # Process commands from GUI in infinite loop
            while self.running:
                await self._process_commands()
                await asyncio.sleep(0.1)
    
    async def _connect(self) -> None:
        """
        Connect to the BLE device and load initial data.
        
        Also subscribes to events for incoming messages and RX log.
        """
        self.shared.set_status(f"🔄 Connecting to {self.address}...")
        
        try:
            print(f"BLE: Connecting to {self.address}...")
            self.mc = await MeshCore.create_ble(self.address)
            print("BLE: Connected!")
            
            # Wait for device to be ready
            await asyncio.sleep(1)
            
            # Subscribe to events
            self.mc.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_msg)
            self.mc.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_msg)
            self.mc.subscribe(EventType.RX_LOG_DATA, self._on_rx_log)
            
            # Load initial data
            await self._load_data()
            
            # Start automatic message fetching
            await self.mc.start_auto_message_fetching()
            
            self.shared.connected = True
            self.shared.set_status("✅ Connected")
            print("BLE: Ready!")
            
        except Exception as e:
            print(f"BLE: Connection error: {e}")
            self.shared.set_status(f"❌ {e}")
    
    async def _load_data(self) -> None:
        """
        Load device data with retry mechanism.
        
        Tries send_appstart and send_device_query each up to 5 times
        with 0.3 second pause between attempts. Channels are loaded from
        the hardcoded configuration.
        """
        # send_appstart with retries
        self.shared.set_status("🔄 Device info...")
        for i in range(5):
            debug_print(f"send_appstart attempt {i+1}")
            r = await self.mc.commands.send_appstart()
            if r.type != EventType.ERROR:
                print(f"BLE: send_appstart OK: {r.payload.get('name')}")
                self.shared.update_from_appstart(r.payload)
                break
            await asyncio.sleep(0.3)
        
        # send_device_query with retries
        for i in range(5):
            debug_print(f"send_device_query attempt {i+1}")
            r = await self.mc.commands.send_device_query()
            if r.type != EventType.ERROR:
                print(f"BLE: send_device_query OK: {r.payload.get('ver')}")
                self.shared.update_from_device_query(r.payload)
                break
            await asyncio.sleep(0.3)
        
        # Channels from hardcoded config (BLE get_channel is unreliable)
        self.shared.set_status("🔄 Channels...")
        self.shared.set_channels(CHANNELS_CONFIG)
        print(f"BLE: Channels loaded: {[c['name'] for c in CHANNELS_CONFIG]}")
        
        # Fetch contacts
        self.shared.set_status("🔄 Contacts...")
        r = await self.mc.commands.get_contacts()
        if r.type != EventType.ERROR:
            self.shared.set_contacts(r.payload)
            print(f"BLE: Contacts loaded: {len(r.payload)} contacts")
    
    async def _process_commands(self) -> None:
        """Process all commands in the queue from the GUI."""
        try:
            while not self.shared.cmd_queue.empty():
                cmd = self.shared.cmd_queue.get_nowait()
                await self._handle_command(cmd)
        except queue.Empty:
            pass
    
    async def _handle_command(self, cmd: Dict) -> None:
        """
        Process a single command from the GUI.
        
        Args:
            cmd: Command dictionary with 'action' and optional parameters
        
        Supported actions:
            - send_message: Send channel message
            - send_advert: Send advertisement
            - refresh: Reload all data
        """
        action = cmd.get('action')
        
        if action == 'send_message':
            channel = cmd.get('channel', 0)
            text = cmd.get('text', '')
            if text and self.mc:
                await self.mc.commands.send_chan_msg(channel, text)
                self.shared.add_message({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'sender': 'Me',
                    'text': text,
                    'channel': channel,
                    'direction': 'out'
                })
                debug_print(f"Sent message to channel {channel}: {text[:30]}")
        
        elif action == 'send_advert':
            if self.mc:
                await self.mc.commands.send_advert(flood=True)
                self.shared.set_status("📢 Advert sent")
                debug_print("Advert sent")
        
        elif action == 'send_dm':
            pubkey = cmd.get('pubkey', '')
            text = cmd.get('text', '')
            contact_name = cmd.get('contact_name', pubkey[:8])
            if text and pubkey and self.mc:
                await self.mc.commands.send_msg(pubkey, text)
                self.shared.add_message({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'sender': 'Me',
                    'text': text,
                    'channel': None,  # None = DM
                    'direction': 'out'
                })
                debug_print(f"Sent DM to {contact_name}: {text[:30]}")
        
        elif action == 'refresh':
            if self.mc:
                debug_print("Refresh requested")
                await self._load_data()
    
    def _on_channel_msg(self, event) -> None:
        """
        Callback for received channel messages.
        
        Args:
            event: MeshCore event with payload
        """
        payload = event.payload
        sender = payload.get('sender_name') or payload.get('sender') or ''
        
        self.shared.add_message({
            'time': datetime.now().strftime('%H:%M:%S'),
            'sender': sender[:15] if sender else '',
            'text': payload.get('text', ''),
            'channel': payload.get('channel_idx'),
            'direction': 'in',
            'snr': payload.get('snr')
        })
    
    def _on_contact_msg(self, event) -> None:
        """
        Callback for received DM (direct message) messages.
        
        Looks up the sender name in the contacts list via pubkey_prefix.
        
        Args:
            event: MeshCore event with payload
        """
        payload = event.payload
        pubkey = payload.get('pubkey_prefix', '')
        sender = ''
        
        # Look up contact name based on pubkey prefix
        if pubkey:
            with self.shared.lock:
                for key, contact in self.shared.contacts.items():
                    if key.startswith(pubkey):
                        sender = contact.get('adv_name', '')
                        break
        
        # Fallback to pubkey prefix
        if not sender:
            sender = pubkey[:8] if pubkey else ''
        
        self.shared.add_message({
            'time': datetime.now().strftime('%H:%M:%S'),
            'sender': sender[:15] if sender else '',
            'text': payload.get('text', ''),
            'channel': None,  # None = DM
            'direction': 'in',
            'snr': payload.get('SNR')  # Note: uppercase in DM payload
        })
        
        debug_print(f"DM received from {sender}: {payload.get('text', '')[:30]}")
    
    def _on_rx_log(self, event) -> None:
        """
        Callback for RX log data.
        
        Args:
            event: MeshCore event with payload
        """
        payload = event.payload
        self.shared.add_rx_log({
            'time': datetime.now().strftime('%H:%M:%S'),
            'snr': payload.get('snr', 0),
            'rssi': payload.get('rssi', 0),
            'payload_type': payload.get('payload_type', '?'),
            'hops': payload.get('path_len', 0)
        })


# ==============================================================================
# GUI - NiceGUI Web Interface
# ==============================================================================

class MeshCoreGUI:
    """
    NiceGUI web interface for MeshCore.
    
    Provides a real-time dashboard with:
        - Device information
        - Contacts list
        - Interactive map with markers
        - Send/receive messages with filtering
        - RX log
    
    Attributes:
        shared: SharedData instance for data access
        TYPE_ICONS: Mapping of contact type to emoji
        TYPE_NAMES: Mapping of contact type to name
    """
    
    # Contact type mappings
    TYPE_ICONS = {0: "○", 1: "📱", 2: "📡", 3: "🏠"}
    TYPE_NAMES = {0: "-", 1: "CLI", 2: "REP", 3: "ROOM"}
    
    def __init__(self, shared: SharedData):
        """
        Initialize the GUI.
        
        Args:
            shared: SharedData instance for data access
        """
        self.shared = shared
        
        # UI element references
        self.status_label = None
        self.device_label = None
        self.channel_select = None
        self.channels_filter_container = None
        self.channel_filters: Dict = {}
        self.contacts_container = None
        self.map_widget = None
        self.messages_container = None
        self.rxlog_table = None
        self.msg_input = None
        
        # Map markers tracking
        self.markers: List = []
        
        # Channel data for message display
        self.last_channels: List[Dict] = []
    
    def render(self) -> None:
        """
        Render the complete UI.
        
        Builds the layout with header, three columns, and starts the
        update timer for real-time data refresh.
        """
        ui.dark_mode(False)
        
        # Header
        with ui.header().classes('bg-blue-600 text-white'):
            ui.label('🔗 MeshCore').classes('text-xl font-bold')
            ui.space()
            self.status_label = ui.label('Starting...').classes('text-sm')
        
        # Main layout: three columns
        with ui.row().classes('w-full h-full gap-2 p-2'):
            # Left column: Device info and Contacts
            with ui.column().classes('w-64 gap-2'):
                self._render_device_panel()
                self._render_contacts_panel()
            
            # Middle column: Map, Input, Filter, Messages
            with ui.column().classes('flex-grow gap-2'):
                self._render_map_panel()
                self._render_input_panel()
                self._render_channels_filter()
                self._render_messages_panel()
            
            # Right column: Actions and RX Log
            with ui.column().classes('w-64 gap-2'):
                self._render_actions_panel()
                self._render_rxlog_panel()
        
        # Start update timer (every 500ms)
        ui.timer(0.5, self._update_ui)
    
    def _render_device_panel(self) -> None:
        """Render the device info panel."""
        with ui.card().classes('w-full'):
            ui.label('📡 Device').classes('font-bold text-gray-600')
            self.device_label = ui.label('Connecting...').classes(
                'text-sm whitespace-pre-line'
            )
    
    def _render_contacts_panel(self) -> None:
        """Render the contacts panel."""
        with ui.card().classes('w-full'):
            ui.label('👥 Contacts').classes('font-bold text-gray-600')
            self.contacts_container = ui.column().classes(
                'w-full gap-1 max-h-96 overflow-y-auto'
            )
    
    def _render_map_panel(self) -> None:
        """Render the map panel with Leaflet."""
        with ui.card().classes('w-full'):
            self.map_widget = ui.leaflet(
                center=(52.5, 6.0),  # Default: Netherlands
                zoom=9
            ).classes('w-full h-72')
    
    def _render_input_panel(self) -> None:
        """Render the message input panel."""
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center gap-2'):
                self.msg_input = ui.input(
                    placeholder='Message...'
                ).classes('flex-grow')
                
                self.channel_select = ui.select(
                    options={0: '[0] Public'},
                    value=0
                ).classes('w-32')
                
                ui.button(
                    'Send',
                    on_click=self._send_message
                ).classes('bg-blue-500 text-white')
    
    def _render_channels_filter(self) -> None:
        """Render the channel filter panel with checkboxes."""
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center gap-4 justify-center'):
                ui.label('📻 Filter:').classes('text-sm text-gray-600')
                self.channels_filter_container = ui.row().classes('gap-4')
    
    def _render_messages_panel(self) -> None:
        """Render the messages panel."""
        with ui.card().classes('w-full'):
            ui.label('💬 Messages').classes('font-bold text-gray-600')
            self.messages_container = ui.column().classes(
                'w-full h-40 overflow-y-auto gap-0 text-sm font-mono '
                'bg-gray-50 p-2 rounded'
            )
    
    def _render_actions_panel(self) -> None:
        """Render the actions panel."""
        with ui.card().classes('w-full'):
            ui.label('⚡ Actions').classes('font-bold text-gray-600')
            with ui.row().classes('gap-2'):
                ui.button('🔄 Refresh', on_click=self._refresh)
                ui.button('📢 Advert', on_click=self._send_advert)
    
    def _render_rxlog_panel(self) -> None:
        """Render the RX log panel."""
        with ui.card().classes('w-full'):
            ui.label('📊 RX Log').classes('font-bold text-gray-600')
            self.rxlog_table = ui.table(
                columns=[
                    {'name': 'time', 'label': 'Time', 'field': 'time'},
                    {'name': 'snr', 'label': 'SNR', 'field': 'snr'},
                    {'name': 'type', 'label': 'Type', 'field': 'type'},
                ],
                rows=[]
            ).props('dense flat').classes('text-xs max-h-48 overflow-y-auto')
    
    def _update_ui(self) -> None:
        """
        Periodic UI update from shared data.
        
        Called every 500ms by the timer. Fetches a snapshot
        of the data and only updates UI elements that have changed.
        """
        try:
            # Check if UI elements exist
            if not self.status_label or not self.device_label:
                return
            
            # Get data snapshot
            data = self.shared.get_snapshot()
            
            # Determine if this is the first GUI render
            is_first_render = not data['gui_initialized']
            
            # Always update status
            self.status_label.text = data['status']
            
            # Update device info if changed OR first render
            if data['device_updated'] or is_first_render:
                self._update_device_info(data)
            
            # Update channels if changed OR first render
            if data['channels_updated'] or is_first_render:
                self._update_channels(data)
            
            # Update contacts if changed OR first render
            if data['contacts_updated'] or is_first_render:
                self._update_contacts(data)
            
            # Update map if contacts changed OR no markers OR first render
            if data['contacts'] and (data['contacts_updated'] or not self.markers or is_first_render):
                self._update_map(data)
            
            # Always refresh messages (for filter functionality)
            self._refresh_messages(data)
            
            # Update RX Log if changed
            if data['rxlog_updated'] and self.rxlog_table:
                self._update_rxlog(data)
            
            # Clear flags and mark GUI as initialized
            self.shared.clear_update_flags()
            
            # Only mark GUI as initialized when there is actual data
            if is_first_render and data['channels'] and data['contacts']:
                self.shared.mark_gui_initialized()
                
        except Exception as e:
            # Only log relevant errors
            error_str = str(e).lower()
            if "deleted" not in error_str and "client" not in error_str:
                print(f"GUI update error: {e}")
    
    def _update_device_info(self, data: Dict) -> None:
        """
        Update the device info panel.
        
        Args:
            data: Snapshot dictionary from SharedData
        """
        lines = []
        
        if data['name']:
            lines.append(f"📡 {data['name']}")
        if data['public_key']:
            lines.append(f"🔑 {data['public_key'][:16]}...")
        if data['radio_freq']:
            lines.append(f"📻 {data['radio_freq']:.3f} MHz")
            lines.append(f"⚙️ SF{data['radio_sf']} / {data['radio_bw']} kHz")
        if data['tx_power']:
            lines.append(f"⚡ TX: {data['tx_power']} dBm")
        if data['adv_lat'] and data['adv_lon']:
            lines.append(f"📍 {data['adv_lat']:.4f}, {data['adv_lon']:.4f}")
        if data['firmware_version']:
            lines.append(f"🏷️ {data['firmware_version']}")
        
        self.device_label.text = "\n".join(lines) if lines else "Loading..."
    
    def _update_channels(self, data: Dict) -> None:
        """
        Update the channel filter checkboxes and send select.
        
        Args:
            data: Snapshot dictionary from SharedData
        """
        if not self.channels_filter_container or not data['channels']:
            return
        
        # Rebuild filter checkboxes
        self.channels_filter_container.clear()
        self.channel_filters = {}
        
        with self.channels_filter_container:
            # DM filter checkbox
            cb_dm = ui.checkbox('DM', value=True)
            self.channel_filters['DM'] = cb_dm
            
            # Channel filter checkboxes
            for ch in data['channels']:
                idx = ch['idx']
                name = ch['name']
                cb = ui.checkbox(f"[{idx}] {name}", value=True)
                self.channel_filters[idx] = cb
        
        # Save channels for message display
        self.last_channels = data['channels']
        
        # Update send channel select
        if self.channel_select and data['channels']:
            options = {ch['idx']: f"[{ch['idx']}] {ch['name']}" for ch in data['channels']}
            self.channel_select.options = options
            if self.channel_select.value not in options:
                self.channel_select.value = list(options.keys())[0]
            self.channel_select.update()
    
    def _update_contacts(self, data: Dict) -> None:
        """
        Update the contacts list.
        
        Args:
            data: Snapshot dictionary from SharedData
        """
        if not self.contacts_container:
            return
        
        self.contacts_container.clear()
        
        with self.contacts_container:
            for key, contact in data['contacts'].items():
                ctype = contact.get('type', 0)
                icon = self.TYPE_ICONS.get(ctype, '○')
                name = contact.get('adv_name', key[:12])
                type_name = self.TYPE_NAMES.get(ctype, '-')
                lat = contact.get('adv_lat', 0)
                lon = contact.get('adv_lon', 0)
                has_loc = lat != 0 or lon != 0
                
                # Tooltip with details
                tooltip = f"{name}\nType: {type_name}\nKey: {key[:16]}...\nClick to send DM"
                if has_loc:
                    tooltip += f"\nLat: {lat:.4f}\nLon: {lon:.4f}"
                
                # Contact row - clickable for DM
                with ui.row().classes(
                    'w-full items-center gap-2 p-1 hover:bg-gray-100 rounded cursor-pointer'
                ).on('click', lambda e, k=key, n=name: self._open_dm_dialog(k, n)):
                    ui.label(icon).classes('text-sm')
                    ui.label(name[:15]).classes(
                        'text-sm flex-grow truncate'
                    ).tooltip(tooltip)
                    ui.label(type_name).classes('text-xs text-gray-500')
                    if has_loc:
                        ui.label('📍').classes('text-xs')
    
    def _open_dm_dialog(self, pubkey: str, contact_name: str) -> None:
        """
        Open a dialog to send a DM to a contact.
        
        Args:
            pubkey: Public key of the contact
            contact_name: Name of the contact for display
        """
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            ui.label(f'💬 DM to {contact_name}').classes('font-bold text-lg')
            
            msg_input = ui.input(
                placeholder='Type your message...'
            ).classes('w-full')
            
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                
                def send_dm():
                    text = msg_input.value
                    if text:
                        self.shared.cmd_queue.put({
                            'action': 'send_dm',
                            'pubkey': pubkey,
                            'text': text,
                            'contact_name': contact_name
                        })
                        dialog.close()
                
                ui.button('Send', on_click=send_dm).classes('bg-blue-500 text-white')
        
        dialog.open()
    
    def _update_map(self, data: Dict) -> None:
        """
        Update the map markers.
        
        Args:
            data: Snapshot dictionary from SharedData
        """
        if not self.map_widget:
            return
        
        # Remove old markers
        for marker in self.markers:
            try:
                self.map_widget.remove_layer(marker)
            except:
                pass
        self.markers.clear()
        
        # Own position marker
        if data['adv_lat'] and data['adv_lon']:
            m = self.map_widget.marker(latlng=(data['adv_lat'], data['adv_lon']))
            self.markers.append(m)
            self.map_widget.set_center((data['adv_lat'], data['adv_lon']))
        
        # Contact markers
        for key, contact in data['contacts'].items():
            lat = contact.get('adv_lat', 0)
            lon = contact.get('adv_lon', 0)
            if lat != 0 or lon != 0:
                m = self.map_widget.marker(latlng=(lat, lon))
                self.markers.append(m)
    
    def _update_rxlog(self, data: Dict) -> None:
        """
        Update the RX log table.
        
        Args:
            data: Snapshot dictionary from SharedData
        """
        rows = [
            {
                'time': entry['time'],
                'snr': f"{entry['snr']:.1f}",
                'type': entry['payload_type']
            }
            for entry in data['rx_log'][:20]
        ]
        self.rxlog_table.rows = rows
        self.rxlog_table.update()
    
    def _refresh_messages(self, data: Dict) -> None:
        """
        Refresh the messages container with filter application.
        
        Shows messages filtered based on channel checkboxes.
        Most recent messages are shown at the top.
        
        Args:
            data: Snapshot dictionary from SharedData
        """
        if not self.messages_container:
            return
        
        # Channel name lookup
        channel_names = {ch['idx']: ch['name'] for ch in self.last_channels}
        
        # Filter messages based on checkboxes
        filtered_messages = []
        for msg in data['messages']:
            ch_idx = msg['channel']
            
            if ch_idx is None:
                # DM message - check DM filter
                if self.channel_filters.get('DM') and not self.channel_filters['DM'].value:
                    continue
            else:
                # Channel message - check channel filter
                if ch_idx in self.channel_filters:
                    if not self.channel_filters[ch_idx].value:
                        continue
            
            filtered_messages.append(msg)
        
        # Rebuild messages container
        self.messages_container.clear()
        
        with self.messages_container:
            # Last 50 messages, newest at top
            for msg in reversed(filtered_messages[-50:]):
                direction = '→' if msg['direction'] == 'out' else '←'
                ch_idx = msg['channel']
                
                # Determine channel name
                if ch_idx is not None:
                    ch_name = channel_names.get(ch_idx, f'ch{ch_idx}')
                    ch_label = f"[{ch_name}]"
                else:
                    ch_label = '[DM]'
                
                # Format message line
                sender = msg.get('sender', '')
                if sender:
                    line = f"{msg['time']} {direction} {ch_label} {sender}: {msg['text']}"
                else:
                    line = f"{msg['time']} {direction} {ch_label} {msg['text']}"
                
                ui.label(line).classes('text-xs leading-tight')
    
    def _send_message(self) -> None:
        """Handle send button click - send message via command queue."""
        text = self.msg_input.value
        channel = self.channel_select.value
        
        if text:
            self.shared.cmd_queue.put({
                'action': 'send_message',
                'channel': channel,
                'text': text
            })
            self.msg_input.value = ''
    
    def _send_advert(self) -> None:
        """Handle advert button click - send advertisement."""
        self.shared.cmd_queue.put({'action': 'send_advert'})
    
    def _refresh(self) -> None:
        """Handle refresh button click - reload all data."""
        self.shared.cmd_queue.put({'action': 'refresh'})


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

# Global instances
shared_data: Optional[SharedData] = None
gui: Optional[MeshCoreGUI] = None


@ui.page('/')
def main_page():
    """NiceGUI page handler - render the GUI."""
    global gui
    if gui:
        gui.render()


def main():
    """
    Main entry point.
    
    Parses command line arguments, initializes SharedData and GUI,
    starts the BLE worker thread, and starts the NiceGUI server.
    """
    global shared_data, gui
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("MeshCore GUI - Threaded BLE Edition")
        print("=" * 40)
        print("Usage: python meshcore_gui_v2.py <BLE_ADDRESS>")
        print("Example: python meshcore_gui_v2.py literal:AA:BB:CC:DD:EE:FF")
        print()
        print("Tip: Use 'bluetoothctl scan on' to find devices")
        sys.exit(1)
    
    ble_address = sys.argv[1]
    
    # Startup banner
    print("=" * 50)
    print("MeshCore GUI - Threaded BLE Edition")
    print("=" * 50)
    print(f"Device:     {ble_address}")
    print(f"Debug mode: {'ON' if DEBUG else 'OFF'}")
    print("=" * 50)
    
    # Initialize shared data
    shared_data = SharedData()
    
    # Initialize GUI
    gui = MeshCoreGUI(shared_data)
    
    # Start BLE worker in separate thread
    worker = BLEWorker(ble_address, shared_data)
    worker.start()
    
    # Start NiceGUI server
    ui.run(
        title='MeshCore',
        port=8080,
        reload=False
    )


if __name__ == "__main__":
    main()
