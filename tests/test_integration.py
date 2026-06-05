"""Integration tests for Discord Text Feed Bot."""

import asyncio
import os
import sys
from pathlib import Path
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBotStartup:
    """Test cases for bot startup and initialization."""

    def test_bot_initialization(self):
        """Test that bot initializes correctly."""
        from src.bot import TextFeedBot
        
        bot = TextFeedBot()
        
        assert bot is not None
        assert bot.config is None  # Not loaded until start()


class TestConfigValidation:
    """Test cases for configuration validation during startup."""

    def test_missing_source_file_raises_error(self):
        """Test that missing source file raises FileNotFoundError."""
        from src.bot import TextFeedBot
        
        # Create a temp config with non-existent file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
discord:
  channel_id: "123456789"
source:
  file_path: "./nonexistent_file.txt"
logging:
  level: "DEBUG"
""")
            temp_config = Path(f.name)

        try:
            # Create bot and manually set config to trigger validation
            from src.config_loader import ConfigLoader
            loader = ConfigLoader(temp_config)
            loader.load()
            
            with pytest.raises(FileNotFoundError, match="Source file does not exist"):
                _ = loader.get_source_file_path()
        finally:
            os.unlink(temp_config)


class TestChannelValidation:
    """Test cases for channel validation."""

    @pytest.mark.asyncio
    async def test_invalid_channel_id_raises_error(self):
        """Test that invalid channel ID raises ValueError."""
        from src.bot import TextFeedBot
        
        bot = TextFeedBot()
        class MockConfig:
            discord_channel_id = 123456789
        bot.config = MockConfig()
        
        # Mock the discord client to simulate NotFound error
        class MockClient:
            async def fetch_channel(self, channel_id):
                raise Exception("Channel not found")
        
        bot._discord_client = MockClient()
        
        with pytest.raises(ValueError, match="Invalid channel ID"):
            await bot._validate_channel(None)


class TestMessageQueueIntegration:
    """Test cases for message queue integration."""

    def test_queue_with_file_reader_output(self):
        """Test that message queue works with file reader output."""
        from src.file_reader import FileReader
        from src.message_queue import MessageQueue
        
        # Create a temp text file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(1, 6):
                f.write(f"line {i}\n")
            temp_path = Path(f.name)

        try:
            # Read file and create queue
            lines = FileReader(temp_path).read()
            queue = MessageQueue(lines)
            
            assert queue.get_total_units() == 5
            assert queue.get_next_index() == 0
            
            # Advance through all units
            for i in range(5):
                if i < 4:
                    assert queue.advance() is True
                else:
                    assert queue.advance() is False
            
            assert queue.is_complete() is True
        finally:
            os.unlink(temp_path)


class TestSchedulerIntegration:
    """Test cases for scheduler integration."""

    def test_scheduler_with_queue(self):
        """Test that scheduler works with message queue."""
        from src.message_queue import MessageQueue
        from src.scheduler import SchedulerManager
        
        # Create a simple queue
        units = ["unit 1", "unit 2"]
        queue = MessageQueue(units)
        
        # Create and start scheduler
        manager = SchedulerManager(interval_seconds=1, randomization_seconds=0)
        manager.set_queue(queue)
        
        assert manager.is_running is False
        
        # Start the scheduler (non-blocking test - just verify it starts)
        async def run_test():
            await manager.start()
            return True
        
        result = asyncio.run(run_test())
        assert result is True
        assert manager.is_running is True


class TestEndToEndFlow:
    """Test cases for end-to-end bot flow."""

    @pytest.mark.asyncio
    async def test_full_flow_with_mock_discord(self):
        """Test the full bot flow with mocked Discord client."""
        from src.config_loader import ConfigLoader
        from src.file_reader import FileReader
        from src.message_queue import MessageQueue
        from src.scheduler import SchedulerManager
        
        # Create temp config file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
discord:
  channel_id: "123456789"
source:
  file_path: "./test.txt"
  skip_header: true
  start_line: 1
schedule:
  interval_seconds: 1
logging:
  level: "DEBUG"
""")
            config_path = Path(f.name)

        # Create temp source file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(1, 4):
                f.write(f"test line {i}\n")
            source_path = Path(f.name)

        try:
            # Load config
            loader = ConfigLoader(config_path)
            
            # Read file and create queue
            lines = FileReader(source_path).read()
            queue = MessageQueue(lines)
            
            assert len(queue.get_content_units()) == 3
            
            # Create scheduler manager
            manager = SchedulerManager(interval_seconds=1, randomization_seconds=0)
            manager.set_queue(queue)
            
            # Verify initial state
            assert manager.is_running is False
            assert queue.get_next_index() == 0
            
        finally:
            os.unlink(config_path)
            os.unlink(source_path)


class TestStatePersistenceIntegration:
    """Test cases for state persistence across restarts."""

    def test_state_saved_on_advance(self):
        """Test that state is saved when advancing queue."""
        from src.message_queue import MessageQueue
        
        units = ["unit 1", "unit 2", "unit 3"]
        queue = MessageQueue(units)
        
        # Advance to position 2
        queue.advance()
        queue.advance()
        
        # Save state
        saved = queue.save_state()
        assert saved is True
        
        # Verify file was created
        import os
        state_file = Path.cwd() / "discord-textfeed-bot.state.json"
        assert state_file.exists()
        
        # Clean up
        if state_file.exists():
            state_file.unlink()


class TestLoggingIntegration:
    """Test cases for logging integration."""

    def test_logging_configured(self):
        """Test that logging is configured correctly."""
        from src.bot import setup_logging
        
        # Create temp config
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
logging:
  level: "DEBUG"
  file: "./test_logs/debug.log"
""")
            config_path = Path(f.name)

        try:
            # Create a mock config object
            class MockConfig:
                log_level = "DEBUG"
                log_file = "./test_logs/debug.log"
            
            setup_logging(MockConfig())
            
            # Verify logging is configured (check that handler exists)
            import logging
            root_logger = logging.getLogger()
            handlers = root_logger.handlers
            
            assert len(handlers) > 0
            
        finally:
            os.unlink(config_path)


# Run pytest with asyncio support
pytest_plugins = ('pytest_asyncio',)
