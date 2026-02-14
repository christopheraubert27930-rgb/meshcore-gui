"""
Archive viewer page for MeshCore GUI.

Displays archived messages with filters and pagination.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from nicegui import ui

from meshcore_gui.core.models import Message
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
                    
                    # DM option (messages with channel=None)
                    channels_options['DM'] = 'DM'
                    
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
        
        # Handle DM filter separately (query_messages doesn't filter by channel=None)
        is_dm_filter = (self._channel_name_filter == 'DM')
        query_channel = None if is_dm_filter else self._channel_name_filter
        
        # Query messages
        messages, total_count = archive.query_messages(
            after=after,
            channel_name=query_channel,
            text_search=self._text_filter if self._text_filter else None,
            limit=self._page_size if not is_dm_filter else self._page_size * 5,
            offset=self._current_page * self._page_size if not is_dm_filter else 0,
        )
        
        # Post-filter for DM (channel is None)
        if is_dm_filter:
            messages = [m for m in messages if m.get('channel') is None]
            total_count = len(messages)
            # Apply pagination manually
            start = self._current_page * self._page_size
            messages = messages[start:start + self._page_size]
        
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
            
            # Messages list (single-line format, same as main page)
            if not messages:
                ui.label('No messages found').classes('text-gray-500 italic mt-4')
            else:
                with ui.column().classes(
                    'w-full overflow-y-auto gap-0 text-sm font-mono '
                    'bg-gray-50 p-2 rounded'
                ):
                    for msg_dict in messages:
                        msg = Message.from_dict(msg_dict)
                        line = msg.format_line()
                        msg_hash = msg_dict.get('message_hash', '')
                        
                        ui.label(line).classes(
                            'text-xs leading-tight cursor-pointer '
                            'hover:bg-blue-50 rounded px-1'
                        ).on('click', lambda e, h=msg_hash: ui.navigate.to(
                            f'/route/{h}', new_tab=True,
                        ) if h else None)
            
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
