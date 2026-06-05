"""Main Discord bot entry point with initialization and lifecycle management."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import discord
from discord.errors import (
    DiscordServerError,
    Forbidden,
    HTTPException,
)

from src.config_loader import load_config, get_discord_token
from src.file_reader import FileReader
from src.message_queue import MessageQueue
from src.scheduler import SchedulerManager, set_discord_client


# Configure logging
def setup_logging(config):
    """Set up debug logging based on configuration.

    Args:
        config: Configuration object with log_level and log_file settings.
    """
    log_level = getattr(logging, config.log_level.upper(), logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    log_path = Path(config.log_file).parent
    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger and configure handlers (don't use basicConfig to avoid resetting)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    file_handler = logging.FileHandler(config.log_file)
    file_handler.setLevel(log_level)
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(log_level)


class TextFeedBot:
    """Discord bot that reads lines from a text file and injects them into Discord."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the bot with default configuration.
        
        Args:
            config_path: Path to the configuration file (e.g., 'config.test.yaml').
        """
        self.config = None
        self._file_reader: Optional[FileReader] = None
        self._queue: Optional[MessageQueue] = None
        self._scheduler: Optional[SchedulerManager] = None
        self._discord_client: Optional[discord.Client] = None

    async def start(self, config_path: str = "config.yaml") -> None:
        """Start the bot and all components.
        
        Args:
            config_path: Path to the configuration file.
        """
        # Load configuration
        self.config = load_config(config_path)

        # Set up logging
        setup_logging(self.config)
        logger = logging.getLogger(__name__)
        logger.info("Bot starting...")

        try:
            # Initialize Discord client with minimal intents (this bot only sends messages)
            intents = discord.Intents()
            # Note: message_content is disabled - this bot doesn't read messages, only sends them
            self._discord_client = discord.Client(intents=intents)

            # Set the global discord client for scheduler to use
            set_discord_client(self._discord_client)

            # Start file reader and message queue
            await self._setup_file_reader(logger)

            # Run the bot (connects first, then we validate channel after connection)
            logger.info(f"Connecting to Discord...")
            
            async def run_client():
                await self._discord_client.start(get_discord_token())
                logger.info("Discord client connected.")
            
            asyncio.create_task(run_client())
            
            # Wait for the client to be fully ready before proceeding (with timeout)
            try:
                await asyncio.wait_for(asyncio.sleep(30), timeout=30)
            except asyncio.TimeoutError:
                pass
            
            logger.info("Connected to Discord.")

            # Validate channel exists now that we're connected
            await self._validate_channel(logger)
            logger.info("Channel validated successfully")

            # Start scheduler after validation
            self._scheduler = SchedulerManager(
                interval_seconds=self.config.interval_seconds,
                randomization_seconds=self.config.randomization_seconds
            )
            
            self._scheduler.set_queue(self._queue)
            await self._scheduler.start()
            logger.info("Scheduler started successfully")

            # Keep the bot running - create a task that stays alive
            logger.info("Bot is now running. Press Ctrl+C to stop.")
            await asyncio.sleep(float('inf'))  # Keep event loop running

        except Exception as e:
            logging.error(f"Bot startup failed: {e}")
            raise

    async def _setup_file_reader(self, logger) -> None:
        """Set up file reader and message queue."""
        source_path = self.config.source_file_path
        
        # Check if source file exists
        if not source_path.exists():
            logging.error(f"Source file not found: {source_path}")
            raise FileNotFoundError(f"Source file does not exist: {source_path}")

        # Read source file
        lines = FileReader(source_path).read(
            skip_header=self.config.skip_header,
            skip_footer=self.config.skip_footer,
            start_line=self.config.start_line,
            end_line=self.config.end_line,
        )

        # Group by injection mode
        content_units = self._group_content(lines)

        # Create message queue
        self._queue = MessageQueue(content_units)

        # Log file read status (without exposing content)
        total_units = len(content_units)
        logger.info(f"Source file read: {total_units} content units available")

    def _group_content(self, lines):
        """Group lines based on injection mode.

        Args:
            lines: List of raw lines from the source file.

        Returns:
            List of content units ready for injection.
        """
        injection_mode = self.config.injection_mode
        
        if injection_mode == "line":
            return list(lines)
        elif injection_mode == "paragraph":
            return FileReader._group_as_paragraphs(lines)
        elif injection_mode == "character_scene":
            return FileReader._group_as_character_scenes(lines)
        else:
            raise ValueError(
                f"Invalid injection_mode: {injection_mode}. "
                "Must be 'line', 'paragraph', or 'character_scene'."
            )

    async def _validate_channel(self, logger) -> None:
        """Validate that the target Discord channel exists.

        Args:
            logger: Logger instance for logging events.
        
        Raises:
            ValueError: If channel validation fails.
        """
        if self._discord_client is None:
            return  # Will validate after connection
        
        try:
            await self._discord_client.fetch_channel(self.config.discord_channel_id)
            logger.info("Channel validated successfully")
        except discord.NotFound:
            logging.error(
                "Invalid channel ID. Channel not found on Discord server."
            )
            raise ValueError(
                "Invalid channel ID. Channel not found. Please verify the channel ID is correct."
            )
        except discord.Forbidden:
            logging.error("Forbidden access to channel")
            raise ValueError(
                "Bot does not have permission to access channel. "
                "Please verify bot permissions."
            )
        except Exception as e:
            logging.error(f"Error validating channel: {e}")
            raise ValueError(f"Invalid channel ID. Error: {e}")

    async def _start_scheduler(self, logger, config) -> None:
        """Start the injection scheduler."""
        interval_seconds = config.interval_seconds
        randomization_seconds = config.randomization_seconds

        self._scheduler = SchedulerManager(
            interval_seconds=interval_seconds,
            randomization_seconds=randomization_seconds
        )
        
        await self._scheduler.set_queue(self._queue)
        await self._scheduler.start()
        
        logger.info(f"Scheduler started: interval={interval_seconds}s, "
                   f"randomization={randomization_seconds}s")

    async def stop(self) -> None:
        """Stop the bot and all components gracefully."""
        # Stop scheduler
        if self._scheduler:
            await self._scheduler.stop()

        # Save queue state before shutdown
        if self._queue:
            self._queue.save_state()

        # Close Discord client
        if self._discord_client:
            await self._discord_client.close()


class BotRunner:
    """Manages bot lifecycle with signal handling for graceful shutdown."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the bot runner.
        
        Args:
            config_path: Path to the configuration file.
        """
        self.bot = TextFeedBot(config_path)
        self._running = False

    async def run(self, config_path: str = "config.yaml") -> None:
        """Run the bot with signal handling for graceful shutdown.
        
        Args:
            config_path: Path to the configuration file (overrides __init__ value).
        """
        # Set up signal handlers
        loop = asyncio.get_event_loop()

        def signal_handler():
            """Handle shutdown signals."""
            if self._running:
                logging.info("Shutdown signal received. Stopping bot...")
                asyncio.create_task(self.bot.stop())
                sys.exit(0)

        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        try:
            self._running = True
            await self.bot.start(config_path)
        except Exception as e:
            logging.error(f"Bot error during run: {e}")
            raise
        finally:
            if self._running:
                await self.bot.stop()


async def main(config_path: str = "config.yaml"):
    """Main entry point for the bot.

    Args:
        config_path: Path to the configuration file.
    """
    runner = BotRunner(config_path)
    await runner.run(config_path)


def run_bot(config_path: str = "config.yaml"):
    """Entry point that handles signal handling.

    Args:
        config_path: Path to the configuration file.

    This function can be called directly from command line or as a module.
    """
    asyncio.run(main(config_path))


if __name__ == "__main__":
    run_bot()
