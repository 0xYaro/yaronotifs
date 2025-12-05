"""
API Source Provider - Example Implementation

This is a template for implementing an API-based source.
Install required package: pip install aiohttp

Usage:
    api_source = APISource(
        name="CoinGecko Trending",
        api_url="https://api.coingecko.com/api/v3/search/trending",
        poll_interval_minutes=60,
        api_key="your_api_key"  # if required
    )
"""

from typing import AsyncIterator, Set, Optional, Dict, Any
import asyncio
from datetime import datetime
import json

from sources.base import BaseSource, SourceMessage
from utils import get_logger

logger = get_logger(__name__)


class APISource(BaseSource):
    """
    REST API source provider.

    Polls a REST API at regular intervals and yields new data as SourceMessages.
    Highly customizable for different API formats.
    """

    def __init__(
        self,
        api_url: str,
        name: str = "API Source",
        source_id: str = None,
        poll_interval_minutes: int = 30,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        transform_func: Optional[callable] = None
    ):
        """
        Initialize API source.

        Args:
            api_url: URL of the API endpoint
            name: Human-readable name
            source_id: Unique identifier
            poll_interval_minutes: How often to poll the API
            api_key: Optional API key (will be added to headers)
            headers: Optional custom headers
            transform_func: Optional function to transform API response to messages
                           Signature: (data: dict) -> List[dict]
                           Each dict should have 'text', 'url', 'metadata' keys
        """
        if not source_id:
            source_id = f"api_{hash(api_url) % 100000}"

        super().__init__(name, source_id)

        self.api_url = api_url
        self.poll_interval = poll_interval_minutes * 60
        self.api_key = api_key
        self.headers = headers or {}
        self.transform_func = transform_func or self._default_transform
        self.seen_ids: Set[str] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()

        # Add API key to headers if provided
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'

    async def start(self) -> bool:
        """
        Start the API poller.

        Returns:
            bool: True if started successfully
        """
        try:
            import aiohttp
            self.aiohttp = aiohttp

            # Test API connection
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, headers=self.headers) as response:
                    if response.status not in (200, 201):
                        logger.error(f"API test failed: HTTP {response.status}")
                        return False

            self.running = True

            # Start polling task
            asyncio.create_task(self._poll_api())

            logger.info(f"✓ APISource '{self.name}' started (polling every {self.poll_interval}s)")
            return True

        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
            return False
        except Exception as e:
            logger.error(f"Failed to start APISource: {e}", exc_info=True)
            return False

    async def stop(self) -> None:
        """Stop the API poller."""
        self.running = False
        logger.info(f"APISource '{self.name}' stopped")

    async def _poll_api(self) -> None:
        """
        Poll the API at regular intervals.
        """
        while self.running:
            try:
                async with self.aiohttp.ClientSession() as session:
                    async with session.get(self.api_url, headers=self.headers) as response:
                        if response.status != 200:
                            logger.warning(f"API returned HTTP {response.status}")
                            await asyncio.sleep(self.poll_interval)
                            continue

                        data = await response.json()

                        # Transform API response to messages
                        items = self.transform_func(data)

                        new_count = 0
                        for item in items:
                            # Generate unique ID
                            item_id = item.get('id', hash(item['text']))

                            if item_id not in self.seen_ids:
                                message = SourceMessage(
                                    text=item['text'],
                                    source_name=self.name,
                                    source_id=self.source_id,
                                    timestamp=item.get('timestamp', datetime.now()),
                                    url=item.get('url'),
                                    metadata=item.get('metadata', {}),
                                    message_id=str(item_id)
                                )

                                await self.message_queue.put(message)
                                self.seen_ids.add(item_id)
                                new_count += 1

                        if new_count > 0:
                            logger.info(f"Found {new_count} new items from {self.name}")

                        # Cleanup
                        if len(self.seen_ids) > 1000:
                            self.seen_ids = set(list(self.seen_ids)[-500:])

            except Exception as e:
                logger.error(f"Error polling API '{self.name}': {e}", exc_info=True)

            await asyncio.sleep(self.poll_interval)

    def _default_transform(self, data: Any) -> list:
        """
        Default transformation function.

        Override this or provide custom transform_func for your API format.

        Args:
            data: API response data

        Returns:
            List of dicts with 'text', 'url', 'id', 'timestamp', 'metadata'
        """
        items = []

        # Handle common API formats
        if isinstance(data, dict):
            # Check for common wrapper keys
            if 'data' in data:
                data = data['data']
            elif 'results' in data:
                data = data['results']
            elif 'items' in data:
                data = data['items']

        # Convert to list if not already
        if isinstance(data, dict):
            data = [data]

        for item in data:
            if isinstance(item, dict):
                # Try to extract common fields
                text = item.get('text') or item.get('description') or item.get('content')
                if text:
                    items.append({
                        'id': item.get('id', hash(text)),
                        'text': text,
                        'url': item.get('url') or item.get('link'),
                        'timestamp': item.get('timestamp') or item.get('created_at'),
                        'metadata': item
                    })

        return items

    async def get_messages(self) -> AsyncIterator[SourceMessage]:
        """
        Get messages from the API source as they arrive.

        Yields:
            SourceMessage: API data as messages
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
                logger.error(f"Error getting API message: {e}")
                await asyncio.sleep(1)


# Example: CoinGecko Trending Coins
class CoinGeckoTrendingSource(APISource):
    """
    Example: CoinGecko trending coins API source.

    Fetches trending cryptocurrencies and formats them as intelligence messages.
    """

    def __init__(self):
        super().__init__(
            api_url="https://api.coingecko.com/api/v3/search/trending",
            name="CoinGecko Trending",
            source_id="coingecko_trending",
            poll_interval_minutes=60,
            transform_func=self._transform_trending
        )

    def _transform_trending(self, data: dict) -> list:
        """Transform CoinGecko trending response to messages."""
        items = []

        coins = data.get('coins', [])

        if not coins:
            return items

        # Create a summary message
        trending_list = []
        for i, coin_item in enumerate(coins[:7], 1):  # Top 7
            coin = coin_item.get('item', {})
            name = coin.get('name', 'Unknown')
            symbol = coin.get('symbol', '???')
            rank = coin.get('market_cap_rank', 'N/A')

            trending_list.append(f"{i}. **{name}** (${symbol}) - Rank #{rank}")

        text = "**🔥 Trending Cryptocurrencies**\n\n" + "\n".join(trending_list)

        items.append({
            'id': f"trending_{datetime.now().strftime('%Y%m%d%H')}",  # Hourly updates
            'text': text,
            'url': "https://www.coingecko.com/en/coins/trending",
            'timestamp': datetime.now(),
            'metadata': {'coins': coins}
        })

        return items
