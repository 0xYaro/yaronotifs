"""
Base source provider interface.

All source providers (Telegram, RSS, web scrapers, etc.) should inherit from BaseSource.

🎯 FOR NEW USERS & AI ASSISTANTS:

This file defines the contract that all information sources must follow.
Think of it as a template/blueprint that ensures all sources work together.

Key concepts:
1. BaseSource - Abstract class that all sources inherit from
2. SourceMessage - Standardized message format across ALL sources
3. Every source must implement: start(), stop(), get_messages()

When adding a new source:
- DON'T modify this file
- DO inherit from BaseSource in your new source class
- DO return SourceMessage objects from get_messages()

See sources/examples/ for ready-to-use templates.
See ADDING_NEW_SOURCES.md for step-by-step guides.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, AsyncIterator
from pathlib import Path
from datetime import datetime


@dataclass
class SourceMessage:
    """
    Standardized message format for all sources.

    This adapter allows any source (Telegram, RSS, web scraper, API, etc.)
    to be processed uniformly by the UnifiedPipeline.

    🎯 KEY INSIGHT:
    Every source converts its data into SourceMessage format.
    This means the pipeline doesn't care WHERE data came from -
    Telegram, RSS, web scraper - they all look the same!

    Required: Either 'text' OR 'document_path' must be provided
    Optional: url, metadata, timestamp, etc.

    Example usage:
        # Text message (e.g., from RSS feed)
        msg = SourceMessage(
            text="Article content here...",
            source_name="TechCrunch",
            source_id="rss_techcrunch",
            url="https://techcrunch.com/article"
        )

        # Document message (e.g., PDF from Telegram)
        msg = SourceMessage(
            text="Report caption",
            document_path=Path("/tmp/report.pdf"),
            document_mime_type="application/pdf",
            source_name="Research Channel",
            source_id="telegram_123"
        )
    """

    # Core fields
    text: Optional[str] = None
    source_name: str = "Unknown Source"
    source_id: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)

    # Optional fields
    document_path: Optional[Path] = None  # For PDF/file attachments
    document_mime_type: Optional[str] = None
    url: Optional[str] = None  # Original URL if applicable
    metadata: Dict[str, Any] = field(default_factory=dict)  # Source-specific metadata

    # Message identification
    message_id: Optional[str] = None

    def __post_init__(self):
        """Validate that message has either text or document."""
        if not self.text and not self.document_path:
            raise ValueError("SourceMessage must have either text or document_path")

    def has_document(self) -> bool:
        """Check if this message contains a document."""
        return self.document_path is not None

    def has_text(self) -> bool:
        """Check if this message contains text."""
        return self.text is not None and len(self.text.strip()) > 0

    def get_source_link(self) -> str:
        """Get a formatted source attribution link."""
        if self.url:
            return f"[{self.source_name}]({self.url})"
        return self.source_name


class BaseSource(ABC):
    """
    Abstract base class for all information sources.

    🎯 FOR AI ASSISTANTS & DEVELOPERS:

    This is the interface contract. Any class that inherits from BaseSource
    can be plugged into the system and will work automatically.

    Implementing a new source is as simple as:
    1. Inherit from BaseSource
    2. Implement start() and stop() methods
    3. Yield SourceMessage objects from get_messages()

    The SourceRegistry will handle:
    - Starting/stopping your source
    - Receiving messages from get_messages()
    - Forwarding to UnifiedPipeline
    - Error handling and logging

    You just focus on:
    - Fetching data from your specific source
    - Converting it to SourceMessage format

    Example implementation:
        class RSSSource(BaseSource):
            async def start(self):
                # Test connection, start polling task
                self.running = True
                asyncio.create_task(self._poll_feed())
                return True

            async def stop(self):
                # Cleanup resources
                self.running = False

            async def get_messages(self):
                # Yield messages as they arrive
                while self.running:
                    articles = await self.fetch_feed()
                    for article in articles:
                        yield SourceMessage(
                            text=article.content,
                            source_name="TechCrunch RSS",
                            url=article.link
                        )

    See sources/examples/ for complete working implementations.
    """

    def __init__(self, name: str, source_id: str):
        """
        Initialize the source.

        Args:
            name: Human-readable name for this source
            source_id: Unique identifier for this source
        """
        self.name = name
        self.source_id = source_id
        self.running = False

    @abstractmethod
    async def start(self) -> bool:
        """
        Start the source and begin monitoring for new messages.

        Returns:
            bool: True if started successfully, False otherwise
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the source and cleanup resources.
        """
        pass

    @abstractmethod
    async def get_messages(self) -> AsyncIterator[SourceMessage]:
        """
        Get messages from this source as they arrive.

        This should be an async generator that yields SourceMessage objects.
        The source should handle its own polling/event loop.

        Yields:
            SourceMessage: Standardized message objects
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if the source is healthy and functioning.

        Returns:
            bool: True if healthy, False otherwise
        """
        return self.running
