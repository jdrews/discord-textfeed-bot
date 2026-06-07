"""Content queue management with persistence and wraparound support."""

import json
import threading
from pathlib import Path
from typing import List, Optional


class MessageQueue:
    """Thread-safe queue for managing content units to send to Discord.

    Provides thread-safe operations using locks for concurrent access.
    Supports state persistence across restarts and wraparound when reaching end of content.
    """

    STATE_FILE_SUFFIX = ".state.json"
    DEFAULT_STATE_FILE = "discord-textfeed-bot.state.json"
    DISCORD_MESSAGE_MAX_LENGTH = 2000

    def __init__(self, content_units: List[str]):
        """Initialize with list of content units (lines/paragraphs/scenes).

        Args:
            content_units: List of strings representing content units to send.
        """
        self._content_units: List[str] = content_units.copy() if content_units else []
        self._current_index: int = 0
        self._total_units: int = len(self._content_units)
        self._state_file_path: Optional[Path] = None
        self._lock: threading.Lock = threading.Lock()

    def _get_state_file_path(self, base_path: Path) -> Path:
        """Get the path to the state persistence file.

        Args:
            base_path: Base directory or filename for the state file.

        Returns:
            Path object pointing to the .state.json file.
        """
        if isinstance(base_path, str):
            return Path(base_path).with_suffix(self.STATE_FILE_SUFFIX)
        return (base_path.parent / f"{base_path.name}{self.STATE_FILE_SUFFIX}")

    def load_state(self, base_path: Optional[Path] = None) -> int:
        """Load saved state from disk.

        Args:
            base_path: Base path for the state file. If None, uses current working directory.

        Returns:
            The loaded index position, or 0 if no state found.
        """
        with self._lock:
            if self._total_units == 0:
                return 0

            if base_path is None:
                # Default to .state.json in current directory
                state_file = Path.cwd() / self.DEFAULT_STATE_FILE
            else:
                state_file = self._get_state_file_path(base_path)

            if not state_file.exists():
                return 0

            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    index = data.get("index", 0)
                    # Validate the loaded index is within bounds
                    if 0 <= index < self._total_units:
                        return index
            except (json.JSONDecodeError, IOError):
                pass

            return 0

    def save_state(self, base_path: Optional[Path] = None) -> bool:
        """Save current position to disk.

        Args:
            base_path: Base path for the state file. If None, uses current working directory.

        Returns:
            True if saved successfully, False otherwise.
        """
        with self._lock:
            if self._total_units == 0:
                return True

            if base_path is None:
                # Default to .state.json in current directory
                state_file = Path.cwd() / self.DEFAULT_STATE_FILE
            else:
                state_file = self._get_state_file_path(base_path)

            try:
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump({"index": self._current_index}, f)
                return True
            except IOError:
                return False

    def get_next_index(self) -> int:
        """Get index of next content unit to send (thread-safe).

        Returns:
            Zero-based index of the next content unit, or 0 if queue is empty.
        """
        with self._lock:
            if self._total_units == 0:
                return 0
            return self._current_index

    def get_current_content_unit(self) -> Optional[str]:
        """Get the current content unit at the current index (thread-safe).

        Returns:
            The content unit string, or None if queue is empty or out of bounds.
        """
        with self._lock:
            if self._total_units == 0 or self._current_index >= self._total_units:
                return None
            return self._content_units[self._current_index]

    def advance(self) -> bool:
        """Advance to the next content unit (thread-safe).
        
        Returns:
            True if advanced successfully, False if queue is empty.
        """
        with self._lock:
            if self._total_units == 0:
                return False
            
            # If we are at the last unit, wrap around to the beginning
            if self._current_index >= self._total_units - 1:
                self._current_index = 0
                return True
            
            # Move to next unit
            self._current_index += 1
            return True

    def reset_position(self) -> None:
        """Reset queue position to start."""
        with self._lock:
            self._current_index = 0

    def get_total_units(self) -> int:
        """Return total content units in queue.

        Returns:
            Number of content units available for injection.
        """
        return len(self._content_units)

    def get_remaining_units(self) -> int:
        """Get number of remaining units to send (thread-safe).

        Returns:
            Number of units from current position to end (inclusive).
        """
        with self._lock:
            if self._total_units == 0 or self._current_index >= self._total_units:
                return 0
            # Remaining = total - current_index (units yet to be sent, including current)
            remaining = self._total_units - self._current_index
            return max(1, remaining)

    def get_progress(self) -> float:
        """Get progress as a percentage (0.0 to 100.0).

        Returns:
            Progress percentage based on completed units vs total units.
        """
        with self._lock:
            if self._total_units == 0 or self._current_index >= self._total_units:
                return 100.0
            
            # Progress = current_index / total * 100 (units sent so far)
            progress = (self._current_index / self._total_units) * 100
            return round(progress, 2)

    def get_content_units(self) -> List[str]:
        """Get the list of content units in the queue (thread-safe).

        Returns:
            List of strings representing the content units.
        """
        with self._lock:
            return self._content_units.copy()

    def is_complete(self) -> bool:
        """Check if all content has been sent (thread-safe).
        
        Returns:
            True if all units have been completed/sent.
        """
        with self._lock:
            # Complete when the queue is empty
            return self._total_units == 0

    def set_content_units(self, units: List[str]) -> None:
        """Set new content units in the queue (thread-safe).

        Args:
            units: New list of content units to send.
        """
        with self._lock:
            self._content_units = units.copy() if units else []
            self._total_units = len(self._content_units)
            self._current_index = 0

    @staticmethod
    def enforce_character_limit(unit: str, max_length: int = DISCORD_MESSAGE_MAX_LENGTH) -> List[str]:
        """Enforce Discord's message length limit by splitting long content.

        Args:
            unit: The content unit string to check and potentially split.
            max_length: Maximum allowed characters (default: 2000).

        Returns:
            List of strings - either the original unit if within limit,
            or multiple shorter units that sum to the original length.
        """
        if len(unit) <= max_length:
            return [unit]

        # Split long content into chunks
        result = []
        start = 0
        while start < len(unit):
            end = min(start + max_length, len(unit))
            result.append(unit[start:end])
            start = end

        return result


