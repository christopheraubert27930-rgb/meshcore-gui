"""Messages panel — filtered message display with route navigation."""

from typing import Dict, List

from nicegui import ui

from meshcore_gui.core.models import Message


class MessagesPanel:
    """Displays filtered messages in the centre column.

    Messages are filtered based on channel checkboxes managed by
    :class:`~meshcore_gui.gui.panels.filter_panel.FilterPanel`.
    """

    def __init__(self) -> None:
        self._container = None

    def render(self) -> None:
        with ui.card().classes('w-full'):
            # Header with Archive button
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('💬 Messages').classes('font-bold text-gray-600')
                ui.button('📚 Archive', on_click=lambda: ui.run_javascript('window.open("/archive", "_blank")')).props('dense flat color=primary')
            
            self._container = ui.column().classes(
                'w-full h-40 overflow-y-auto gap-0 text-sm font-mono '
                'bg-gray-50 p-2 rounded'
            )

    def update(
        self,
        data: Dict,
        channel_filters: Dict,
        last_channels: List[Dict],
    ) -> None:
        """Refresh messages applying current filter state.

        Args:
            data:            Snapshot dict from SharedData.
            channel_filters: ``{channel_idx: checkbox, 'DM': checkbox}``
                             from FilterPanel.
            last_channels:   Channel list from FilterPanel.
        """
        if not self._container:
            return

        channel_names = {ch['idx']: ch['name'] for ch in last_channels}
        messages: List[Message] = data['messages']

        # Apply filters
        filtered = []
        for orig_idx, msg in enumerate(messages):
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
