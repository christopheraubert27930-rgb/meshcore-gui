"""
BLE event callbacks for MeshCore GUI.

Handles ``CHANNEL_MSG_RECV``, ``CONTACT_MSG_RECV`` and ``RX_LOG_DATA``
events from the MeshCore library.  Extracted from ``BLEWorker`` so the
worker only deals with connection lifecycle.
"""

from datetime import datetime
from typing import Dict, Optional

from meshcore_gui.config import debug_print
from meshcore_gui.core.models import Message, RxLogEntry
from meshcore_gui.core.protocols import SharedDataWriter
from meshcore_gui.ble.packet_decoder import PacketDecoder, PayloadType
from meshcore_gui.services.bot import MeshBot
from meshcore_gui.services.dedup import DualDeduplicator


class EventHandler:
    """Processes BLE events and writes results to shared data.

    Args:
        shared:  SharedDataWriter for storing messages and RX log.
        decoder: PacketDecoder for raw LoRa packet decryption.
        dedup:   DualDeduplicator for message deduplication.
        bot:     MeshBot for auto-reply logic.
    """

    def __init__(
        self,
        shared: SharedDataWriter,
        decoder: PacketDecoder,
        dedup: DualDeduplicator,
        bot: MeshBot,
    ) -> None:
        self._shared = shared
        self._decoder = decoder
        self._dedup = dedup
        self._bot = bot

    # ------------------------------------------------------------------
    # RX_LOG_DATA — the single source of truth for path info
    # ------------------------------------------------------------------

    def on_rx_log(self, event) -> None:
        """Handle RX log data events."""
        payload = event.payload

        # Extract basic RX log info
        time_str = datetime.now().strftime('%H:%M:%S')
        snr = payload.get('snr', 0)
        rssi = payload.get('rssi', 0)
        payload_type = payload.get('payload_type', '?')
        hops = payload.get('path_len', 0)
        
        # Try to decode payload to get message_hash
        message_hash = ""
        payload_hex = payload.get('payload', '')
        if payload_hex:
            decoded = self._decoder.decode(payload_hex)
            if decoded is not None:
                message_hash = decoded.message_hash
                
                # Process decoded message if it's a group text
                if decoded.payload_type == PayloadType.GroupText and decoded.is_decrypted:
                    self._dedup.mark_hash(decoded.message_hash)
                    self._dedup.mark_content(
                        decoded.sender, decoded.channel_idx, decoded.text,
                    )

                    sender_pubkey = ''
                    if decoded.sender:
                        match = self._shared.get_contact_by_name(decoded.sender)
                        if match:
                            sender_pubkey, _contact = match

                    snr_msg = self._extract_snr(payload)

                    self._shared.add_message(Message(
                        time=time_str,
                        sender=decoded.sender,
                        text=decoded.text,
                        channel=decoded.channel_idx,
                        direction='in',
                        snr=snr_msg,
                        path_len=decoded.path_length,
                        sender_pubkey=sender_pubkey,
                        path_hashes=decoded.path_hashes,
                        message_hash=decoded.message_hash,
                    ))

                    debug_print(
                        f"RX_LOG → message: hash={decoded.message_hash}, "
                        f"sender={decoded.sender!r}, ch={decoded.channel_idx}, "
                        f"path={decoded.path_hashes}"
                    )

                    self._bot.check_and_reply(
                        sender=decoded.sender,
                        text=decoded.text,
                        channel_idx=decoded.channel_idx,
                        snr=snr_msg,
                        path_len=decoded.path_length,
                        path_hashes=decoded.path_hashes,
                    )
        
        # Add RX log entry with message_hash (if available)
        self._shared.add_rx_log(RxLogEntry(
            time=time_str,
            snr=snr,
            rssi=rssi,
            payload_type=payload_type,
            hops=hops,
            message_hash=message_hash,
        ))

    # ------------------------------------------------------------------
    # CHANNEL_MSG_RECV — fallback when RX_LOG decode missed it
    # ------------------------------------------------------------------

    def on_channel_msg(self, event) -> None:
        """Handle channel message events."""
        payload = event.payload

        debug_print(f"Channel msg payload keys: {list(payload.keys())}")

        # Dedup via hash
        msg_hash = payload.get('message_hash', '')
        if msg_hash and self._dedup.is_hash_seen(msg_hash):
            debug_print(f"Channel msg suppressed (hash): {msg_hash}")
            return

        # Parse sender from "SenderName: message body" format
        raw_text = payload.get('text', '')
        sender, msg_text = '', raw_text
        if ': ' in raw_text:
            name_part, body_part = raw_text.split(': ', 1)
            sender = name_part.strip()
            msg_text = body_part
        elif raw_text:
            msg_text = raw_text

        # Dedup via content
        ch_idx = payload.get('channel_idx')
        if self._dedup.is_content_seen(sender, ch_idx, msg_text):
            debug_print(f"Channel msg suppressed (content): {sender!r}")
            return

        debug_print(
            f"Channel msg (fallback): sender={sender!r}, "
            f"text={msg_text[:40]!r}"
        )

        sender_pubkey = ''
        if sender:
            match = self._shared.get_contact_by_name(sender)
            if match:
                sender_pubkey, _contact = match

        snr = self._extract_snr(payload)

        self._shared.add_message(Message(
            time=datetime.now().strftime('%H:%M:%S'),
            sender=sender,
            text=msg_text,
            channel=ch_idx,
            direction='in',
            snr=snr,
            path_len=payload.get('path_len', 0),
            sender_pubkey=sender_pubkey,
            path_hashes=[],
            message_hash=msg_hash,
        ))

        self._bot.check_and_reply(
            sender=sender,
            text=msg_text,
            channel_idx=ch_idx,
            snr=snr,
            path_len=payload.get('path_len', 0),
        )

    # ------------------------------------------------------------------
    # CONTACT_MSG_RECV — DMs
    # ------------------------------------------------------------------

    def on_contact_msg(self, event) -> None:
        """Handle direct message and room message events.

        Room Server messages arrive as ``CONTACT_MSG_RECV`` with
        ``txt_type == 2``.  The ``pubkey_prefix`` is the Room Server's
        key and the ``signature`` field contains the original author's
        pubkey prefix.  We resolve the author name from ``signature``
        so the UI shows who actually wrote the message.
        """
        payload = event.payload
        pubkey = payload.get('pubkey_prefix', '')
        txt_type = payload.get('txt_type', 0)
        signature = payload.get('signature', '')

        debug_print(f"DM payload keys: {list(payload.keys())}")

        # --- Room Server message (txt_type 2) ---
        if txt_type == 2 and signature:
            # Resolve actual author from signature (author pubkey prefix)
            author = self._shared.get_contact_name_by_prefix(signature)
            if not author:
                author = signature[:8] if signature else '?'

            self._shared.add_message(Message(
                time=datetime.now().strftime('%H:%M:%S'),
                sender=author,
                text=payload.get('text', ''),
                channel=None,
                direction='in',
                snr=self._extract_snr(payload),
                path_len=payload.get('path_len', 0),
                sender_pubkey=pubkey,  # room pubkey → for panel filtering
            ))
            debug_print(
                f"Room msg from {author} (sig={signature}) "
                f"via room {pubkey[:12]}: "
                f"{payload.get('text', '')[:30]}"
            )
            return

        # --- Regular DM ---
        sender = ''
        if pubkey:
            sender = self._shared.get_contact_name_by_prefix(pubkey)
        if not sender:
            sender = pubkey[:8] if pubkey else ''

        self._shared.add_message(Message(
            time=datetime.now().strftime('%H:%M:%S'),
            sender=sender,
            text=payload.get('text', ''),
            channel=None,
            direction='in',
            snr=self._extract_snr(payload),
            path_len=payload.get('path_len', 0),
            sender_pubkey=pubkey,
        ))
        debug_print(f"DM received from {sender}: {payload.get('text', '')[:30]}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_snr(payload: Dict) -> Optional[float]:
        """Extract SNR from a payload dict (handles 'SNR' and 'snr' keys)."""
        raw = payload.get('SNR') or payload.get('snr')
        if raw is not None:
            try:
                return float(raw)
            except (ValueError, TypeError):
                pass
        return None
