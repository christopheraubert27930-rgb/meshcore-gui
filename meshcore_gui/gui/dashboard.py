"""
Main dashboard page for MeshCore GUI.

Thin orchestrator that owns the layout and the 500 ms update timer.
All visual content is delegated to individual panel classes in
:mod:`meshcore_gui.gui.panels`.
"""

import logging

from nicegui import ui

from meshcore_gui.core.protocols import SharedDataReader
from meshcore_gui.gui.panels import (
    ActionsPanel,
    ContactsPanel,
    DevicePanel,
    FilterPanel,
    InputPanel,
    MapPanel,
    MessagesPanel,
    RxLogPanel,
)
from meshcore_gui.services.pin_store import PinStore


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

    def __init__(self, shared: SharedDataReader, pin_store: PinStore) -> None:
        self._shared = shared
        self._pin_store = pin_store

        # Panels (created fresh on each render)
        self._device: DevicePanel | None = None
        self._contacts: ContactsPanel | None = None
        self._map: MapPanel | None = None
        self._input: InputPanel | None = None
        self._filter: FilterPanel | None = None
        self._messages: MessagesPanel | None = None
        self._actions: ActionsPanel | None = None
        self._rxlog: RxLogPanel | None = None

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
        self._contacts = ContactsPanel(put_cmd, self._pin_store, self._shared.set_auto_add_enabled)
        self._map = MapPanel()
        self._input = InputPanel(put_cmd)
        self._filter = FilterPanel(self._shared.set_bot_enabled)
        self._messages = MessagesPanel()
        self._actions = ActionsPanel(put_cmd)
        self._rxlog = RxLogPanel()

        ui.dark_mode(False)

        # Header
        with ui.header().classes('bg-blue-600 text-white'):
            ui.label('🔗 MeshCore').classes('text-xl font-bold')
            ui.space()
            self._status_label = ui.label('Starting...').classes('text-sm')

        # Three-column layout
        with ui.row().classes('w-full h-full gap-2 p-2'):
            # Left column
            with ui.column().classes('w-72 gap-2'):
                self._device.render()
                self._contacts.render()

            # Centre column
            with ui.column().classes('flex-grow gap-2'):
                self._map.render()
                self._input.render()
                self._filter.render()
                self._messages.render()

            # Right column
            with ui.column().classes('w-64 gap-2'):
                self._actions.render()
                self._rxlog.render()

        # Start update timer
        ui.timer(0.5, self._update_ui)

    # ------------------------------------------------------------------
    # Timer-driven UI update
    # ------------------------------------------------------------------

    def _update_ui(self) -> None:
        try:
            if not self._status_label:
                return

            data = self._shared.get_snapshot()
            is_first = not self._initialized

            # Always update status
            self._status_label.text = data['status']

            # Device info
            if data['device_updated'] or is_first:
                self._device.update(data)

            # Channels → filter checkboxes + input dropdown
            if data['channels_updated'] or is_first:
                self._filter.update(data)
                self._input.update_channel_options(data['channels'])

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
                self._filter.channel_filters,
                self._filter.last_channels,
            )

            # RX Log
            if data['rxlog_updated']:
                self._rxlog.update(data)

            # Clear flags and mark initialised
            self._shared.clear_update_flags()

            if is_first and data['channels'] and data['contacts']:
                self._initialized = True
                self._shared.mark_gui_initialized()

        except Exception as e:
            err = str(e).lower()
            if "deleted" not in err and "client" not in err:
                print(f"GUI update error: {e}")
