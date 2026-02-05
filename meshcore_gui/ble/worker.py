"""
BLE communication worker for MeshCore GUI.

Runs in a separate thread with its own asyncio event loop.  Connects
to the MeshCore device, wires up collaborators, and runs the command
processing loop.

Responsibilities deliberately kept narrow (SRP):
    - Thread lifecycle and asyncio loop
    - BLE connection and initial data loading
    - Wiring CommandHandler and EventHandler

Command execution  → :mod:`meshcore_gui.ble.commands`
Event handling     → :mod:`meshcore_gui.ble.events`
Packet decoding    → :mod:`meshcore_gui.ble.packet_decoder`
Bot logic          → :mod:`meshcore_gui.services.bot`
Deduplication      → :mod:`meshcore_gui.services.dedup`
"""

import asyncio
import threading
from typing import Optional

from meshcore import MeshCore, EventType

from meshcore_gui.config import CHANNELS_CONFIG, debug_print
from meshcore_gui.core.protocols import SharedDataWriter
from meshcore_gui.ble.commands import CommandHandler
from meshcore_gui.ble.events import EventHandler
from meshcore_gui.ble.packet_decoder import PacketDecoder
from meshcore_gui.services.bot import BotConfig, MeshBot
from meshcore_gui.services.dedup import DualDeduplicator


class BLEWorker:
    """BLE communication worker that runs in a separate thread.

    Args:
        address: BLE MAC address (e.g. ``"literal:AA:BB:CC:DD:EE:FF"``).
        shared:  SharedDataWriter for thread-safe communication.
    """

    def __init__(self, address: str, shared: SharedDataWriter) -> None:
        self.address = address
        self.shared = shared
        self.mc: Optional[MeshCore] = None
        self.running = True

        # Collaborators (created eagerly, wired after connection)
        self._decoder = PacketDecoder()
        self._dedup = DualDeduplicator(max_size=200)
        self._bot = MeshBot(
            config=BotConfig(),
            command_sink=shared.put_command,
            enabled_check=shared.is_bot_enabled,
        )

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker in a new daemon thread."""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        debug_print("BLE worker thread started")

    def _run(self) -> None:
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        await self._connect()
        if self.mc:
            while self.running:
                await self._cmd_handler.process_all()
                await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        self.shared.set_status(f"🔄 Connecting to {self.address}...")
        try:
            print(f"BLE: Connecting to {self.address}...")
            self.mc = await MeshCore.create_ble(self.address)
            print("BLE: Connected!")

            await asyncio.sleep(1)

            # Wire collaborators now that mc is available
            self._evt_handler = EventHandler(
                shared=self.shared,
                decoder=self._decoder,
                dedup=self._dedup,
                bot=self._bot,
            )
            self._cmd_handler = CommandHandler(mc=self.mc, shared=self.shared)
            self._cmd_handler.set_load_data_callback(self._load_data)

            # Subscribe to events
            self.mc.subscribe(EventType.CHANNEL_MSG_RECV, self._evt_handler.on_channel_msg)
            self.mc.subscribe(EventType.CONTACT_MSG_RECV, self._evt_handler.on_contact_msg)
            self.mc.subscribe(EventType.RX_LOG_DATA, self._evt_handler.on_rx_log)

            await self._load_data()
            await self._load_channel_keys()
            await self.mc.start_auto_message_fetching()

            self.shared.set_connected(True)
            self.shared.set_status("✅ Connected")
            print("BLE: Ready!")

        except Exception as e:
            print(f"BLE: Connection error: {e}")
            self.shared.set_status(f"❌ {e}")

    # ------------------------------------------------------------------
    # Initial data loading
    # ------------------------------------------------------------------

    async def _load_data(self) -> None:
        """Load device info, channels and contacts."""
        # send_appstart (retries)
        self.shared.set_status("🔄 Device info...")
        for i in range(5):
            debug_print(f"send_appstart attempt {i + 1}")
            r = await self.mc.commands.send_appstart()
            if r.type != EventType.ERROR:
                print(f"BLE: send_appstart OK: {r.payload.get('name')}")
                self.shared.update_from_appstart(r.payload)
                break
            await asyncio.sleep(0.3)

        # send_device_query (retries)
        for i in range(5):
            debug_print(f"send_device_query attempt {i + 1}")
            r = await self.mc.commands.send_device_query()
            if r.type != EventType.ERROR:
                print(f"BLE: send_device_query OK: {r.payload.get('ver')}")
                self.shared.update_from_device_query(r.payload)
                break
            await asyncio.sleep(0.3)

        # Channels (hardcoded — BLE get_channel is unreliable)
        self.shared.set_status("🔄 Channels...")
        self.shared.set_channels(CHANNELS_CONFIG)
        print(f"BLE: Channels loaded: {[c['name'] for c in CHANNELS_CONFIG]}")

        # Contacts
        self.shared.set_status("🔄 Contacts...")
        r = await self.mc.commands.get_contacts()
        if r.type != EventType.ERROR:
            self.shared.set_contacts(r.payload)
            print(f"BLE: Contacts loaded: {len(r.payload)} contacts")

    async def _load_channel_keys(self) -> None:
        """Load channel decryption keys from device or derive from name.

        Channels that cannot be confirmed on the device are logged with
        a warning.  Sending and receiving on unconfirmed channels will
        likely fail because the device does not know about them.
        """
        self.shared.set_status("🔄 Channel keys...")
        confirmed: list[str] = []
        missing: list[str] = []

        for ch in CHANNELS_CONFIG:
            idx, name = ch['idx'], ch['name']
            loaded = False

            for attempt in range(3):
                try:
                    r = await self.mc.commands.get_channel(idx)
                    if r.type != EventType.ERROR:
                        secret = r.payload.get('channel_secret')
                        if secret and isinstance(secret, bytes) and len(secret) >= 16:
                            self._decoder.add_channel_key(idx, secret[:16])
                            print(f"BLE: ✅ Channel [{idx}] '{name}' — key loaded from device")
                            confirmed.append(f"[{idx}] {name}")
                            loaded = True
                            break
                except Exception as exc:
                    debug_print(f"get_channel({idx}) attempt {attempt + 1} error: {exc}")
                await asyncio.sleep(0.3)

            if not loaded:
                self._decoder.add_channel_key_from_name(idx, name)
                missing.append(f"[{idx}] {name}")
                print(f"BLE: ⚠️  Channel [{idx}] '{name}' — NOT found on device (key derived from name)")

        if missing:
            print(f"BLE: ⚠️  Channels not confirmed on device: {', '.join(missing)}")
            print(f"BLE: ⚠️  Sending/receiving on these channels may not work.")
            print(f"BLE: ⚠️  Check your device config with: meshcli -d <BLE_ADDRESS> → get_channels")

        print(f"BLE: PacketDecoder ready — has_keys={self._decoder.has_keys}")
        print(f"BLE: Confirmed: {', '.join(confirmed) if confirmed else 'none'}")
        print(f"BLE: Unconfirmed: {', '.join(missing) if missing else 'none'}")
