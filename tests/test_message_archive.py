"""
Unit tests for MessageArchive.

Tests cover:
- Message and RxLog archiving
- Batch write behavior
- Retention cleanup
- Thread safety
- JSON serialization
"""

import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from meshcore_gui.core.models import Message, RxLogEntry
from meshcore_gui.services.message_archive import MessageArchive, ARCHIVE_DIR


class TestMessageArchive(unittest.TestCase):
    """Test cases for MessageArchive class."""

    def setUp(self):
        """Create a temporary archive instance for testing."""
        self.test_address = "test:AA:BB:CC:DD:EE:FF"
        self.archive = MessageArchive(self.test_address)
        
        # Override archive directory to use temp dir
        self.temp_dir = tempfile.mkdtemp()
        self.archive._messages_path = Path(self.temp_dir) / "test_messages.json"
        self.archive._rxlog_path = Path(self.temp_dir) / "test_rxlog.json"

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # Message archiving tests
    # ------------------------------------------------------------------

    def test_add_message_single(self):
        """Test adding a single message."""
        msg = Message(
            time="12:34:56",
            sender="PE1HVH",
            text="Test message",
            channel=0,
            direction="in",
            snr=8.5,
            path_len=2,
            sender_pubkey="abc123",
            path_hashes=["a1", "b2"],
            message_hash="def456",
        )
        
        self.archive.add_message(msg)
        self.archive.flush()
        
        # Verify file was created
        self.assertTrue(self.archive._messages_path.exists())
        
        # Verify content
        data = json.loads(self.archive._messages_path.read_text())
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["sender"], "PE1HVH")
        self.assertEqual(data["messages"][0]["text"], "Test message")

    def test_add_message_batch(self):
        """Test batch write behavior (flush after N messages)."""
        # Add messages below batch threshold
        for i in range(5):
            msg = Message(
                time=f"12:34:{i:02d}",
                sender=f"User{i}",
                text=f"Message {i}",
                channel=0,
                direction="in",
            )
            self.archive.add_message(msg)
        
        # File should NOT exist yet (batch size = 10)
        self.assertFalse(self.archive._messages_path.exists())
        
        # Add more to trigger batch write
        for i in range(5, 12):
            msg = Message(
                time=f"12:34:{i:02d}",
                sender=f"User{i}",
                text=f"Message {i}",
                channel=0,
                direction="in",
            )
            self.archive.add_message(msg)
        
        # File should exist now (>= 10 messages)
        self.assertTrue(self.archive._messages_path.exists())
        
        # Verify all messages were written
        data = json.loads(self.archive._messages_path.read_text())
        # First batch of 10 was written, 2 still in buffer
        self.assertGreaterEqual(len(data["messages"]), 10)

    def test_manual_flush(self):
        """Test manual flush of pending messages."""
        msg = Message(
            time="12:34:56",
            sender="PE1HVH",
            text="Test",
            channel=0,
            direction="in",
        )
        
        self.archive.add_message(msg)
        self.assertFalse(self.archive._messages_path.exists())
        
        # Manual flush
        self.archive.flush()
        self.assertTrue(self.archive._messages_path.exists())
        
        data = json.loads(self.archive._messages_path.read_text())
        self.assertEqual(len(data["messages"]), 1)

    # ------------------------------------------------------------------
    # RxLog archiving tests
    # ------------------------------------------------------------------

    def test_add_rxlog(self):
        """Test adding RX log entries."""
        entry = RxLogEntry(
            time="12:34:56",
            snr=8.5,
            rssi=-95.0,
            payload_type="MSG",
            hops=2,
            message_hash="abc123",
        )
        
        self.archive.add_rx_log(entry)
        self.archive.flush()
        
        # Verify file was created
        self.assertTrue(self.archive._rxlog_path.exists())
        
        # Verify content
        data = json.loads(self.archive._rxlog_path.read_text())
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["entries"][0]["snr"], 8.5)
        self.assertEqual(data["entries"][0]["payload_type"], "MSG")
        self.assertEqual(data["entries"][0]["message_hash"], "abc123")

    # ------------------------------------------------------------------
    # Retention tests
    # ------------------------------------------------------------------

    def test_cleanup_old_messages(self):
        """Test cleanup removes messages older than retention period."""
        # Create archive with old and new messages
        now = datetime.now(timezone.utc)
        old_timestamp = (now - timedelta(days=35)).isoformat()
        new_timestamp = now.isoformat()
        
        data = {
            "version": 1,
            "address": self.test_address,
            "last_updated": now.isoformat(),
            "messages": [
                {
                    "time": "12:00:00",
                    "timestamp_utc": old_timestamp,
                    "sender": "Old",
                    "text": "Old message",
                    "channel": 0,
                    "direction": "in",
                },
                {
                    "time": "12:30:00",
                    "timestamp_utc": new_timestamp,
                    "sender": "New",
                    "text": "New message",
                    "channel": 0,
                    "direction": "in",
                },
            ],
        }
        
        self.archive._messages_path.write_text(json.dumps(data))
        self.archive._total_messages = 2
        
        # Run cleanup (MESSAGE_RETENTION_DAYS = 30 by default)
        self.archive.cleanup_old_data()
        
        # Verify old message was removed
        data = json.loads(self.archive._messages_path.read_text())
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["sender"], "New")

    def test_cleanup_old_rxlog(self):
        """Test cleanup removes RX log entries older than retention period."""
        now = datetime.now(timezone.utc)
        old_timestamp = (now - timedelta(days=10)).isoformat()
        new_timestamp = now.isoformat()
        
        data = {
            "version": 1,
            "address": self.test_address,
            "last_updated": now.isoformat(),
            "entries": [
                {
                    "time": "12:00:00",
                    "timestamp_utc": old_timestamp,
                    "snr": 5.0,
                    "rssi": -100.0,
                    "payload_type": "OLD",
                    "hops": 1,
                    "message_hash": "old123",
                },
                {
                    "time": "12:30:00",
                    "timestamp_utc": new_timestamp,
                    "snr": 8.0,
                    "rssi": -90.0,
                    "payload_type": "NEW",
                    "hops": 2,
                    "message_hash": "new456",
                },
            ],
        }
        
        self.archive._rxlog_path.write_text(json.dumps(data))
        self.archive._total_rxlog = 2
        
        # Run cleanup (RXLOG_RETENTION_DAYS = 7 by default)
        self.archive.cleanup_old_data()
        
        # Verify old entry was removed
        data = json.loads(self.archive._rxlog_path.read_text())
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["entries"][0]["payload_type"], "NEW")
        self.assertEqual(data["entries"][0]["message_hash"], "new456")

    # ------------------------------------------------------------------
    # Stats tests
    # ------------------------------------------------------------------

    def test_get_stats(self):
        """Test archive statistics."""
        # Add some messages
        for i in range(3):
            msg = Message(
                time=f"12:34:{i:02d}",
                sender=f"User{i}",
                text=f"Message {i}",
                channel=0,
                direction="in",
            )
            self.archive.add_message(msg)
        
        # Add some rxlog entries
        for i in range(2):
            entry = RxLogEntry(
                time=f"12:34:{i:02d}",
                snr=8.0 + i,
                rssi=-95.0,
                payload_type="MSG",
                hops=i,
            )
            self.archive.add_rx_log(entry)
        
        stats = self.archive.get_stats()
        
        self.assertEqual(stats["pending_messages"], 3)
        self.assertEqual(stats["pending_rxlog"], 2)
        self.assertEqual(stats["total_messages"], 0)  # Not flushed yet
        self.assertEqual(stats["total_rxlog"], 0)
        
        # After flush
        self.archive.flush()
        stats = self.archive.get_stats()
        
        self.assertEqual(stats["pending_messages"], 0)
        self.assertEqual(stats["pending_rxlog"], 0)
        self.assertEqual(stats["total_messages"], 3)
        self.assertEqual(stats["total_rxlog"], 2)

    # ------------------------------------------------------------------
    # Thread safety tests
    # ------------------------------------------------------------------

    def test_concurrent_writes(self):
        """Test thread-safe concurrent message additions."""
        num_threads = 5
        messages_per_thread = 20
        
        def add_messages(thread_id):
            for i in range(messages_per_thread):
                msg = Message(
                    time=f"12:34:{i:02d}",
                    sender=f"Thread{thread_id}",
                    text=f"Message {i}",
                    channel=0,
                    direction="in",
                )
                self.archive.add_message(msg)
        
        threads = []
        for tid in range(num_threads):
            t = threading.Thread(target=add_messages, args=(tid,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        self.archive.flush()
        
        # Verify all messages were written
        data = json.loads(self.archive._messages_path.read_text())
        expected_total = num_threads * messages_per_thread
        self.assertEqual(len(data["messages"]), expected_total)


if __name__ == "__main__":
    unittest.main()
