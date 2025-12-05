"""
Web Scraper Source Provider - Example Implementation

This is a template for implementing a web scraper source.
Install required packages: pip install aiohttp beautifulsoup4

Usage:
    scraper = WebScraperSource(
        name="CoinDesk Bitcoin News",
        url="https://www.coindesk.com/tag/bitcoin/",
        scrape_interval_minutes=30,
        css_selector=".article-card"
    )
"""

from typing import AsyncIterator, Set, List
import asyncio
from datetime import datetime
from pathlib import Path

from sources.base import BaseSource, SourceMessage
from utils import get_logger

logger = get_logger(__name__)


class WebScraperSource(BaseSource):
    """
    Web scraper source provider.

    Scrapes a webpage at regular intervals and yields new content as SourceMessages.
    Tracks seen content to avoid duplicates.
    """

    def __init__(
        self,
        url: str,
        css_selector: str,
        name: str = None,
        source_id: str = None,
        scrape_interval_minutes: int = 30,
        headers: dict = None
    ):
        """
        Initialize web scraper source.

        Args:
            url: URL to scrape
            css_selector: CSS selector to find content elements
            name: Human-readable name
            source_id: Unique identifier
            scrape_interval_minutes: How often to scrape
            headers: Optional HTTP headers
        """
        if not source_id:
            source_id = f"scraper_{hash(url) % 100000}"

        super().__init__(name or "Web Scraper", source_id)

        self.url = url
        self.css_selector = css_selector
        self.scrape_interval = scrape_interval_minutes * 60
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (compatible; IntelligenceBot/1.0)'
        }
        self.seen_content: Set[str] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()

    async def start(self) -> bool:
        """
        Start the web scraper.

        Returns:
            bool: True if started successfully
        """
        try:
            # Test connection
            import aiohttp
            from bs4 import BeautifulSoup

            self.aiohttp = aiohttp
            self.BeautifulSoup = BeautifulSoup

            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to access {self.url}: HTTP {response.status}")
                        return False

            self.running = True

            # Start scraping task
            asyncio.create_task(self._scrape_loop())

            logger.info(f"✓ WebScraperSource '{self.name}' started (scraping every {self.scrape_interval}s)")
            return True

        except ImportError as e:
            logger.error(f"Missing dependency: {e}. Install with: pip install aiohttp beautifulsoup4")
            return False
        except Exception as e:
            logger.error(f"Failed to start WebScraperSource: {e}", exc_info=True)
            return False

    async def stop(self) -> None:
        """Stop the web scraper."""
        self.running = False
        logger.info(f"WebScraperSource '{self.name}' stopped")

    async def _scrape_loop(self) -> None:
        """
        Scrape the webpage at regular intervals.
        """
        while self.running:
            try:
                items = await self._scrape_page()

                new_count = 0
                for item in items:
                    # Generate content hash for deduplication
                    content_hash = hash(item['text'])

                    if content_hash not in self.seen_content:
                        message = SourceMessage(
                            text=item['text'],
                            source_name=self.name,
                            source_id=self.source_id,
                            timestamp=datetime.now(),
                            url=item.get('url', self.url),
                            metadata=item.get('metadata', {})
                        )

                        await self.message_queue.put(message)
                        self.seen_content.add(content_hash)
                        new_count += 1

                if new_count > 0:
                    logger.info(f"Scraped {new_count} new items from {self.name}")

                # Cleanup old hashes
                if len(self.seen_content) > 1000:
                    self.seen_content = set(list(self.seen_content)[-500:])

            except Exception as e:
                logger.error(f"Error scraping {self.name}: {e}", exc_info=True)

            # Wait before next scrape
            await asyncio.sleep(self.scrape_interval)

    async def _scrape_page(self) -> List[dict]:
        """
        Scrape the webpage and extract items.

        Returns:
            List of dicts with 'text', 'url', and optional 'metadata'
        """
        items = []

        async with self.aiohttp.ClientSession() as session:
            async with session.get(self.url, headers=self.headers) as response:
                if response.status != 200:
                    logger.warning(f"HTTP {response.status} from {self.url}")
                    return items

                html = await response.text()
                soup = self.BeautifulSoup(html, 'html.parser')

                # Find all matching elements
                elements = soup.select(self.css_selector)

                for element in elements:
                    # Extract text
                    text = element.get_text(strip=True)

                    if not text:
                        continue

                    # Try to find a link
                    link = element.find('a')
                    item_url = link.get('href') if link else None

                    # Make URL absolute if needed
                    if item_url and item_url.startswith('/'):
                        from urllib.parse import urljoin
                        item_url = urljoin(self.url, item_url)

                    items.append({
                        'text': text,
                        'url': item_url,
                        'metadata': {}
                    })

        return items

    async def get_messages(self) -> AsyncIterator[SourceMessage]:
        """
        Get messages from the web scraper as they arrive.

        Yields:
            SourceMessage: Scraped content
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
                logger.error(f"Error getting scraper message: {e}")
                await asyncio.sleep(1)
