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
from src.scheduler import SchedulerManager


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

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


class TextFeedBot:
    """Discord bot that reads lines from a text file and injects them into Discord."""

    def __init__(self):
        """Initialize the bot with default configuration."""
        self.config = None
        self._file_reader: Optional[FileReader] = None
        self._queue: Optional[MessageQueue] = None
        self._scheduler: Optional[SchedulerManager] = None
        self._discord_client: Optional[discord.Client] = None

    async def start(self) -> None:
        """Start the bot and all components."""
        # Load configuration
        self.config = load_config("config.yaml")

        # Set up logging
        setup_logging(self.config)
        logger = logging.getLogger(__name__)
        logger.info("Bot starting...")

        try:
            # Initialize Discord client with proper intents
            intents = discord.Intents.default()
            intents.message_content = True  # Required for reading messages if needed
            self._discord_client = discord.Client(intents=intents)

            # Start file reader and message queue
            await self._setup_file_reader(logger)

            # Validate channel exists before starting scheduler
            await self._validate_channel(logger)

            # Start scheduler
            await self._start_scheduler(logger, self.config)

            # Run the bot
            logger.info(f"Connecting to Discord...")
            await self._discord_client.start(get_discord_token())
            logger.info("Connected to Discord. Starting message injection.")

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
            logger.info(f"Channel validated: {self.config.discord_channel_id}")
        except discord.NotFound:
            logging.error(
                f"Invalid channel ID: {self.config.discord_channel_id}. "
                "Channel not found on Discord server."
            )
            raise ValueError(
                f"Invalid channel ID: {self.config.discord_channel_id}. "
                "Channel not found. Please verify the channel ID is correct."
            )
        except discord.Forbidden:
            logging.error(
                f"Forbidden access to channel: {self.config.discord_channel_id}"
            )
            raise ValueError(
                f"Bot does not have permission to access channel: "
                f"{self.config.discord_channel_id}. Please verify bot permissions."
            )
        except Exception as e:
            logging.error(
                f"Error validating channel: {e}"
            )
            raise ValueError(
                f"Invalid channel ID: {self.config.discord_channel_id}. "
                f"Error: {e}"
            )

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

    def __init__(self):
        """Initialize the bot runner."""
        self.bot = TextFeedBot()
        self._running = False

    async def run(self) -> None:
        """Run the bot with signal handling for graceful shutdown."""
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
            await self.bot.start()
        except Exception as e:
            logging.error(f"Bot error during run: {e}")
            raise
        finally:
            if self._running:
                await self.bot.stop()


async def main():
    """Main entry point for the bot."""
    runner = BotRunner()
    await runner.run()


def run_bot():
    """Entry point that handles signal handling.

    This function can be called directly from command line or as a module.
    """
    asyncio.run(main())


if __name__ == "__main__":
    run_bot()
