"""RX log panel — table of recently received packets."""

from typing import Dict, List

from nicegui import ui

from meshcore_gui.core.models import RxLogEntry


class RxLogPanel:
    """RX log table in the right column."""

    def __init__(self) -> None:
        self._table = None

    def render(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('📊 RX Log').classes('font-bold text-gray-600')
            self._table = ui.table(
                columns=[
                    {'name': 'time', 'label': 'Time', 'field': 'time'},
                    {'name': 'snr', 'label': 'SNR', 'field': 'snr'},
                    {'name': 'type', 'label': 'Type', 'field': 'type'},
                ],
                rows=[],
            ).props('dense flat').classes('text-xs max-h-48 overflow-y-auto')

    def update(self, data: Dict) -> None:
        if not self._table:
            return
        entries: List[RxLogEntry] = data['rx_log'][:20]
        rows = [
            {
                'time': e.time,
                'snr': f"{e.snr:.1f}",
                'type': e.payload_type,
            }
            for e in entries
        ]
        self._table.rows = rows
        self._table.update()
