"""Map panel — Leaflet map with own position and contact markers."""

from typing import Dict, List

from nicegui import ui


class MapPanel:
    """Interactive Leaflet map in the centre column."""

    def __init__(self) -> None:
        self._map = None
        self._markers: List = []

    @property
    def has_markers(self) -> bool:
        return bool(self._markers)

    def render(self) -> None:
        with ui.card().classes('w-full'):
            self._map = ui.leaflet(
                center=(52.5, 6.0), zoom=9
            ).classes('w-full h-72')

    def update(self, data: Dict) -> None:
        if not self._map:
            return

        # Remove old markers
        for marker in self._markers:
            try:
                self._map.remove_layer(marker)
            except Exception:
                pass
        self._markers.clear()

        # Own position
        if data['adv_lat'] and data['adv_lon']:
            m = self._map.marker(latlng=(data['adv_lat'], data['adv_lon']))
            self._markers.append(m)
            self._map.set_center((data['adv_lat'], data['adv_lon']))

        # Contact markers
        for key, contact in data['contacts'].items():
            lat = contact.get('adv_lat', 0)
            lon = contact.get('adv_lon', 0)
            if lat != 0 or lon != 0:
                m = self._map.marker(latlng=(lat, lon))
                self._markers.append(m)
