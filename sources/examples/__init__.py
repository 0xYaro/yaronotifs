"""
Example source implementations.

These are templates/examples for creating new source integrations.
"""

from .rss_source import RSSSource
from .webscraper_source import WebScraperSource
from .api_source import APISource, CoinGeckoTrendingSource

__all__ = [
    'RSSSource',
    'WebScraperSource',
    'APISource',
    'CoinGeckoTrendingSource',
]
