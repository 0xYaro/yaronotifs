"""
Source providers for the intelligence aggregator.

This module provides a modular system for integrating various information sources
(Telegram channels, RSS feeds, web scrapers, APIs, etc.) into the unified pipeline.
"""

from .base import BaseSource, SourceMessage
from .telegram_source import TelegramSource
from .registry import SourceRegistry

__all__ = [
    'BaseSource',
    'SourceMessage',
    'TelegramSource',
    'SourceRegistry',
]
