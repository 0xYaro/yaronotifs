"""
RSS Feed Source Provider - Example Implementation

This is a template for implementing an RSS feed source.
Install required package: pip install feedparser

Usage:
    rss_source = RSSSource(
        name="TechCrunch",
        feed_url="https://techcrunch.com/feed/",
        poll_interval_minutes=15
    )
"""

from typing import AsyncIterator, Set
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from sources.base import BaseSource, SourceMessage
from utils import get_logger

logger = get_logger(__name__)


class RSSSource(BaseSource):
    """
    RSS feed source provider.

    Polls an RSS feed at regular intervals and yields new articles as SourceMessages.
    Tracks seen articles to avoid duplicates.
    """

    def __init__(
        self,
        feed_url: str,
        name: str = None,
        source_id: str = None,
        poll_interval_minutes: int = 15,
        max_age_hours: int = 24
    ):
        """
        Initialize RSS source.

        Args:
            feed_url: URL of the RSS feed
            name: Human-readable name (defaults to feed title)
            source_id: Unique identifier (auto-generated from URL if not provided)
            poll_interval_minutes: How often to poll the feed
            max_age_hours: Ignore articles older than this
        """
        if not source_id:
            source_id = f"rss_{hash(feed_url) % 100000}"

        super().__init__(name or "RSS Feed", source_id)

        self.feed_url = feed_url
        self.poll_interval = poll_interval_minutes * 60  # Convert to seconds
        self.max_age = timedelta(hours=max_age_hours)
        self.seen_entries: Set[str] = set()  # Track seen article IDs
        self.message_queue: asyncio.Queue = asyncio.Queue()

    async def start(self) -> bool:
        """
        Start the RSS feed poller.

        Returns:
            bool: True if started successfully
        """
        try:
            # Test connection to feed
            import feedparser
            self.feedparser = feedparser

            feed = await asyncio.get_event_loop().run_in_executor(
                None,
                feedparser.parse,
                self.feed_url
            )

            if feed.bozo:  # Feed error
                logger.error(f"Invalid RSS feed: {self.feed_url}")
                return False

            # Update name if not set
            if self.name == "RSS Feed" and hasattr(feed.feed, 'title'):
                self.name = feed.feed.title

            self.running = True

            # Start polling task
            asyncio.create_task(self._poll_feed())

            logger.info(f"✓ RSSSource '{self.name}' started (polling every {self.poll_interval}s)")
            return True

        except ImportError:
            logger.error("feedparser not installed. Install with: pip install feedparser")
            return False
        except Exception as e:
            logger.error(f"Failed to start RSSSource: {e}", exc_info=True)
            return False

    async def stop(self) -> None:
        """Stop the RSS feed poller."""
        self.running = False
        logger.info(f"RSSSource '{self.name}' stopped")

    async def _poll_feed(self) -> None:
        """
        Poll the RSS feed at regular intervals.

        Fetches new entries and queues them as SourceMessages.
        """
        while self.running:
            try:
                # Parse feed
                feed = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.feedparser.parse,
                    self.feed_url
                )

                if feed.bozo:
                    logger.warning(f"Feed parse error for {self.name}")
                    await asyncio.sleep(self.poll_interval)
                    continue

                # Process new entries
                new_count = 0
                for entry in feed.entries:
                    # Generate unique ID for this entry
                    entry_id = entry.get('id', entry.get('link', str(hash(entry.title))))

                    # Skip if already seen
                    if entry_id in self.seen_entries:
                        continue

                    # Check age
                    published = entry.get('published_parsed')
                    if published:
                        pub_date = datetime(*published[:6])
                        if datetime.now() - pub_date > self.max_age:
                            continue  # Too old

                    # Convert to SourceMessage
                    message = self._convert_entry(entry)
                    await self.message_queue.put(message)

                    # Mark as seen
                    self.seen_entries.add(entry_id)
                    new_count += 1

                if new_count > 0:
                    logger.info(f"Found {new_count} new articles from {self.name}")

                # Cleanup old seen entries (prevent memory growth)
                if len(self.seen_entries) > 1000:
                    self.seen_entries = set(list(self.seen_entries)[-500:])

            except Exception as e:
                logger.error(f"Error polling RSS feed '{self.name}': {e}", exc_info=True)

            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    def _convert_entry(self, entry) -> SourceMessage:
        """
        Convert an RSS entry to a SourceMessage.

        Args:
            entry: feedparser entry object

        Returns:
            SourceMessage
        """
        # Extract content
        title = entry.get('title', 'Untitled')
        summary = entry.get('summary', '')
        content = entry.get('content', [{}])[0].get('value', summary)

        # Combine title and content
        text = f"**{title}**\n\n{content}"

        # Get timestamp
        published = entry.get('published_parsed')
        timestamp = datetime.now()
        if published:
            timestamp = datetime(*published[:6])

        return SourceMessage(
            text=text,
            source_name=self.name,
            source_id=self.source_id,
            timestamp=timestamp,
            url=entry.get('link'),
            message_id=entry.get('id', entry.get('link')),
            metadata={
                'author': entry.get('author', ''),
                'tags': [tag.term for tag in entry.get('tags', [])],
            }
        )

    async def get_messages(self) -> AsyncIterator[SourceMessage]:
        """
        Get messages from the RSS source as they arrive.

        Yields:
            SourceMessage: New articles
        """
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error getting RSS message: {e}")
                await asyncio.sleep(1)
