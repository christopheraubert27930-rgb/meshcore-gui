"""
Main dashboard page for MeshCore GUI.

Thin orchestrator that owns the layout and the 500 ms update timer.
All visual content is delegated to individual panel classes in
:mod:`meshcore_gui.gui.panels`.
"""

import logging

from nicegui import ui

from meshcore_gui import config

from meshcore_gui.core.protocols import SharedDataReader
from meshcore_gui.gui.panels import (
    ActionsPanel,
    ContactsPanel,
    DevicePanel,
    MapPanel,
    MessagesPanel,
    RoomServerPanel,
    RxLogPanel,
)
from meshcore_gui.services.pin_store import PinStore
from meshcore_gui.services.room_password_store import RoomPasswordStore


# Suppress the harmless "Client has been deleted" warning that NiceGUI
# emits when a browser tab is refreshed while a ui.timer is active.
class _DeletedClientFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return 'Client has been deleted' not in record.getMessage()

logging.getLogger('nicegui').addFilter(_DeletedClientFilter())


class DashboardPage:
    """Main dashboard rendered at ``/``.

    Args:
        shared: SharedDataReader for data access and command dispatch.
    """

    def __init__(self, shared: SharedDataReader, pin_store: PinStore, room_password_store: RoomPasswordStore) -> None:
        self._shared = shared
        self._pin_store = pin_store
        self._room_password_store = room_password_store

        # Panels (created fresh on each render)
        self._device: DevicePanel | None = None
        self._contacts: ContactsPanel | None = None
        self._map: MapPanel | None = None
        self._messages: MessagesPanel | None = None
        self._actions: ActionsPanel | None = None
        self._rxlog: RxLogPanel | None = None
        self._room_server: RoomServerPanel | None = None

        # Header status label
        self._status_label = None

        # Local first-render flag
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Build the complete dashboard layout and start the timer."""
        self._initialized = False

        # Create panel instances
        put_cmd = self._shared.put_command
        self._device = DevicePanel()
        self._contacts = ContactsPanel(put_cmd, self._pin_store, self._shared.set_auto_add_enabled, self._on_add_room_server)
        self._map = MapPanel()
        self._messages = MessagesPanel(put_cmd)
        self._actions = ActionsPanel(put_cmd, self._shared.set_bot_enabled)
        self._rxlog = RxLogPanel()
        self._room_server = RoomServerPanel(put_cmd, self._room_password_store)

        ui.dark_mode(False)

        # Header
        with ui.header().classes('bg-blue-600 text-white'):
            ui.label(f'🔗 MeshCore v{config.VERSION}').classes('text-xl font-bold')
            ui.space()
            self._status_label = ui.label('Starting...').classes('text-sm')

        # Three-column layout
        with ui.row().classes('w-full h-full gap-2 p-2 flex-nowrap overflow-x-auto'):
            # Left column
            with ui.column().classes('w-72 gap-2'):
                self._device.render()
                self._contacts.render()

            # Centre column
            with ui.column().classes('flex-grow gap-2 min-w-[400px]'):
                self._map.render()
                self._messages.render()
                self._room_server.render()

            # Right column
            with ui.column().classes('w-64 gap-2 flex-shrink-0'):
                self._actions.render()
                self._rxlog.render()

        # Start update timer
        ui.timer(0.5, self._update_ui)

    # ------------------------------------------------------------------
    # Room Server callback (from ContactsPanel)
    # ------------------------------------------------------------------

    def _on_add_room_server(self, pubkey: str, name: str, password: str) -> None:
        """Handle adding a Room Server from the contacts panel.

        Delegates to the RoomServerPanel which persists the entry,
        creates the UI card and sends the login command.
        """
        if self._room_server:
            self._room_server.add_room(pubkey, name, password)

    # ------------------------------------------------------------------
    # Timer-driven UI update
    # ------------------------------------------------------------------

    def _update_ui(self) -> None:
        try:
            if not self._status_label:
                return

            data = self._shared.get_snapshot()
            is_first = not self._initialized

            # Mark initialised immediately — even if a panel update
            # crashes below, we must NOT retry the full first-render
            # path every 500 ms (that causes the infinite rebuild).
            if is_first:
                self._initialized = True

            # Always update status
            self._status_label.text = data['status']

            # Device info
            if data['device_updated'] or is_first:
                self._device.update(data)

            # Channels → filter checkboxes + channel dropdown + BOT state
            if data['channels_updated'] or is_first:
                self._messages.update_filters(data)
                self._messages.update_channel_options(data['channels'])
                self._actions.update(data)

            # Contacts
            if data['contacts_updated'] or is_first:
                self._contacts.update(data)

            # Map
            if data['contacts'] and (
                data['contacts_updated'] or not self._map.has_markers or is_first
            ):
                self._map.update(data)

            # Messages (always — for live filter changes)
            self._messages.update(
                data,
                self._messages.channel_filters,
                self._messages.last_channels,
                room_pubkeys=self._room_server.get_room_pubkeys() if self._room_server else None,
            )

            # Room Server panels (always — for live messages + contact changes)
            self._room_server.update(data)

            # RX Log
            if data['rxlog_updated']:
                self._rxlog.update(data)

            # Clear flags
            self._shared.clear_update_flags()

            # Signal BLE worker that GUI is ready for data
            if is_first and data['channels'] and data['contacts']:
                self._shared.mark_gui_initialized()

        except Exception as e:
            err = str(e).lower()
            if "deleted" not in err and "client" not in err:
                import traceback
                print(f"GUI update error: {e}")
                traceback.print_exc()
