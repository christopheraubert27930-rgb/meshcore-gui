"""
Archive viewer page for MeshCore GUI.

Displays archived messages with filters and pagination.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from nicegui import ui

from meshcore_gui.core.protocols import SharedDataReadAndLookup


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
        
        # Current page state (stored in app.storage.user)
        self._current_page = 0
        self._channel_filter = None
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
            snapshot: Current snapshot containing channels data.
        """
        with ui.card().classes('w-full'):
            ui.label('Filters').classes('text-lg font-bold mb-2')
            
            with ui.row().classes('w-full gap-4 items-end'):
                # Channel filter
                with ui.column().classes('flex-none'):
                    ui.label('Channel').classes('text-sm')
                    channels_options = {'All': None}
                    
                    # Build options from snapshot channels
                    for ch in snapshot.get('channels', []):
                        ch_idx = ch.get('idx', ch.get('index', 0))
                        ch_name = ch.get('name', f'Ch {ch_idx}')
                        channels_options[ch_name] = ch_idx
                    
                    # Find current value label
                    current_label = 'All'
                    if self._channel_filter is not None:
                        for label, value in channels_options.items():
                            if value == self._channel_filter:
                                current_label = label
                                break
                    
                    channel_select = ui.select(
                        options=channels_options,
                        value=current_label,
                    ).classes('w-48')
                    
                    def on_channel_change(e):
                        # e.value is now the label, get the actual value
                        self._channel_filter = channels_options.get(channel_select.value)
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
                    self._channel_filter = None
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
            channel=self._channel_filter,
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
        """Render a single message card with reply option.
        
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
        message_hash = msg_dict.get('message_hash', '')
        
        # Channel name - lookup from snapshot
        channel_name = f'Ch {channel}'  # Default
        for ch in snapshot.get('channels', []):
            ch_idx = ch.get('idx', ch.get('index', 0))
            if ch_idx == channel:
                channel_name = ch.get('name', f'Ch {channel}')
                break
        
        # Direction indicator
        dir_icon = '📤' if direction == 'out' else '📥'
        dir_color = 'text-blue-600' if direction == 'out' else 'text-green-600'
        
        # Card styling (same as messages_panel)
        with ui.card().classes('w-full hover:bg-gray-50') as card:
            with ui.column().classes('w-full gap-2'):
                # Main message content (clickable for route)
                with ui.row().classes('w-full items-start gap-2 cursor-pointer') as main_row:
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
                            
                            if snr > 0:
                                snr_color = 'text-green-600' if snr >= 5 else 'text-orange-600' if snr >= 0 else 'text-red-600'
                                ui.label(f'SNR: {snr:.1f}').classes(f'text-xs {snr_color}')
                        
                        # Message text
                        ui.label(text).classes('text-sm whitespace-pre-wrap')
                
                # Reply panel (expandable)
                with ui.expansion('💬 Reply', icon='reply').classes('w-full') as expansion:
                    expansion.classes('bg-gray-50')
                    with ui.column().classes('w-full gap-2 p-2'):
                        # Pre-filled reply text
                        prefilled = f"@{sender} "
                        
                        # Channel selector
                        ch_options = {}
                        default_ch = 0
                        
                        for ch in snapshot.get('channels', []):
                            ch_idx = ch.get('idx', ch.get('index', 0))
                            ch_name = ch.get('name', f'Ch {ch_idx}')
                            ch_options[ch_idx] = f"[{ch_idx}] {ch_name}"
                            if default_ch == 0:  # Use first channel as default
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
            
            # Click handler for main row - open route visualization
            def open_route():
                # Find message in current snapshot to get its index
                current_messages = snapshot.get('messages', [])
                
                # Try to find this message by hash in current messages
                msg_index = -1
                for idx, msg in enumerate(current_messages):
                    if hasattr(msg, 'message_hash') and msg.message_hash == message_hash:
                        msg_index = idx
                        break
                
                if msg_index >= 0:
                    # Message is in current buffer - use normal route page
                    ui.run_javascript(f'window.open("/route/{msg_index}", "_blank")')
                else:
                    # Message is only in archive - show notification
                    ui.notify('Route visualization only available for recent messages', type='warning')
            
            main_row.on('click', open_route)
    
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
