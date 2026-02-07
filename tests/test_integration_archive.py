"""
Integration tests for SharedData + MessageArchive.

Tests the complete flow from message reception to persistent storage.
"""

import json
import tempfile
import unittest
from pathlib import Path

from meshcore_gui.core.models import Message, RxLogEntry
from meshcore_gui.core.shared_data import SharedData


class TestSharedDataArchiveIntegration(unittest.TestCase):
    """Integration tests for SharedData with MessageArchive."""

    def setUp(self):
        """Create SharedData instance with archive."""
        self.test_address = "test:AA:BB:CC:DD:EE:FF"
        self.shared = SharedData(self.test_address)
        
        # Override archive paths to use temp directory
        self.temp_dir = tempfile.mkdtemp()
        if self.shared.archive:
            self.shared.archive._messages_path = Path(self.temp_dir) / "test_messages.json"
            self.shared.archive._rxlog_path = Path(self.temp_dir) / "test_rxlog.json"

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # Message flow tests
    # ------------------------------------------------------------------

    def test_message_flow_to_archive(self):
        """Test message flows from SharedData to archive."""
        msg = Message(
            time="12:34:56",
            sender="PE1HVH",
            text="Test message",
            channel=0,
            direction="in",
            snr=8.5,
        )
        
        # Add message via SharedData
        self.shared.add_message(msg)
        
        # Verify message is in SharedData
        snapshot = self.shared.get_snapshot()
        self.assertEqual(len(snapshot["messages"]), 1)
        self.assertEqual(snapshot["messages"][0].sender, "PE1HVH")
        
        # Flush archive
        if self.shared.archive:
            self.shared.archive.flush()
            
            # Verify message is in archive
            self.assertTrue(self.shared.archive._messages_path.exists())
            data = json.loads(self.shared.archive._messages_path.read_text())
            self.assertEqual(len(data["messages"]), 1)
            self.assertEqual(data["messages"][0]["sender"], "PE1HVH")

    def test_rxlog_flow_to_archive(self):
        """Test RX log entry flows from SharedData to archive."""
        entry = RxLogEntry(
            time="12:34:56",
            snr=8.5,
            rssi=-95.0,
            payload_type="MSG",
            hops=2,
            message_hash="test123",
        )
        
        # Add via SharedData
        self.shared.add_rx_log(entry)
        
        # Verify in SharedData
        snapshot = self.shared.get_snapshot()
        self.assertEqual(len(snapshot["rx_log"]), 1)
        self.assertEqual(snapshot["rx_log"][0].snr, 8.5)
        self.assertEqual(snapshot["rx_log"][0].message_hash, "test123")
        
        # Flush archive
        if self.shared.archive:
            self.shared.archive.flush()
            
            # Verify in archive
            self.assertTrue(self.shared.archive._rxlog_path.exists())
            data = json.loads(self.shared.archive._rxlog_path.read_text())
            self.assertEqual(len(data["entries"]), 1)
            self.assertEqual(data["entries"][0]["snr"], 8.5)
            self.assertEqual(data["entries"][0]["message_hash"], "test123")

    def test_shareddata_buffer_limit(self):
        """Test SharedData maintains buffer limit while archiving all."""
        # Add 150 messages (SharedData limit is 100)
        for i in range(150):
            msg = Message(
                time=f"12:34:{i:02d}",
                sender=f"User{i}",
                text=f"Message {i}",
                channel=0,
                direction="in",
            )
            self.shared.add_message(msg)
        
        # Verify SharedData has only 100
        snapshot = self.shared.get_snapshot()
        self.assertEqual(len(snapshot["messages"]), 100)
        # First message should be #50 (oldest 50 were dropped)
        self.assertEqual(snapshot["messages"][0].sender, "User50")
        
        # Flush and verify archive has all 150
        if self.shared.archive:
            self.shared.archive.flush()
            data = json.loads(self.shared.archive._messages_path.read_text())
            self.assertEqual(len(data["messages"]), 150)
            self.assertEqual(data["messages"][0]["sender"], "User0")

    # ------------------------------------------------------------------
    # Archive stats tests
    # ------------------------------------------------------------------

    def test_archive_stats_via_shareddata(self):
        """Test getting archive stats through SharedData."""
        # Add messages
        for i in range(5):
            msg = Message(
                time=f"12:34:{i:02d}",
                sender=f"User{i}",
                text=f"Message {i}",
                channel=0,
                direction="in",
            )
            self.shared.add_message(msg)
        
        # Get stats
        stats = self.shared.get_archive_stats()
        if stats:
            self.assertEqual(stats["pending_messages"], 5)
            
            # After flush
            self.shared.archive.flush()
            stats = self.shared.get_archive_stats()
            self.assertEqual(stats["total_messages"], 5)
            self.assertEqual(stats["pending_messages"], 0)

    # ------------------------------------------------------------------
    # Backward compatibility tests
    # ------------------------------------------------------------------

    def test_shareddata_without_address(self):
        """Test SharedData works without address (no archive)."""
        shared_no_archive = SharedData()  # No address
        
        # Should work without archive
        msg = Message(
            time="12:34:56",
            sender="PE1HVH",
            text="Test",
            channel=0,
            direction="in",
        )
        
        shared_no_archive.add_message(msg)
        
        # Verify message is in SharedData
        snapshot = shared_no_archive.get_snapshot()
        self.assertEqual(len(snapshot["messages"]), 1)
        
        # Archive should be None
        self.assertIsNone(shared_no_archive.archive)
        self.assertIsNone(shared_no_archive.get_archive_stats())

    def test_persistence_across_restart(self):
        """Test messages persist across SharedData restart."""
        # Add messages
        for i in range(5):
            msg = Message(
                time=f"12:34:{i:02d}",
                sender=f"User{i}",
                text=f"Message {i}",
                channel=0,
                direction="in",
            )
            self.shared.add_message(msg)
        
        if self.shared.archive:
            self.shared.archive.flush()
            messages_path = self.shared.archive._messages_path
            
            # Create new SharedData instance (simulating restart)
            shared2 = SharedData(self.test_address)
            shared2.archive._messages_path = messages_path
            shared2.archive._load_archives()
            
            # Verify messages were loaded
            stats = shared2.get_archive_stats()
            self.assertEqual(stats["total_messages"], 5)

    def test_append_on_restart_not_overwrite(self):
        """Test that existing archive is appended to, not overwritten on restart."""
        # First session: add and flush 3 messages
        for i in range(3):
            msg = Message(
                time=f"12:00:{i:02d}",
                sender=f"Session1_User{i}",
                text=f"Session 1 Message {i}",
                channel=0,
                direction="in",
            )
            self.shared.add_message(msg)
        
        if self.shared.archive:
            self.shared.archive.flush()
            messages_path = self.shared.archive._messages_path
            
            # Verify first session data
            data = json.loads(messages_path.read_text())
            self.assertEqual(len(data["messages"]), 3)
            self.assertEqual(data["messages"][0]["sender"], "Session1_User0")
            
            # Simulate restart: create new SharedData and archive
            shared2 = SharedData(self.test_address)
            shared2.archive._messages_path = messages_path
            shared2.archive._rxlog_path = self.shared.archive._rxlog_path
            shared2.archive._load_archives()
            
            # Second session: add and flush 2 more messages
            for i in range(2):
                msg = Message(
                    time=f"13:00:{i:02d}",
                    sender=f"Session2_User{i}",
                    text=f"Session 2 Message {i}",
                    channel=0,
                    direction="in",
                )
                shared2.add_message(msg)
            
            shared2.archive.flush()
            
            # Verify BOTH sessions' data exists (appended, not overwritten)
            data = json.loads(messages_path.read_text())
            self.assertEqual(len(data["messages"]), 5)
            
            # Verify session 1 messages still exist
            session1_messages = [m for m in data["messages"] if "Session1" in m["sender"]]
            self.assertEqual(len(session1_messages), 3)
            
            # Verify session 2 messages were added
            session2_messages = [m for m in data["messages"] if "Session2" in m["sender"]]
            self.assertEqual(len(session2_messages), 2)


if __name__ == "__main__":
    unittest.main()
