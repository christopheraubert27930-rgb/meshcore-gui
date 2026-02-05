"""Contacts panel — list of known mesh nodes with click-to-DM."""

from typing import Callable, Dict

from nicegui import ui

from meshcore_gui.gui.constants import TYPE_ICONS, TYPE_NAMES


class ContactsPanel:
    """Displays contacts in the left column. Click opens a DM dialog.

    Args:
        put_command: Callable to enqueue a command dict for the BLE worker.
    """

    def __init__(self, put_command: Callable[[Dict], None]) -> None:
        self._put_command = put_command
        self._container = None

    def render(self) -> None:
        with ui.card().classes('w-full'):
            ui.label('👥 Contacts').classes('font-bold text-gray-600')
            self._container = ui.column().classes(
                'w-full gap-1 max-h-96 overflow-y-auto'
            )

    def update(self, data: Dict) -> None:
        if not self._container:
            return

        self._container.clear()

        with self._container:
            for key, contact in data['contacts'].items():
                ctype = contact.get('type', 0)
                icon = TYPE_ICONS.get(ctype, '○')
                name = contact.get('adv_name', key[:12])
                type_name = TYPE_NAMES.get(ctype, '-')
                lat = contact.get('adv_lat', 0)
                lon = contact.get('adv_lon', 0)
                has_loc = lat != 0 or lon != 0

                tooltip = (
                    f"{name}\nType: {type_name}\n"
                    f"Key: {key[:16]}...\nClick to send DM"
                )
                if has_loc:
                    tooltip += f"\nLat: {lat:.4f}\nLon: {lon:.4f}"

                with ui.row().classes(
                    'w-full items-center gap-2 p-1 '
                    'hover:bg-gray-100 rounded cursor-pointer'
                ).on('click', lambda e, k=key, n=name: self._open_dm_dialog(k, n)):
                    ui.label(icon).classes('text-sm')
                    ui.label(name[:15]).classes(
                        'text-sm flex-grow truncate'
                    ).tooltip(tooltip)
                    ui.label(type_name).classes('text-xs text-gray-500')
                    if has_loc:
                        ui.label('📍').classes('text-xs')

    # ------------------------------------------------------------------
    # DM dialog
    # ------------------------------------------------------------------

    def _open_dm_dialog(self, pubkey: str, contact_name: str) -> None:
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            ui.label(f'💬 DM to {contact_name}').classes('font-bold text-lg')
            msg_input = ui.input(placeholder='Type your message...').classes('w-full')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')

                def send_dm():
                    text = msg_input.value
                    if text:
                        self._put_command({
                            'action': 'send_dm',
                            'pubkey': pubkey,
                            'text': text,
                            'contact_name': contact_name,
                        })
                        dialog.close()

                ui.button('Send', on_click=send_dm).classes('bg-blue-500 text-white')
        dialog.open()
