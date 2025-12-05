"""
Source registry for managing multiple information sources.

The registry allows you to register and manage multiple sources
(Telegram, RSS, web scrapers, APIs, etc.) in a unified way.
"""

from typing import Dict, List, Callable, Awaitable
import asyncio

from .base import BaseSource, SourceMessage
from utils import get_logger

logger = get_logger(__name__)


class SourceRegistry:
    """
    Central registry for managing all information sources.

    The registry:
    1. Registers and manages multiple sources
    2. Starts/stops all sources
    3. Multiplexes messages from all sources to a single handler
    4. Provides health monitoring

    Example:
        registry = SourceRegistry()

        # Register sources
        telegram_source = TelegramSource(monitored_channels=[...])
        rss_source = RSSSource(feed_url="https://...")

        registry.register(telegram_source)
        registry.register(rss_source)

        # Start all sources
        await registry.start_all()

        # Process all messages through unified handler
        await registry.process_messages(message_handler)
    """

    def __init__(self):
        """Initialize the source registry."""
        self.sources: Dict[str, BaseSource] = {}
        self.running = False

    def register(self, source: BaseSource) -> None:
        """
        Register a new source.

        Args:
            source: Source to register

        Raises:
            ValueError: If source_id is already registered
        """
        if source.source_id in self.sources:
            raise ValueError(f"Source with ID '{source.source_id}' already registered")

        self.sources[source.source_id] = source
        logger.info(f"Registered source: {source.name} (ID: {source.source_id})")

    def unregister(self, source_id: str) -> None:
        """
        Unregister a source.

        Args:
            source_id: ID of source to unregister
        """
        if source_id in self.sources:
            del self.sources[source_id]
            logger.info(f"Unregistered source: {source_id}")

    def get_source(self, source_id: str) -> BaseSource:
        """
        Get a registered source by ID.

        Args:
            source_id: Source identifier

        Returns:
            BaseSource: The source

        Raises:
            KeyError: If source not found
        """
        return self.sources[source_id]

    def list_sources(self) -> List[str]:
        """
        Get list of all registered source IDs.

        Returns:
            List of source IDs
        """
        return list(self.sources.keys())

    async def start_all(self) -> bool:
        """
        Start all registered sources.

        Returns:
            bool: True if all sources started successfully
        """
        if not self.sources:
            logger.warning("No sources registered")
            return False

        logger.info(f"Starting {len(self.sources)} sources...")

        results = await asyncio.gather(
            *[source.start() for source in self.sources.values()],
            return_exceptions=True
        )

        success_count = sum(1 for r in results if r is True)
        failure_count = len(results) - success_count

        if failure_count > 0:
            logger.warning(f"Started {success_count}/{len(self.sources)} sources")
        else:
            logger.info(f"✓ All {success_count} sources started successfully")

        self.running = True
        return success_count > 0

    async def stop_all(self) -> None:
        """
        Stop all registered sources.
        """
        self.running = False
        logger.info(f"Stopping {len(self.sources)} sources...")

        await asyncio.gather(
            *[source.stop() for source in self.sources.values()],
            return_exceptions=True
        )

        logger.info("✓ All sources stopped")

    async def process_messages(
        self,
        handler: Callable[[SourceMessage], Awaitable[bool]]
    ) -> None:
        """
        Process messages from all sources through a unified handler.

        This multiplexes messages from all registered sources and routes
        them to a single handler function (typically UnifiedPipeline.process).

        Args:
            handler: Async function that processes SourceMessage objects
        """
        if not self.sources:
            logger.error("No sources registered")
            return

        logger.info(f"Processing messages from {len(self.sources)} sources...")

        # Create tasks for each source's message stream
        tasks = []
        for source in self.sources.values():
            task = asyncio.create_task(
                self._process_source_messages(source, handler)
            )
            tasks.append(task)

        # Run all source processors concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_source_messages(
        self,
        source: BaseSource,
        handler: Callable[[SourceMessage], Awaitable[bool]]
    ) -> None:
        """
        Process messages from a single source.

        Args:
            source: Source to process messages from
            handler: Handler function for messages
        """
        try:
            async for message in source.get_messages():
                # Process each message in a separate task to avoid blocking
                asyncio.create_task(self._handle_message(message, handler))

        except Exception as e:
            logger.error(
                f"Error processing messages from {source.name}: {e}",
                exc_info=True
            )

    async def _handle_message(
        self,
        message: SourceMessage,
        handler: Callable[[SourceMessage], Awaitable[bool]]
    ) -> None:
        """
        Handle a single message with error handling.

        Args:
            message: Message to process
            handler: Handler function
        """
        try:
            await handler(message)
        except Exception as e:
            logger.error(
                f"Error handling message from {message.source_name}: {e}",
                exc_info=True
            )

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all registered sources.

        Returns:
            Dict mapping source_id to health status (True = healthy)
        """
        health = {}
        for source_id, source in self.sources.items():
            try:
                health[source_id] = await source.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {source_id}: {e}")
                health[source_id] = False

        return health
