"""
Archive viewer page for MeshCore GUI.

Displays archived messages with filters and pagination.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from nicegui import ui

from meshcore_gui.core.models import Message
from meshcore_gui.core.protocols import SharedDataReadAndLookup
from meshcore_gui.gui.constants import TYPE_LABELS
from meshcore_gui.services.route_builder import RouteBuilder


class ArchivePage:
    """Archive viewer page with filters and pagination.
    
    Shows archived messages in the same style as the main messages panel,
    with filters (channel, date range, text search) and pagination.
    """
    
    def __init__(self, shared: SharedDataReadAndLookup, page_size: int = 50):
        """Initialize archive page.
        
        Args:
            shared: SharedData reader with contact lookup.
            page_size: Number of messages per page.
        """
        self._shared = shared
        self._page_size = page_size
        self._builder = RouteBuilder(shared)
        
        # Current page state (stored in app.storage.user)
        self._current_page = 0
        self._channel_name_filter = None
        self._text_filter = ""
        self._days_back = 7  # Default: last 7 days
        
    def render(self):
        """Render the archive page."""
        # Get snapshot once for use in filters and messages
        snapshot = self._shared.get_snapshot()
        
        with ui.column().classes('w-full p-4 gap-4'):
            # Header
            with ui.row().classes('w-full items-center'):
                ui.label('Message Archive').classes('text-2xl font-bold')
                ui.space()
                ui.button('Back to Dashboard', on_click=lambda: ui.navigate.to('/')).props('flat')
            
            # Filters
            self._render_filters(snapshot)
            
            # Messages
            self._render_messages(snapshot)
    
    def _render_filters(self, snapshot: dict):
        """Render filter controls.
        
        Args:
            snapshot: Current snapshot containing archive data.
        """
        with ui.card().classes('w-full'):
            ui.label('Filters').classes('text-lg font-bold mb-2')
            
            with ui.row().classes('w-full gap-4 items-end'):
                # Channel filter (built from distinct archived channel names)
                with ui.column().classes('flex-none'):
                    ui.label('Channel').classes('text-sm')
                    channels_options = {'All': None}
                    
                    # Build options from distinct channel names in archive
                    archive = snapshot.get('archive')
                    if archive:
                        for name in archive.get_distinct_channel_names():
                            channels_options[name] = name
                    
                    # Find current value label
                    current_label = 'All'
                    if self._channel_name_filter is not None:
                        for label, value in channels_options.items():
                            if value == self._channel_name_filter:
                                current_label = label
                                break
                    
                    channel_select = ui.select(
                        options=channels_options,
                        value=current_label,
                    ).classes('w-48')
                    
                    def on_channel_change(e):
                        # e.value is now the label, get the actual value
                        self._channel_name_filter = channels_options.get(channel_select.value)
                        self._current_page = 0
                        ui.navigate.reload()
                    
                    channel_select.on('update:model-value', on_channel_change)
                
                # Days back filter
                with ui.column().classes('flex-none'):
                    ui.label('Time Range').classes('text-sm')
                    days_select = ui.select(
                        options={
                            1: 'Last 24 hours',
                            7: 'Last 7 days',
                            30: 'Last 30 days',
                            90: 'Last 90 days',
                            9999: 'All time',
                        },
                        value=self._days_back,
                    ).classes('w-48')
                    
                    def on_days_change(e):
                        self._days_back = e.value
                        self._current_page = 0
                        
                        ui.navigate.reload()
                    
                    days_select.on('update:model-value', on_days_change)
                
                # Text search
                with ui.column().classes('flex-1'):
                    ui.label('Search Text').classes('text-sm')
                    text_input = ui.input(
                        placeholder='Search in messages...',
                        value=self._text_filter,
                    ).classes('w-full')
                    
                    def on_text_change(e):
                        self._text_filter = e.value
                        self._current_page = 0
                        
                    
                    text_input.on('change', on_text_change)
                
                # Search button
                ui.button('Search', on_click=lambda: ui.navigate.reload()).props('flat color=primary')
                
                # Clear filters
                def clear_filters():
                    self._channel_name_filter = None
                    self._text_filter = ""
                    self._days_back = 7
                    self._current_page = 0
                    
                    ui.navigate.reload()
                
                ui.button('Clear', on_click=clear_filters).props('flat')
    
    def _render_messages(self, snapshot: dict):
        """Render messages with pagination.
        
        Args:
            snapshot: Current snapshot containing archive data.
        """
        if not snapshot.get('archive'):
            ui.label('Archive not available').classes('text-gray-500 italic')
            return
        
        archive = snapshot['archive']
        
        # Calculate date range
        now = datetime.now(timezone.utc)
        after = None if self._days_back >= 9999 else now - timedelta(days=self._days_back)
        
        # Query messages
        messages, total_count = archive.query_messages(
            after=after,
            channel_name=self._channel_name_filter,
            text_search=self._text_filter if self._text_filter else None,
            limit=self._page_size,
            offset=self._current_page * self._page_size,
        )
        
        # Pagination info
        total_pages = (total_count + self._page_size - 1) // self._page_size
        
        with ui.column().classes('w-full gap-2'):
            # Pagination header
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(f'Showing {len(messages)} of {total_count} messages').classes('text-sm text-gray-600')
                
                if total_pages > 1:
                    with ui.row().classes('gap-2'):
                        # Previous button
                        def go_prev():
                            if self._current_page > 0:
                                self._current_page -= 1
                                
                                ui.navigate.reload()
                        
                        ui.button('Previous', on_click=go_prev).props(
                            f'flat {"disabled" if self._current_page == 0 else ""}'
                        )
                        
                        # Page indicator
                        ui.label(f'Page {self._current_page + 1} / {total_pages}').classes('mx-2')
                        
                        # Next button
                        def go_next():
                            if self._current_page < total_pages - 1:
                                self._current_page += 1
                                
                                ui.navigate.reload()
                        
                        ui.button('Next', on_click=go_next).props(
                            f'flat {"disabled" if self._current_page >= total_pages - 1 else ""}'
                        )
            
            # Messages list
            if not messages:
                ui.label('No messages found').classes('text-gray-500 italic mt-4')
            else:
                for msg_dict in messages:
                    self._render_message_card(msg_dict, snapshot)
            
            # Pagination footer
            if total_pages > 1:
                with ui.row().classes('w-full items-center justify-center mt-4'):
                    ui.button('Previous', on_click=go_prev).props(
                        f'flat {"disabled" if self._current_page == 0 else ""}'
                    )
                    ui.label(f'Page {self._current_page + 1} / {total_pages}').classes('mx-4')
                    ui.button('Next', on_click=go_next).props(
                        f'flat {"disabled" if self._current_page >= total_pages - 1 else ""}'
                    )
    
    def _render_message_card(self, msg_dict: dict, snapshot: dict):
        """Render a single message card with route table and reply option.
        
        Args:
            msg_dict: Message dictionary from archive.
            snapshot: Current snapshot for contact lookup.
        """
        # Convert dict to display format (same as messages_panel)
        time = msg_dict.get('time', '')
        sender = msg_dict.get('sender', 'Unknown')
        text = msg_dict.get('text', '')
        channel = msg_dict.get('channel', 0)
        direction = msg_dict.get('direction', 'in')
        snr = msg_dict.get('snr', 0.0)
        path_len = msg_dict.get('path_len', 0)
        path_hashes = msg_dict.get('path_hashes', [])
        
        # Channel name - use archived channel_name, fallback to index
        channel_name = msg_dict.get('channel_name', '')
        if not channel_name:
            channel_name = f'Ch {channel}' if channel is not None else 'DM'
        
        # Direction indicator
        dir_icon = '📤' if direction == 'out' else '📥'
        dir_color = 'text-blue-600' if direction == 'out' else 'text-green-600'
        
        # Card styling (same as messages_panel)
        with ui.card().classes('w-full hover:bg-gray-50'):
            with ui.column().classes('w-full gap-2'):
                # Main message content
                with ui.row().classes('w-full items-start gap-2'):
                    # Time + direction
                    with ui.column().classes('flex-none w-20'):
                        ui.label(time).classes('text-xs text-gray-600')
                        ui.label(dir_icon).classes(f'text-sm {dir_color}')
                    
                    # Content
                    with ui.column().classes('flex-1 gap-1'):
                        # Sender + channel
                        with ui.row().classes('gap-2 items-center'):
                            ui.label(sender).classes('font-bold')
                            ui.label(f'→ {channel_name}').classes('text-sm text-gray-600')
                            
                            if path_len > 0:
                                ui.label(f'↔ {path_len} hops').classes('text-xs text-gray-500')
                            
                            if snr and snr > 0:
                                snr_color = 'text-green-600' if snr >= 5 else 'text-orange-600' if snr >= 0 else 'text-red-600'
                                ui.label(f'SNR: {snr:.1f}').classes(f'text-xs {snr_color}')
                        
                        # Message text
                        ui.label(text).classes('text-sm whitespace-pre-wrap')
                
                # Route table (expandable)
                self._render_archive_route(msg_dict, snapshot)
                
                # Reply panel (expandable)
                with ui.expansion('💬 Reply', icon='reply').classes('w-full') as expansion:
                    expansion.classes('bg-gray-50')
                    with ui.column().classes('w-full gap-2 p-2'):
                        # Pre-filled reply text
                        prefilled = f"@{sender} "
                        
                        # Channel selector
                        ch_options = {}
                        default_ch = None
                        
                        for ch in snapshot.get('channels', []):
                            ch_idx = ch.get('idx', ch.get('index', 0))
                            ch_name = ch.get('name', f'Ch {ch_idx}')
                            ch_options[ch_idx] = f"[{ch_idx}] {ch_name}"
                            if default_ch is None:
                                default_ch = ch_idx
                        
                        with ui.row().classes('w-full items-center gap-2'):
                            msg_input = ui.input(
                                placeholder='Type your reply...',
                                value=prefilled
                            ).classes('flex-1')
                            
                            ch_select = ui.select(
                                options=ch_options,
                                value=default_ch
                            ).classes('w-40')
                            
                            def send_reply(inp=msg_input, sel=ch_select):
                                reply_text = inp.value
                                if reply_text:
                                    self._shared.put_command({
                                        'action': 'send_message',
                                        'channel': sel.value,
                                        'text': reply_text,
                                    })
                                    ui.notify(f'Reply sent to {channel_name}', type='positive')
                                    inp.value = prefilled  # Reset to prefilled
                                    expansion.open = False  # Close expansion
                            
                            ui.button('Send', on_click=send_reply).props('color=primary')

    def _render_archive_route(self, msg_dict: dict, snapshot: dict):
        """Render an inline route table for an archive message.

        Args:
            msg_dict: Message dictionary from archive.
            snapshot: Current snapshot for contact lookup.
        """
        with ui.expansion('🗺️ Route', icon='route').classes('w-full') as expansion:
            expansion.classes('bg-blue-50')
            with ui.column().classes('w-full gap-1 p-2'):
                msg = Message.from_dict(msg_dict)
                route = self._builder.build(msg, snapshot)

                path_nodes = route['path_nodes']
                sender = route['sender']
                self_node = route['self_node']

                rows = []

                # Sender row
                if sender:
                    rows.append({
                        'hop': 'Start',
                        'name': sender.name,
                        'hash': sender.pubkey[:2].upper() if sender.pubkey else '-',
                        'type': TYPE_LABELS.get(sender.type, '-'),
                        'role': '📱 Sender',
                    })
                else:
                    rows.append({
                        'hop': 'Start',
                        'name': msg.sender or 'Unknown',
                        'hash': msg.sender_pubkey[:2].upper() if msg.sender_pubkey else '-',
                        'type': '-',
                        'role': '📱 Sender',
                    })

                # Repeaters
                for i, node in enumerate(path_nodes):
                    rows.append({
                        'hop': str(i + 1),
                        'name': node.name,
                        'hash': node.pubkey[:2].upper() if node.pubkey else '-',
                        'type': TYPE_LABELS.get(node.type, '-'),
                        'role': '📡 Repeater',
                    })

                # Placeholder rows for unresolved hops
                if not path_nodes and msg.path_len > 0:
                    for i in range(msg.path_len):
                        rows.append({
                            'hop': str(i + 1),
                            'name': '-', 'hash': '-', 'type': '-',
                            'role': '📡 Repeater',
                        })

                # Receiver (self)
                rows.append({
                    'hop': 'End',
                    'name': self_node.name,
                    'hash': '-',
                    'type': 'Companion',
                    'role': '📱 Receiver' if msg.direction == 'in' else '📱 Sender',
                })

                ui.table(
                    columns=[
                        {'name': 'hop', 'label': 'Hop', 'field': 'hop', 'align': 'center'},
                        {'name': 'role', 'label': 'Role', 'field': 'role'},
                        {'name': 'name', 'label': 'Name', 'field': 'name'},
                        {'name': 'hash', 'label': 'ID', 'field': 'hash', 'align': 'center'},
                        {'name': 'type', 'label': 'Type', 'field': 'type'},
                    ],
                    rows=rows,
                ).props('dense flat bordered').classes('w-full')
    
    @staticmethod
    def setup_route(shared: SharedDataReadAndLookup):
        """Setup the /archive route.
        
        Args:
            shared: SharedData reader with contact lookup.
        """
        @ui.page('/archive')
        def archive_page():
            page = ArchivePage(shared)
            page.render()
