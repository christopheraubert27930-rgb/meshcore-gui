"""
BLE command handlers for MeshCore GUI.

Extracted from ``BLEWorker`` so that each command is an isolated unit
of work.  New commands can be registered without modifying existing
code (Open/Closed Principle).
"""

from datetime import datetime
from typing import Dict, Optional

from meshcore import MeshCore

from meshcore_gui.config import debug_print
from meshcore_gui.core.models import Message
from meshcore_gui.core.protocols import SharedDataWriter


class CommandHandler:
    """Dispatches and executes commands sent from the GUI.

    Args:
        mc:     Connected MeshCore instance.
        shared: SharedDataWriter for storing results.
    """

    def __init__(self, mc: MeshCore, shared: SharedDataWriter) -> None:
        self._mc = mc
        self._shared = shared

        # Handler registry — add new commands here (OCP)
        self._handlers: Dict[str, object] = {
            'send_message': self._cmd_send_message,
            'send_dm': self._cmd_send_dm,
            'send_advert': self._cmd_send_advert,
            'refresh': self._cmd_refresh,
        }

    async def process_all(self) -> None:
        """Drain the command queue and dispatch each command."""
        while True:
            cmd = self._shared.get_next_command()
            if cmd is None:
                break
            await self._dispatch(cmd)

    async def _dispatch(self, cmd: Dict) -> None:
        action = cmd.get('action')
        handler = self._handlers.get(action)
        if handler:
            await handler(cmd)
        else:
            debug_print(f"Unknown command action: {action}")

    # ------------------------------------------------------------------
    # Individual command handlers
    # ------------------------------------------------------------------

    async def _cmd_send_message(self, cmd: Dict) -> None:
        channel = cmd.get('channel', 0)
        text = cmd.get('text', '')
        is_bot = cmd.get('_bot', False)
        if text:
            await self._mc.commands.send_chan_msg(channel, text)
            if not is_bot:
                self._shared.add_message(Message(
                    time=datetime.now().strftime('%H:%M:%S'),
                    sender='Me',
                    text=text,
                    channel=channel,
                    direction='out',
                ))
            debug_print(
                f"{'BOT' if is_bot else 'Sent'} message to "
                f"channel {channel}: {text[:30]}"
            )

    async def _cmd_send_dm(self, cmd: Dict) -> None:
        pubkey = cmd.get('pubkey', '')
        text = cmd.get('text', '')
        contact_name = cmd.get('contact_name', pubkey[:8])
        if text and pubkey:
            await self._mc.commands.send_msg(pubkey, text)
            self._shared.add_message(Message(
                time=datetime.now().strftime('%H:%M:%S'),
                sender='Me',
                text=text,
                channel=None,
                direction='out',
                sender_pubkey=pubkey,
            ))
            debug_print(f"Sent DM to {contact_name}: {text[:30]}")

    async def _cmd_send_advert(self, cmd: Dict) -> None:
        await self._mc.commands.send_advert(flood=True)
        self._shared.set_status("📢 Advert sent")
        debug_print("Advert sent")

    async def _cmd_refresh(self, cmd: Dict) -> None:
        debug_print("Refresh requested")
        # Delegate to the worker's _load_data via a callback
        if self._load_data_callback:
            await self._load_data_callback()

    # ------------------------------------------------------------------
    # Callback for refresh (set by BLEWorker after construction)
    # ------------------------------------------------------------------

    _load_data_callback = None

    def set_load_data_callback(self, callback) -> None:
        """Register the worker's ``_load_data`` coroutine for refresh."""
        self._load_data_callback = callback