def create_message_queue(content_units: List[str]) -> MessageQueue:
    """Create a new message queue with the given content units.

    Args:
        content_units: List of strings representing content units to send.

    Returns:
        A new MessageQueue instance.
    """
    return MessageQueue(content_units)


def get_next_index(queue: MessageQueue) -> int:
    """Get index of next content unit to send (thread-safe).

    Args:
        queue: The message queue instance.

    Returns:
        Zero-based index of the next content unit, or 0 if queue is empty.
    """
    return queue.get_next_index()


def get_current_content_unit(queue: MessageQueue) -> Optional[str]:
    """Get the current content unit at the current index (thread-safe).

    Args:
        queue: The message queue instance.

    Returns:
        The content unit string, or None if queue is empty or out of bounds.
    """
    return queue.get_current_content_unit()


def advance_queue(queue: MessageQueue) -> bool:
    """Advance to the next content unit (thread-safe).

    Args:
        queue: The message queue instance.

    Returns:
        True if advanced successfully, False if queue is empty.
    """
    return queue.advance()


def reset_queue_position(queue: MessageQueue) -> None:
    """Reset queue position to start (sync wrapper).

    Args:
        queue: The message queue instance.
    """
    queue.reset_position()


def get_total_units(queue: MessageQueue) -> int:
    """Return total content units in queue.

    Args:
        queue: The message queue instance.

    Returns:
            Number of content units available for injection.
    """
    return queue.get_total_units()


def get_remaining_units(queue: MessageQueue) -> int:
    """Get number of remaining units to send (thread-safe).

    Args:
        queue: The message queue instance.

    Returns:
            Number of units from current position to end (inclusive).
    """
    return queue.get_remaining_units()


def get_progress(queue: MessageQueue) -> float:
    """Get progress as a percentage (0.0 to 100.0).

    Args:
        queue: The message queue instance.

    Returns:
            Progress percentage based on current index vs total units.
    """
    return queue.get_progress()


def is_queue_complete(queue: MessageQueue) -> bool:
    """Check if all content has been sent (thread-safe).

    Args:
        queue: The message queue instance.

    Returns:
            True if current index is at or past the end of the queue.
    """
    return queue.is_complete()


def enforce_character_limit(unit: str, max_length: int = 2000) -> List[str]:
    """Enforce Discord's message length limit by splitting long content.

    Args:
        unit: The content unit string to check and potentially split.
        max_length: Maximum allowed characters (default: 2000).

    Returns:
        List of strings - either the original unit if within limit,
        or multiple shorter units that sum to the original length.
    """
    queue = MessageQueue([])
    return queue.enforce_character_limit(unit, max_length)
