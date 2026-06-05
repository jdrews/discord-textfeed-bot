"""Unit tests for message_queue module."""

import tempfile
from pathlib import Path
import pytest

from src.message_queue import MessageQueue, create_message_queue


class TestMessageQueue:
    """Test cases for MessageQueue class."""

    def test_init_with_content_units(self):
        """Test initializing with content units."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        assert queue.get_total_units() == 3
        assert queue.get_next_index() == 0

    def test_init_with_empty_list(self):
        """Test initializing with empty content units."""
        queue = MessageQueue([])

        assert queue.get_total_units() == 0
        assert queue.get_next_index() == 0

    def test_get_current_content_unit(self):
        """Test getting current content unit at index."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        assert queue.get_current_content_unit() == "unit 1"
        queue.advance()
        assert queue.get_current_content_unit() == "unit 2"
        queue.advance()
        assert queue.get_current_content_unit() == "unit 3"

    def test_advance(self):
        """Test advancing to next content unit."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        assert queue.advance() is True
        assert queue.get_next_index() == 1
        assert queue.advance() is True
        assert queue.get_next_index() == 2
        # After advancing past the last unit, advance returns False
        assert queue.advance() is False

    def test_reset_position(self):
        """Test resetting position to start."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        queue.advance()
        queue.advance()
        assert queue.get_next_index() == 2

        queue.reset_position()
        assert queue.get_next_index() == 0

    def test_get_remaining_units(self):
        """Test getting remaining units count."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        # Initially all 3 units remain (including current one)
        assert queue.get_remaining_units() == 3
        
        # After advancing once, 2 units remain
        queue.advance()
        assert queue.get_remaining_units() == 2
        
        # After advancing again, 1 unit remains
        queue.advance()
        assert queue.get_remaining_units() == 1
        
        # Advance past the last one - now at end, 0 remaining
        queue.advance()
        assert queue.get_remaining_units() == 0

    def test_get_progress(self):
        """Test getting progress percentage."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        # Before any advances, 0% complete
        assert queue.get_progress() == 0.0
        
        # After advancing once (1 of 3), ~33%
        queue.advance()
        assert queue.get_progress() == 33.33
        
        # After advancing twice (2 of 3), ~67%
        queue.advance()
        assert queue.get_progress() == 66.67
        
        # Advance past all units - now at end, 100% complete
        queue.advance()
        assert queue.get_progress() == 100.0

    def test_is_complete(self):
        """Test checking if all content has been sent."""
        units = ["unit 1", "unit 2"]
        queue = MessageQueue(units)

        # Not complete yet
        assert queue.is_complete() is False
        
        # Advance through both units (now at last unit, not complete yet)
        queue.advance()
        assert queue.is_complete() is False
        
        # After advancing past the last one, complete
        queue.advance()
        assert queue.is_complete() is True

    def test_set_content_units(self):
        """Test setting new content units."""
        queue = MessageQueue([])
        queue.set_content_units(["new 1", "new 2"])

        assert queue.get_total_units() == 2
        assert queue.get_next_index() == 0


class TestMessageQueueStatePersistence:
    """Test cases for state persistence."""

    def test_save_and_load_state(self):
        """Test saving and loading state from disk."""
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)

        # Advance to position 2
        queue.advance()
        queue.advance()
        assert queue.get_next_index() == 2

        # Save state
        saved = queue.save_state()
        assert saved is True

        # Verify file was created
        import os
        state_file = Path.cwd() / "discord-textfeed-bot.state.json"
        assert state_file.exists()

        # Create new queue and load state
        new_queue = MessageQueue(units)
        loaded = new_queue.load_state()
        assert loaded == 2


class TestMessageQueueCharacterLimit:
    """Test cases for character limit enforcement."""

    def test_enforce_character_limit_within_limit(self):
        """Test that content within limit is returned as-is."""
        unit = "This is a short message"
        result = MessageQueue([]).enforce_character_limit(unit)

        assert len(result) == 1
        assert result[0] == unit

    def test_enforce_character_limit_exceeds_limit(self):
        """Test that content exceeding limit is split."""
        # Create a string longer than 2000 chars
        long_unit = "A" * 2500
        result = MessageQueue([]).enforce_character_limit(long_unit)

        assert len(result) == 2  # Split into two chunks
        assert len(result[0]) <= 2000
        assert len(result[1]) <= 2000
        assert "".join(result) == long_unit


class TestCreateMessageQueue:
    """Test cases for create_message_queue function."""

    def test_create_with_units(self):
        """Test creating queue with units."""
        units = ["unit 1", "unit 2"]
        queue = create_message_queue(units)

        assert isinstance(queue, MessageQueue)
        assert queue.get_total_units() == 2


class TestModuleLevelFunctions:
    """Test cases for module-level convenience functions."""

    def test_get_next_index(self):
        """Test sync wrapper for get_next_index."""
        units = ["unit 1", "unit 2"]
        queue = MessageQueue(units)

        index = get_next_index(queue)
        assert index == 0

    def test_advance_queue(self):
        """Test sync wrapper for advance."""
        units = ["unit 1", "unit 2"]
        queue = MessageQueue(units)

        result = advance_queue(queue)
        assert result is True
        assert queue.get_next_index() == 1


# Import the module-level functions for testing
from src.message_queue import get_next_index, advance_queue
