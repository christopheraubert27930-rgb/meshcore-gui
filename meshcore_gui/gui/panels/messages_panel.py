"""Messages panel — filtered message display with inline filters and message input."""

from typing import Callable, Dict, List, Set

from nicegui import ui

from meshcore_gui.core.models import Message


class MessagesPanel:
    """Displays filtered messages with inline filter checkboxes and message input.

    Filter checkboxes (DM + channels) appear in the header row between
    the "Messages" label and the "Archive" button.  The message input,
    channel selector and send button appear below the message list.

    Args:
        put_command: Callable to enqueue a command dict for the BLE worker.
    """

    def __init__(self, put_command: Callable[[Dict], None]) -> None:
        self._put_command = put_command
        self._container = None
        self._filter_container = None
        self._channel_filters: Dict = {}
        self._last_channels: List[Dict] = []
        self._msg_input = None
        self._channel_select = None

    # -- Properties (same as FilterPanel originals) --------------------

    @property
    def channel_filters(self) -> Dict:
        """Current filter checkboxes (key: channel idx or ``'DM'``)."""
        return self._channel_filters

    @property
    def last_channels(self) -> List[Dict]:
        """Channel list from the most recent update."""
        return self._last_channels

    # -- Render --------------------------------------------------------

    def render(self) -> None:
        with ui.card().classes('w-full'):
            # Header row: Messages label + filter checkboxes + Archive button
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('💬 Messages').classes('font-bold text-gray-600')
                self._filter_container = ui.row().classes('flex-grow gap-4 items-center justify-center')
                ui.button('📚 Archive', on_click=lambda: ui.run_javascript('window.open("/archive", "_blank")')).props('dense flat color=primary')

            # Message container
            self._container = ui.column().classes(
                'w-full h-40 overflow-y-auto gap-0 text-sm font-mono '
                'bg-gray-50 p-2 rounded'
            )

            # Send message row (moved from InputPanel)
            with ui.row().classes('w-full items-center gap-2'):
                self._msg_input = ui.input(
                    placeholder='Message...'
                ).classes('flex-grow')

                self._channel_select = ui.select(
                    options={0: '[0] Public'}, value=0
                ).classes('w-32')

                ui.button(
                    'Send', on_click=self._send_message
                ).classes('bg-blue-500 text-white')

    # -- Filter checkboxes (moved from FilterPanel) --------------------

    def update_filters(self, data: Dict) -> None:
        """Rebuild filter checkboxes when channel data changes."""
        if not self._filter_container or not data['channels']:
            return

        self._filter_container.clear()
        self._channel_filters = {}

        with self._filter_container:
            cb_dm = ui.checkbox('DM', value=True)
            self._channel_filters['DM'] = cb_dm

            for ch in data['channels']:
                cb = ui.checkbox(f"[{ch['idx']}] {ch['name']}", value=True)
                self._channel_filters[ch['idx']] = cb

        self._last_channels = data['channels']

    # -- Channel selector (moved from InputPanel) ----------------------

    def update_channel_options(self, channels: List[Dict]) -> None:
        """Update the channel dropdown options."""
        if not self._channel_select or not channels:
            return
        opts = {ch['idx']: f"[{ch['idx']}] {ch['name']}" for ch in channels}
        self._channel_select.options = opts
        if self._channel_select.value not in opts:
            self._channel_select.value = list(opts.keys())[0]
        self._channel_select.update()

    # -- Send message (moved from InputPanel) --------------------------

    def _send_message(self) -> None:
        text = self._msg_input.value
        channel = self._channel_select.value
        if text:
            self._put_command({
                'action': 'send_message',
                'channel': channel,
                'text': text,
            })
            self._msg_input.value = ''

    # -- Message display -----------------------------------------------

    @staticmethod
    def _is_room_message(msg: Message, room_pubkeys: Set[str]) -> bool:
        """Return True if *msg* belongs to a Room Server.

        Matches when the message's ``sender_pubkey`` prefix-matches
        any tracked room pubkey (same logic as RoomServerPanel).
        """
        if not msg.sender_pubkey or not room_pubkeys:
            return False
        for rpk in room_pubkeys:
            if (msg.sender_pubkey.startswith(rpk[:16])
                    or rpk.startswith(msg.sender_pubkey[:16])):
                return True
        return False

    def update(
        self,
        data: Dict,
        channel_filters: Dict,
        last_channels: List[Dict],
        room_pubkeys: Set[str] | None = None,
    ) -> None:
        """Refresh messages applying current filter state.

        Args:
            data:            Snapshot dict from SharedData.
            channel_filters: ``{channel_idx: checkbox, 'DM': checkbox}``
                             from filter checkboxes.
            last_channels:   Channel list from filter state.
            room_pubkeys:    Pubkeys of Room Servers to exclude from
                             the general message view (shown in
                             RoomServerPanel instead).
        """
        if not self._container:
            return

        room_pks = room_pubkeys or set()
        channel_names = {ch['idx']: ch['name'] for ch in last_channels}
        messages: List[Message] = data['messages']

        # Apply filters
        filtered = []
        for orig_idx, msg in enumerate(messages):
            # Skip room server messages (shown in RoomServerPanel)
            if self._is_room_message(msg, room_pks):
                continue
            if msg.channel is None:
                if channel_filters.get('DM') and not channel_filters['DM'].value:
                    continue
            else:
                if msg.channel in channel_filters and not channel_filters[msg.channel].value:
                    continue
            filtered.append((orig_idx, msg))

        # Rebuild
        self._container.clear()

        with self._container:
            for orig_idx, msg in reversed(filtered[-50:]):
                direction = '→' if msg.direction == 'out' else '←'

                ch_label = (
                    f"[{channel_names.get(msg.channel, f'ch{msg.channel}')}]"
                    if msg.channel is not None
                    else '[DM]'
                )

                path_len = msg.path_len
                has_path = bool(msg.path_hashes)
                if msg.direction == 'in' and path_len > 0:
                    hop_tag = f' [{path_len}h{"✓" if has_path else ""}]'
                else:
                    hop_tag = ''

                if msg.sender:
                    line = f"{msg.time} {direction} {ch_label}{hop_tag} {msg.sender}: {msg.text}"
                else:
                    line = f"{msg.time} {direction} {ch_label}{hop_tag} {msg.text}"

                ui.label(line).classes(
                    'text-xs leading-tight cursor-pointer '
                    'hover:bg-blue-50 rounded px-1'
                ).on('click', lambda e, i=orig_idx: ui.navigate.to(
                    f'/route/{i}', new_tab=True
                ))
