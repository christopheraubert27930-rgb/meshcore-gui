"""Actions panel — refresh and advertise buttons."""

from typing import Callable, Dict

from nicegui import ui


class ActionsPanel:
    """Action buttons in the right column.

    Args:
        put_command: Callable to enqueue a command dict for the BLE worker.
    """

    def __init__(self, put_command: Callable[[Dict], None]) -> None:
        self._put_command = put_command

    def render(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('⚡ Actions').classes('font-bold text-gray-600')
            with ui.row().classes('gap-2'):
                ui.button('🔄 Refresh', on_click=self._refresh)
                ui.button('📢 Advert', on_click=self._advert)

    def _refresh(self) -> None:
        self._put_command({'action': 'refresh'})

    def _advert(self) -> None:
        self._put_command({'action': 'send_advert'})
