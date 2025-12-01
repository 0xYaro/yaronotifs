import asyncio
from typing import Dict
from telethon.tl.types import Message

from config import settings
from pipelines import UnifiedPipeline
from services import StatusReporter
from utils import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """
    Central message routing and orchestration layer.

    This class:
    1. Receives messages from monitored channels
    2. Processes all messages through the unified pipeline
    3. Ensures non-blocking processing using asyncio.create_task()
    4. Tracks processing metrics

    Key Design:
    - All messages go through a single UnifiedPipeline
    - LLM intelligently determines processing needs
    - Each message is processed in a separate async task
    - PDF downloads never block text message processing
    - Graceful error handling prevents crashes
    """

    def __init__(self, telegram_client):
        """
        Initialize the message handler.

        Args:
            telegram_client: TelegramClientWrapper instance
        """
        self.client = telegram_client
        self.output_channel_id = settings.OUTPUT_CHANNEL_ID
        self.status_destination_id = settings.STATUS_DESTINATION_ID

        # Initialize unified pipeline
        self.unified_pipeline = UnifiedPipeline(
            client=telegram_client.client,
            output_channel_id=self.output_channel_id
        )

        # Initialize status reporter
        self.status_reporter = StatusReporter(
            client=telegram_client.client,
            status_destination_id=self.status_destination_id
        )

        # Metrics tracking
        self.metrics = {
            'total_messages': 0,
            'processed': 0,
            'errors': 0
        }

        logger.info("MessageHandler initialized with UnifiedPipeline")

    def register_handlers(self):
        """
        Register message handlers for all monitored channels.

        This sets up event listeners that route messages to the handle_message method.
        """
        print(f"DEBUG: register_handlers() called")
        all_channels = settings.MONITORED_CHANNELS
        print(f"DEBUG: all_channels = {all_channels}")

        self.client.on_new_message(
            chat_ids=all_channels,
            handler=self.handle_message
        )
        print(f"DEBUG: on_new_message() completed")

        logger.info(f"✓ Registered handlers for {len(all_channels)} channels")
        logger.info(f"  - All messages will be processed through UnifiedPipeline")

    async def handle_message(self, message: Message):
        """
        Handle an incoming message through the unified pipeline.

        CRITICAL: This method uses asyncio.create_task() to process messages
        concurrently. This ensures that a slow PDF download doesn't block
        fast text message processing.

        Args:
            message: Incoming Telegram message
        """
        print(f"DEBUG: handle_message() called! Message received!")
        self.metrics['total_messages'] += 1

        try:
            # Get channel ID
            channel_id = message.chat_id if hasattr(message, 'chat_id') else None
            print(f"DEBUG: channel_id = {channel_id}")
            if not channel_id:
                logger.warning("Message has no chat_id, skipping")
                return

            # Log message receipt
            logger.info(f"📩 New message from channel {channel_id} → UnifiedPipeline")
            print(f"DEBUG: About to process message through UnifiedPipeline")

            # Create a background task for processing
            # This is the KEY to non-blocking concurrency
            asyncio.create_task(self._process_message(message))

        except Exception as e:
            logger.error(f"Error in handle_message: {e}", exc_info=True)
            self.metrics['errors'] += 1

    async def _process_message(self, message: Message):
        """
        Process a message through the UnifiedPipeline.

        This runs as an independent task and won't block other messages.
        The UnifiedPipeline intelligently determines what processing is needed.

        Args:
            message: Telegram message
        """
        try:
            success = await self.unified_pipeline.process(message)
            if success:
                self.metrics['processed'] += 1
                logger.info("✓ UnifiedPipeline completed")
            else:
                logger.warning("✗ UnifiedPipeline failed")
                self.metrics['errors'] += 1
                # Report error to status channel
                await self.status_reporter.report_error(
                    error_type="UnifiedPipeline Failure",
                    error_message="Message processing failed in unified pipeline",
                    context={"channel_id": message.chat_id}
                )

        except Exception as e:
            logger.error(f"Error in unified pipeline: {e}", exc_info=True)
            self.metrics['errors'] += 1
            # Report error to status channel
            await self.status_reporter.report_error(
                error_type="UnifiedPipeline Exception",
                error_message=str(e),
                context={"channel_id": message.chat_id}
            )

    def get_metrics(self) -> Dict[str, int]:
        """
        Get processing metrics.

        Returns:
            dict: Dictionary of metrics
        """
        return self.metrics.copy()

    async def send_status_report(self):
        """
        Send a status report to the configured status destination.

        If STATUS_DESTINATION_ID is not configured, this method does nothing.
        Useful for monitoring and debugging.
        """
        # Skip if status reports are disabled
        if not self.status_destination_id:
            logger.debug("Status reports disabled (STATUS_DESTINATION_ID not set)")
            return

        try:
            report = f"""**📊 Bot Status Report**

**Messages Received:** {self.metrics['total_messages']}
**Successfully Processed:** {self.metrics['processed']}
**Errors:** {self.metrics['errors']}

_Bot is running with UnifiedPipeline architecture_
"""
            await self.client.send_message(
                self.status_destination_id,
                report,
                parse_mode='Markdown'
            )
            logger.info("Status report sent to status destination")

        except Exception as e:
            logger.error(f"Failed to send status report: {e}")
