#!/usr/bin/env python3
"""
Market Intelligence Aggregator & Router

Main application entry point for the Telegram intelligence bot.

This bot:
1. Monitors specific Telegram channels for market intelligence
2. Processes messages using two pipelines:
   - Pipeline A: Chinese news translation (BWEnews, Foresight News)
   - Pipeline B: PDF research report analysis (DTpapers - equities market research)
3. Forwards processed intelligence to your main Telegram account

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
from core import TelegramClientWrapper, MessageHandler
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
    Main application loop.
    """
    global logger

    # Setup logging
    logger = setup_logger('yaronotifs', level=settings.LOG_LEVEL)

    logger.info("=" * 60)
    logger.info("MARKET INTELLIGENCE AGGREGATOR & ROUTER")
    logger.info("=" * 60)
    logger.info("")

    # Run health checks
    if not await health_checks():
        logger.error("Health checks failed. Exiting.")
        return 1

    logger.info("")
    logger.info("Initializing Telegram client...")

    # Initialize Telegram client
    telegram_client = TelegramClientWrapper()

    # Start client
    if not await telegram_client.start():
        logger.error("Failed to start Telegram client. Exiting.")
        return 1

    # Refresh dialog cache to learn channel IDs
    logger.info("Refreshing Dialog Cache...")
    await telegram_client.client.get_dialogs()

    logger.info("")
    logger.info("Setting up message handlers...")

    # Initialize and register message handler
    message_handler = MessageHandler(telegram_client)
    message_handler.register_handlers()

    logger.info("")
    logger.info("=" * 60)
    logger.info("✓ BOT IS RUNNING")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Architecture: Unified Pipeline (LLM-powered)")
    logger.info(f"Monitoring {len(settings.MONITORED_CHANNELS)} channels:")
    for channel_id in settings.MONITORED_CHANNELS:
        logger.info(f"  • Channel: {channel_id}")
    logger.info("")
    logger.info("All messages processed through UnifiedPipeline")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    # Send startup notification to status channel
    await message_handler.status_reporter.report_startup(
        monitored_channels=len(settings.MONITORED_CHANNELS)
    )

    # Start periodic status updates (every 4 hours)
    async def get_metrics():
        return message_handler.get_metrics()

    await message_handler.status_reporter.start_periodic_updates(
        metrics_callback=get_metrics,
        interval_hours=4
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
        # Run until shutdown signal
        await asyncio.gather(
            telegram_client.run_until_disconnected(),
            shutdown_event.wait()
        )

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")

    finally:
        logger.info("Shutting down...")

        # Cleanup
        await telegram_client.stop()

        # Print final metrics
        metrics = message_handler.get_metrics()
        logger.info("")
        logger.info("Final Statistics:")
        logger.info(f"  Total Messages: {metrics['total_messages']}")
        logger.info(f"  Successfully Processed: {metrics['processed']}")
        logger.info(f"  Errors: {metrics['errors']}")
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
