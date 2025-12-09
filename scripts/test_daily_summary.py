#!/usr/bin/env python3
"""
Test Daily Summary Generation

This script allows you to manually test the daily summary feature without waiting for 10am SGT.
It will immediately generate summaries for both cryptonotifs and equitiesnotifs channels.

Usage:
    python scripts/test_daily_summary.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from core import TelegramClientWrapper
from services import DailySummaryService
from utils import setup_logger

logger = setup_logger('test_daily_summary', level='INFO')


async def main():
    """
    Test the daily summary generation.
    """
    logger.info("=" * 60)
    logger.info("TESTING DAILY SUMMARY GENERATION")
    logger.info("=" * 60)

    # Initialize Telegram client
    logger.info("Initializing Telegram client...")
    client_wrapper = TelegramClientWrapper()

    if not await client_wrapper.start():
        logger.error("Failed to start Telegram client")
        return 1

    try:
        # Get the underlying client
        client = client_wrapper.client

        # Initialize daily summary service
        logger.info("Initializing Daily Summary Service...")
        daily_summary = DailySummaryService(client=client)

        # Generate summaries
        logger.info("")
        logger.info("Generating daily summaries...")
        logger.info("This will retrieve all messages from the past 24 hours and create summaries.")
        logger.info("")

        success = await daily_summary.generate_daily_summary()

        if success:
            logger.info("")
            logger.info("=" * 60)
            logger.info("✓ Daily summaries generated successfully!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Check your Telegram channels:")
            logger.info(f"  - {settings.CRYPTO_OUTPUT_CHANNEL}")
            logger.info(f"  - {settings.EQUITIES_OUTPUT_CHANNEL}")
            logger.info("")
            logger.info("Look for messages with #dailysummary hashtag")
            return 0
        else:
            logger.error("Failed to generate daily summaries")
            return 1

    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return 1

    finally:
        # Stop the client
        await client_wrapper.stop()


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
