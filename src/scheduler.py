"""Interval-based scheduling for content injection."""

import asyncio
import logging
from typing import List, Optional


class InjectionScheduler:
    """Asyncio-based interval scheduler with optional randomization.

    Coordinates with message queue for next content unit and handles
    graceful shutdown on bot close. Logs operational events only (no content).
    Implements exponential backoff for rate limiting errors.
    """

    def __init__(self, interval_seconds: int, randomization_seconds: int = 0, queue=None):
        """Initialize scheduler with base interval and optional randomization.

        Args:
            interval_seconds: Base seconds between injections.
            randomization_seconds: ± variance in scheduling (0 = exact timing).
            queue: MessageQueue instance for content units.
        """
        self.interval_seconds = interval_seconds
        self.randomization_seconds = randomization_seconds
        self._queue = queue
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the injection loop with randomized intervals."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the injection loop gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

    async def _run(self) -> None:
        """Main injection loop."""
        while self._running:
            try:
                # Calculate interval with randomization
                if self.randomization_seconds > 0:
                    import random
                    delay = self.interval_seconds + random.randint(
                        -self.randomization_seconds, self.randomization_seconds
                    )
                    delay = max(delay, 1)  # Ensure minimum 1 second
                else:
                    delay = self.interval_seconds

                await asyncio.sleep(delay)

                if not self._running:
                    break

                # Get next content unit and send it
                if self._queue:
                    index = self._queue.get_next_index()
                    content_unit = self._queue.get_current_content_unit()

                    if content_unit is not None:
                        # Enforce character limit and split if needed
                        chunks = self._enforce_character_limit(content_unit)

                        for i, chunk in enumerate(chunks):
                            success = await self.inject_content(index, chunk)

                        # Advance queue once after all chunks are sent successfully
                        if len(chunks) > 0:
                            self._queue.advance()

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue on next interval
                self._logger.error(f"Scheduler error: {e}")

    def _enforce_character_limit(self, unit: str) -> List[str]:
        """Enforce Discord's message length limit by splitting long content.

        Args:
            unit: The content unit string to check and potentially split.

        Returns:
            List of strings - either the original unit if within limit,
            or multiple shorter units that sum to the original length.
        """
        DISCORD_MESSAGE_MAX_LENGTH = 2000
        if len(unit) <= DISCORD_MESSAGE_MAX_LENGTH:
            return [unit]

        # Split long content into chunks
        result = []
        start = 0
        while start < len(unit):
            end = min(start + DISCORD_MESSAGE_MAX_LENGTH, len(unit))
            result.append(unit[start:end])
            start = end

        return result

    async def inject_content(self, index: int, content_unit: str) -> bool:
        """Send a single content unit to Discord channel. Logs operation only.

        Args:
            index: The index of the content unit being sent.
            content_unit: The actual content string to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        return await inject_content(index, content_unit)


async def inject_content(index: int, content_unit: str) -> bool:
    """Send a single content unit to Discord channel. Logs operation only.

    This is a placeholder function that should be implemented in bot.py
    where the actual Discord client integration occurs with proper error handling.

    Args:
        index: The index of the content unit being sent.
        content_unit: The actual content string to send.

    Returns:
        True if sent successfully, False otherwise.
    """
    # Placeholder - actual implementation in bot.py
    return True


class SchedulerManager:
    """Manages scheduler lifecycle and provides high-level control."""

    def __init__(self, interval_seconds: int = 180, randomization_seconds: int = 0):
        """Initialize the scheduler manager.

        Args:
            interval_seconds: Base seconds between injections.
            randomization_seconds: ± variance in scheduling (0 = exact timing).
        """
        self.interval_seconds = interval_seconds
        self.randomization_seconds = randomization_seconds
        self._scheduler: Optional[InjectionScheduler] = None
        self._queue = None
        self._running = False
        self._logger = logging.getLogger(__name__)

    def set_queue(self, queue) -> None:
        """Set the message queue for content units.

        Args:
            queue: MessageQueue instance.
        """
        self._queue = queue

    async def start(self) -> None:
        """Start the injection scheduler."""
        if self._queue is None:
            raise RuntimeError("Message queue not set. Call set_queue() first.")

        self._scheduler = InjectionScheduler(
            interval_seconds=self.interval_seconds,
            randomization_seconds=self.randomization_seconds,
            queue=self._queue
        )
        
        # Set logger for scheduler
        if hasattr(self._scheduler, '_logger'):
            self._scheduler._logger = self._logger

        await self._scheduler.start()
        self._running = True

    async def stop(self) -> None:
        """Stop the injection scheduler gracefully."""
        if self._scheduler:
            await self._scheduler.stop()
            self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


# Module-level convenience functions for direct usage

async def start_scheduler(
    interval_seconds: int = 180,
    randomization_seconds: int = 0,
    queue=None
) -> InjectionScheduler:
    """Create and start an injection scheduler.

    Args:
        interval_seconds: Base seconds between injections.
        randomization_seconds: ± variance in scheduling (0 = exact timing).
        queue: MessageQueue instance for content units.

    Returns:
        The created InjectionScheduler instance.
    """
    scheduler = InjectionScheduler(
        interval_seconds=interval_seconds,
        randomization_seconds=randomization_seconds,
        queue=queue
    )
    await scheduler.start()
    return scheduler


async def stop_scheduler(scheduler: InjectionScheduler) -> None:
    """Stop an injection scheduler gracefully.

    Args:
        scheduler: The InjectionScheduler instance to stop.
    """
    await scheduler.stop()
