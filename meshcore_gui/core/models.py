"""
Domain model for MeshCore GUI.

Typed dataclasses that replace untyped Dict objects throughout the
codebase.  Each class represents a core domain concept.  All classes
are immutable-friendly (frozen is not used because SharedData mutates
collections, but fields are not reassigned after construction).

Migration note
~~~~~~~~~~~~~~
``SharedData.get_snapshot()`` still returns a plain dict for backward
compatibility with the NiceGUI timer loop.  Inside that dict, however,
``messages`` and ``rx_log`` are now lists of dataclass instances.
UI code can access attributes directly (``msg.sender``) or fall back
to ``dataclasses.asdict(msg)`` if a plain dict is needed.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A channel message or direct message (DM).

    Attributes:
        time:          Formatted timestamp (HH:MM:SS).
        sender:        Display name of the sender.
        text:          Message body.
        channel:       Channel index, or ``None`` for a DM.
        direction:     ``'in'`` for received, ``'out'`` for sent.
        snr:           Signal-to-noise ratio (dB), if available.
        path_len:      Hop count from the LoRa frame header.
        sender_pubkey: Full public key of the sender (hex string).
        path_hashes:   List of 2-char hex strings, one per repeater.
        message_hash:  Deterministic packet identifier (hex string).
        channel_name:  Human-readable channel name (resolved at add time).
    """

    time: str
    sender: str
    text: str
    channel: Optional[int]
    direction: str
    snr: Optional[float] = None
    path_len: int = 0
    sender_pubkey: str = ""
    path_hashes: List[str] = field(default_factory=list)
    message_hash: str = ""
    channel_name: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Message":
        """Create a Message from an archive dictionary.

        Args:
            d: Dictionary as stored by MessageArchive.

        Returns:
            Message dataclass instance.
        """
        return Message(
            time=d.get("time", ""),
            sender=d.get("sender", ""),
            text=d.get("text", ""),
            channel=d.get("channel"),
            direction=d.get("direction", "in"),
            snr=d.get("snr"),
            path_len=d.get("path_len", 0),
            sender_pubkey=d.get("sender_pubkey", ""),
            path_hashes=d.get("path_hashes", []),
            message_hash=d.get("message_hash", ""),
            channel_name=d.get("channel_name", ""),
        )


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

@dataclass
class Contact:
    """A known mesh network node.

    Attributes:
        pubkey:       Full public key (hex string).
        adv_name:     Advertised display name.
        type:         Node type (0=unknown, 1=CLI, 2=REP, 3=ROOM).
        adv_lat:      Advertised latitude (0.0 if unknown).
        adv_lon:      Advertised longitude (0.0 if unknown).
        out_path:     Hex string of stored route (2 hex chars per hop).
        out_path_len: Number of hops in ``out_path``.
    """

    pubkey: str
    adv_name: str = ""
    type: int = 0
    adv_lat: float = 0.0
    adv_lon: float = 0.0
    out_path: str = ""
    out_path_len: int = 0

    @staticmethod
    def from_dict(pubkey: str, d: dict) -> "Contact":
        """Create a Contact from a meshcore contacts dict entry."""
        return Contact(
            pubkey=pubkey,
            adv_name=d.get("adv_name", ""),
            type=d.get("type", 0),
            adv_lat=d.get("adv_lat", 0.0),
            adv_lon=d.get("adv_lon", 0.0),
            out_path=d.get("out_path", ""),
            out_path_len=d.get("out_path_len", 0),
        )


# ---------------------------------------------------------------------------
# DeviceInfo
# ---------------------------------------------------------------------------

@dataclass
class DeviceInfo:
    """Radio device identification and configuration.

    Attributes:
        name:             Device display name.
        public_key:       Device public key (hex string).
        radio_freq:       Radio frequency in MHz.
        radio_sf:         LoRa spreading factor.
        radio_bw:         Bandwidth in kHz.
        tx_power:         Transmit power in dBm.
        adv_lat:          Advertised latitude.
        adv_lon:          Advertised longitude.
        firmware_version: Firmware version string.
    """

    name: str = ""
    public_key: str = ""
    radio_freq: float = 0.0
    radio_sf: int = 0
    radio_bw: float = 0.0
    tx_power: int = 0
    adv_lat: float = 0.0
    adv_lon: float = 0.0
    firmware_version: str = ""


# ---------------------------------------------------------------------------
# RxLogEntry
# ---------------------------------------------------------------------------

@dataclass
class RxLogEntry:
    """A single RX log entry from the radio.

    Attributes:
        time:         Formatted timestamp (HH:MM:SS).
        snr:          Signal-to-noise ratio (dB).
        rssi:         Received signal strength (dBm).
        payload_type: Packet type identifier.
        hops:         Number of hops (path_len from frame header).
        message_hash: Optional message hash for correlation with messages.
    """

    time: str
    snr: float = 0.0
    rssi: float = 0.0
    payload_type: str = "?"
    hops: int = 0
    message_hash: str = ""


# ---------------------------------------------------------------------------
# RouteNode
# ---------------------------------------------------------------------------

@dataclass
class RouteNode:
    """A node in a message route (sender, repeater or receiver).

    Attributes:
        name:   Display name (or ``'-'`` if unknown).
        lat:    Latitude (0.0 if unknown).
        lon:    Longitude (0.0 if unknown).
        type:   Node type (0=unknown, 1=CLI, 2=REP, 3=ROOM).
        pubkey: Public key or 2-char hash (hex string).
    """

    name: str
    lat: float = 0.0
    lon: float = 0.0
    type: int = 0
    pubkey: str = ""

    @property
    def has_location(self) -> bool:
        """True if the node has GPS coordinates."""
        return self.lat != 0 or self.lon != 0
