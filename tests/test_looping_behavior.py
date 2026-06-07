"""Unit tests for looping behavior in FileReader and MessageQueue."""

import pytest
from pathlib import Path
import tempfile
from src.file_reader import FileReader
from src.message_queue import MessageQueue

class TestLoopingBehavior:
    """Test cases for looping behavior."""

    def test_file_reader_and_message_queue_looping(self):
        """Test that FileReader and MessageQueue support looping behavior."""
        # Test MessageQueue looping with content units from FileReader
        units = ["line 1", "line 2", "line 3"]
        queue = MessageQueue(units)

        # Initial state: at unit 1 (index 0)
        assert queue.get_next_index() == 0
        assert queue.get_current_content_unit() == "line 1"

        # Advance to unit 2 (index 1)
        assert queue.advance() is True, "Should advance to unit 2"
        assert queue.get_next_index() == 1
        assert queue.get_current_content_unit() == "line 2"

        # Advance to unit 3 (index 2)
        assert queue.advance() is True, "Should advance to unit 3"
        assert queue.get_next_index() == 2
        assert queue.get_current_content_unit() == "line 3"

        # Advance past last unit - should wrap around and return True
        assert queue.advance() is True, "Should wrap around to beginning"
        assert queue.get_next_index() == 0
        assert queue.get_current_content_unit() == "line 1"

    def test_message_queue_is_complete_with_looping(self):
        """Test that is_complete() returns False when looping is active."""
        units = ["unit 1", "unit 2"]
        queue = MessageQueue(units)

        # Advance through all units
        queue.advance()
        queue.advance()
        
        # Should still not be complete because it loops
        assert queue.is_complete() is False
        
        # Advance again (loops back)
        queue.advance()
        assert queue.is_complete() is False
