import asyncio
from datetime import datetime
from typing import Optional
from telethon import TelegramClient

from config import settings
from utils import get_logger

logger = get_logger(__name__)


class StatusReporter:
    """
    Service for sending status updates and error notifications to a monitoring channel.

    This service provides:
    - Startup notifications
    - Periodic health check updates (every 4 hours)
    - Error reporting when processing failures occur
    """

    def __init__(self, client: TelegramClient, status_destination_id: str):
        """
        Initialize the status reporter.

        Args:
            client: Authenticated Telegram client
            status_destination_id: Channel/user ID to send status updates to
        """
        self.client = client
        self.status_destination_id = status_destination_id
        self.start_time = datetime.now()
        self.enabled = bool(status_destination_id)

        if not self.enabled:
            logger.info("Status reporting is disabled (no STATUS_DESTINATION_ID configured)")
        else:
            logger.info(f"Status reporting enabled: {status_destination_id}")

    async def report_startup(self, monitored_channels: int) -> None:
        """
        Send a startup notification when the bot starts.

        Args:
            monitored_channels: Number of channels being monitored
        """
        if not self.enabled:
            return

        try:
            startup_time = self.start_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            message = f"""🟢 **Bot Started**

**Time:** {startup_time}
**Status:** Operational
**Monitoring:** {monitored_channels} channels

The intelligence aggregator is now running and processing messages.
"""
            await self._send_status(message)
            logger.info("Startup notification sent")
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")

    async def report_periodic_status(self, metrics: dict) -> None:
        """
        Send periodic status update with current metrics.

        Args:
            metrics: Dictionary containing current bot metrics
        """
        if not self.enabled:
            return

        try:
            uptime = self._calculate_uptime()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            message = f"""📊 **Periodic Status Update**

**Time:** {current_time}
**Uptime:** {uptime}
**Status:** Operational

**Metrics:**
• Total Messages: {metrics.get('total_messages', 0)}
• Translator Processed: {metrics.get('translator_processed', 0)}
• Analyst Processed: {metrics.get('analyst_processed', 0)}
• Errors: {metrics.get('errors', 0)}

All systems operational.
"""
            await self._send_status(message)
            logger.info("Periodic status update sent")
        except Exception as e:
            logger.error(f"Failed to send periodic status: {e}")

    async def report_error(self, error_type: str, error_message: str,
                          context: Optional[dict] = None) -> None:
        """
        Report an error that occurred during message processing.

        Args:
            error_type: Type/category of the error
            error_message: Error message details
            context: Optional additional context (channel, message ID, etc.)
        """
        if not self.enabled:
            return

        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            context_str = ""
            if context:
                context_str = "\n**Context:**\n" + "\n".join(
                    f"• {k}: {v}" for k, v in context.items()
                )

            message = f"""⚠️ **Error Alert**

**Time:** {current_time}
**Type:** {error_type}
**Error:** {error_message}
{context_str}

The bot continues running, but this error may require attention.
"""
            await self._send_status(message)
            logger.info(f"Error report sent: {error_type}")
        except Exception as e:
            logger.error(f"Failed to send error report: {e}")

    async def start_periodic_updates(self, metrics_callback, interval_hours: int = 4) -> None:
        """
        Start a background task that sends periodic status updates.

        Args:
            metrics_callback: Async function that returns current metrics dict
            interval_hours: Hours between status updates (default: 4)
        """
        if not self.enabled:
            return

        async def periodic_task():
            interval_seconds = interval_hours * 3600
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    metrics = await metrics_callback()
                    await self.report_periodic_status(metrics)
                except asyncio.CancelledError:
                    logger.info("Periodic status updates cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in periodic status update: {e}")

        # Start the background task
        asyncio.create_task(periodic_task())
        logger.info(f"Periodic status updates started (every {interval_hours} hours)")

    async def _send_status(self, message: str) -> None:
        """
        Internal method to send status message to the configured destination.

        Args:
            message: Status message to send
        """
        try:
            await self.client.send_message(
                self.status_destination_id,
                message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")
            raise

    def _calculate_uptime(self) -> str:
        """
        Calculate and format the bot's uptime.

        Returns:
            str: Formatted uptime string (e.g., "2d 5h 30m")
        """
        uptime_delta = datetime.now() - self.start_time
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")

        return " ".join(parts)
