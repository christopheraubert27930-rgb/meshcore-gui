"""
BLE command handlers for MeshCore GUI.

Extracted from ``BLEWorker`` so that each command is an isolated unit
of work.  New commands can be registered without modifying existing
code (Open/Closed Principle).
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from meshcore import MeshCore, EventType

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
            'purge_unpinned': self._cmd_purge_unpinned,
            'set_auto_add': self._cmd_set_auto_add,
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

    async def _cmd_purge_unpinned(self, cmd: Dict) -> None:
        """Remove unpinned contacts from the MeshCore device.

        Iterates the list of public keys, calls ``remove_contact``
        for each one with a short delay between calls to avoid
        overwhelming the BLE link.  After completion, triggers a
        full refresh so the GUI reflects the new state.

        Expected command dict::

            {
                'action': 'purge_unpinned',
                'pubkeys': ['aabbcc...', ...],
            }
        """
        pubkeys: List[str] = cmd.get('pubkeys', [])
        if not pubkeys:
            self._shared.set_status("⚠️ No contacts to remove")
            return

        total = len(pubkeys)
        removed = 0
        errors = 0

        self._shared.set_status(
            f"🗑️ Removing {total} contacts..."
        )
        debug_print(f"Purge: starting removal of {total} contacts")

        for i, pubkey in enumerate(pubkeys, 1):
            try:
                r = await self._mc.commands.remove_contact(pubkey)
                if r.type == EventType.ERROR:
                    errors += 1
                    debug_print(
                        f"Purge: remove_contact({pubkey[:16]}) "
                        f"returned ERROR"
                    )
                else:
                    removed += 1
                    debug_print(
                        f"Purge: removed {pubkey[:16]} "
                        f"({i}/{total})"
                    )
            except Exception as exc:
                errors += 1
                debug_print(
                    f"Purge: remove_contact({pubkey[:16]}) "
                    f"exception: {exc}"
                )

            # Update status with progress
            self._shared.set_status(
                f"🗑️ Removing... {i}/{total}"
            )

            # Brief pause between BLE calls to avoid congestion
            if i < total:
                await asyncio.sleep(0.5)

        # Summary
        if errors:
            status = (
                f"⚠️ {removed} contacts removed, "
                f"{errors} failed"
            )
        else:
            status = f"✅ {removed} contacts removed from device"

        self._shared.set_status(status)
        print(f"Purge: {status}")

        # Resync with device to confirm new state
        if self._load_data_callback:
            await self._load_data_callback()

    async def _cmd_set_auto_add(self, cmd: Dict) -> None:
        """Toggle auto-add contacts on the MeshCore device.

        The SDK function ``set_manual_add_contacts(true)`` means
        *manual mode* (auto-add OFF).  The UI toggle is inverted:
        toggle ON = auto-add ON = ``set_manual_add_contacts(false)``.

        On failure the SharedData flag is rolled back so the GUI
        checkbox reverts on the next update cycle.

        Expected command dict::

            {
                'action': 'set_auto_add',
                'enabled': True/False,
            }
        """
        enabled: bool = cmd.get('enabled', False)
        # Invert: UI "auto-add ON" → manual_add = False
        manual_add = not enabled

        try:
            r = await self._mc.commands.set_manual_add_contacts(manual_add)
            if r.type == EventType.ERROR:
                # Rollback
                self._shared.set_auto_add_enabled(not enabled)
                self._shared.set_status(
                    "⚠️ Failed to change auto-add setting"
                )
                debug_print(
                    f"set_auto_add: ERROR response, rolled back to "
                    f"{'enabled' if not enabled else 'disabled'}"
                )
            else:
                self._shared.set_auto_add_enabled(enabled)
                state = "ON" if enabled else "OFF"
                self._shared.set_status(f"✅ Auto-add contacts: {state}")
                debug_print(f"set_auto_add: success → {state}")
        except Exception as exc:
            # Rollback
            self._shared.set_auto_add_enabled(not enabled)
            self._shared.set_status(
                f"⚠️ Auto-add error: {exc}"
            )
            debug_print(f"set_auto_add exception: {exc}")

    # ------------------------------------------------------------------
    # Callback for refresh (set by BLEWorker after construction)
    # ------------------------------------------------------------------

    _load_data_callback = None

    def set_load_data_callback(self, callback) -> None:
        """Register the worker's ``_load_data`` coroutine for refresh."""
        self._load_data_callback = callback
