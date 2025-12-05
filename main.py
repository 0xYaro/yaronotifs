#!/usr/bin/env python3
"""
Market Intelligence Aggregator & Router - Modular Architecture

Main application entry point for the modular intelligence bot.

This bot uses a modular source architecture that allows easy integration of:
- Telegram channels (existing)
- RSS feeds (new)
- Web scrapers (new)
- REST APIs (new)
- Custom sources (easy to add)

All sources are processed through a unified LLM-powered pipeline.

Usage:
    python main.py

Requirements:
    - .env file with configuration (see .env.example)
    - .session file created by running scripts/create_session.py locally
"""

import asyncio
import signal
import sys
from pathlib import Path

from config import settings
from sources import SourceRegistry, TelegramSource
from pipelines import UnifiedPipeline
from services import StatusReporter
from utils import setup_logger, get_logger


# Global logger
logger = None


async def health_checks() -> bool:
    """
    Perform pre-flight health checks.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    logger.info("Running health checks...")

    try:
        # Validate configuration
        settings.validate()
        logger.info("✓ Configuration validated")

        # Check session file exists
        session_path = settings.BASE_DIR / f"{settings.SESSION_NAME}.session"
        if not session_path.exists():
            logger.error(f"✗ Session file not found: {session_path}")
            logger.error("Please run: python scripts/create_session.py")
            return False
        logger.info("✓ Session file found")

        # Test Gemini API
        from services import GeminiService
        gemini = GeminiService()
        if await gemini.health_check():
            logger.info("✓ Gemini API accessible")
        else:
            logger.warning("⚠ Gemini API health check failed (but continuing)")

        return True

    except ValueError as e:
        logger.error(f"✗ Configuration error: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Health check failed: {e}")
        return False


async def main():
    """
    Main application loop - Modular Source Architecture.
    """
    global logger

    # Setup logging
    logger = setup_logger('yaronotifs', level=settings.LOG_LEVEL)

    logger.info("=" * 60)
    logger.info("MARKET INTELLIGENCE AGGREGATOR & ROUTER")
    logger.info("Modular Source Architecture")
    logger.info("=" * 60)
    logger.info("")

    # Run health checks
    if not await health_checks():
        logger.error("Health checks failed. Exiting.")
        return 1

    logger.info("")
    logger.info("Initializing modular source registry...")

    # ========================================
    # Initialize Source Registry
    # ========================================
    registry = SourceRegistry()

    # ========================================
    # Register Telegram Source
    # ========================================
    # This wraps your existing Telegram monitoring in the modular architecture.
    # The TelegramSource will monitor channels specified in config/settings.py
    # and convert Telegram messages to SourceMessage format.
    telegram_source = TelegramSource(
        name="Telegram Channels",
        source_id="telegram",
        monitored_channels=settings.MONITORED_CHANNELS
    )
    registry.register(telegram_source)

    # ========================================
    # Register Additional Sources (Optional)
    # ========================================
    # 🎯 ADD YOUR NEW SOURCES HERE!
    #
    # The modular architecture makes it easy to add any information source.
    # Just uncomment the examples below or create your own.
    #
    # Pattern:
    #   1. Import the source type
    #   2. Create an instance with your config
    #   3. Register it with registry.register(source)
    #
    # See ADDING_NEW_SOURCES.md for detailed examples and templates.
    # See QUICK_REFERENCE.md for copy-paste snippets.
    #
    # Uncomment and configure additional sources as needed:

    # Example: Add an RSS feed
    # from sources.examples import RSSSource
    # rss_source = RSSSource(
    #     name="CoinDesk",
    #     feed_url="https://www.coindesk.com/arc/outboundfeeds/rss/",
    #     poll_interval_minutes=20
    # )
    # registry.register(rss_source)

    # Example: Add trending crypto tracker
    # from sources.examples import CoinGeckoTrendingSource
    # trending_source = CoinGeckoTrendingSource()
    # registry.register(trending_source)

    # Example: Add a web scraper
    # from sources.examples import WebScraperSource
    # scraper = WebScraperSource(
    #     name="Example News Site",
    #     url="https://example.com/news",
    #     css_selector=".article",
    #     scrape_interval_minutes=30
    # )
    # registry.register(scraper)

    logger.info("")
    logger.info("Starting all registered sources...")

    # Start all sources
    if not await registry.start_all():
        logger.error("Failed to start sources. Exiting.")
        return 1

    # ========================================
    # Initialize Unified Pipeline
    # ========================================
    logger.info("")
    logger.info("Initializing unified processing pipeline...")

    # Get Telegram client for output (we need it for sending messages)
    telegram_client = telegram_source.client.client

    pipeline = UnifiedPipeline(
        client=telegram_client,
        output_channel_id=settings.OUTPUT_CHANNEL_ID
    )

    # ========================================
    # Initialize Status Reporter
    # ========================================
    status_reporter = StatusReporter(
        client=telegram_client,
        status_destination_id=settings.STATUS_DESTINATION_ID
    )

    # ========================================
    # Define Message Handler
    # ========================================
    async def process_message(source_message):
        """
        Process a message from any source through the unified pipeline.

        Args:
            source_message: SourceMessage from any registered source
        """
        import time
        start_time = time.time()

        try:
            logger.info(f"⏱️ [TIMING] Starting pipeline processing for message from {source_message.source_name}")

            pipeline_start = time.time()
            success = await pipeline.process(source_message)
            pipeline_time = time.time() - pipeline_start

            total_time = time.time() - start_time

            if success:
                logger.info(f"✓ Processed message from {source_message.source_name} | Pipeline: {pipeline_time:.2f}s | Total: {total_time:.2f}s")
            else:
                logger.warning(f"✗ Failed to process message from {source_message.source_name}")
        except Exception as e:
            logger.error(f"Error processing message from {source_message.source_name}: {e}", exc_info=True)
            await status_reporter.report_error(
                error_type="Pipeline Exception",
                error_message=str(e),
                context={"source": source_message.source_name}
            )

    # ========================================
    # Start Processing
    # ========================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("✓ BOT IS RUNNING")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Architecture: Modular Source Registry + Unified Pipeline")
    logger.info(f"Active sources: {len(registry.list_sources())}")
    for source_id in registry.list_sources():
        source = registry.get_source(source_id)
        logger.info(f"  • {source.name} (ID: {source_id})")
    logger.info("")
    logger.info("All messages processed through UnifiedPipeline with LLM intelligence")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    # Send startup notification
    await status_reporter.report_startup(
        monitored_channels=len(settings.MONITORED_CHANNELS)
    )

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info("")
        logger.info("Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start message processing and wait for shutdown
        processing_task = asyncio.create_task(
            registry.process_messages(process_message)
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

        # Cancel processing
        processing_task.cancel()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")

    finally:
        logger.info("Shutting down...")

        # Stop all sources
        await registry.stop_all()

        # Health check one last time
        health = await registry.health_check()
        logger.info(f"Final health check: {health}")

        logger.info("")
        logger.info("Goodbye!")

    return 0


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        if logger:
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}")
        sys.exit(1)
