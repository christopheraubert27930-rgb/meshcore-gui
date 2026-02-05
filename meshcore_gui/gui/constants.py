"""
Display constants for the GUI layer.

Contact type → icon/name/label mappings used by multiple panels.
"""

from typing import Dict

TYPE_ICONS: Dict[int, str] = {0: "○", 1: "📱", 2: "📡", 3: "🏠"}
TYPE_NAMES: Dict[int, str] = {0: "-", 1: "CLI", 2: "REP", 3: "ROOM"}
TYPE_LABELS: Dict[int, str] = {0: "-", 1: "Companion", 2: "Repeater", 3: "Room Server"}
