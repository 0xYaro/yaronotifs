import asyncio
from typing import Dict
from telethon.tl.types import Message

from config import settings
from pipelines import TranslatorPipeline, AnalystPipeline
from services import StatusReporter
from utils import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """
    Central message routing and orchestration layer.

    This class:
    1. Receives messages from monitored channels
    2. Routes messages to the appropriate pipeline based on source
    3. Ensures non-blocking processing using asyncio.create_task()
    4. Tracks processing metrics

    Key Design:
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

        # Initialize pipelines
        self.translator_pipeline = TranslatorPipeline(
            client=telegram_client.client,
            output_channel_id=self.output_channel_id
        )

        self.analyst_pipeline = AnalystPipeline(
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
            'translator_processed': 0,
            'analyst_processed': 0,
            'errors': 0
        }

        logger.info("MessageHandler initialized with pipelines")

    def register_handlers(self):
        """
        Register message handlers for all monitored channels.

        This sets up event listeners that route messages to the handle_message method.
        """
        all_channels = settings.ALL_CHANNELS

        self.client.on_new_message(
            chat_ids=all_channels,
            handler=self.handle_message
        )

        logger.info(f"✓ Registered handlers for {len(all_channels)} channels:")
        logger.info(f"  - Translator channels: {len(settings.TRANSLATOR_CHANNELS)}")
        logger.info(f"  - Analyst channels: {len(settings.ANALYST_CHANNELS)}")

    async def handle_message(self, message: Message):
        """
        Handle an incoming message by routing it to the appropriate pipeline.

        CRITICAL: This method uses asyncio.create_task() to process messages
        concurrently. This ensures that a slow PDF download doesn't block
        fast text message processing.

        Args:
            message: Incoming Telegram message
        """
        self.metrics['total_messages'] += 1

        try:
            # Get channel ID
            channel_id = message.chat_id if hasattr(message, 'chat_id') else None
            if not channel_id:
                logger.warning("Message has no chat_id, skipping")
                return

            # Determine pipeline
            pipeline_type = settings.get_pipeline_for_channel(channel_id)

            if pipeline_type == 'unknown':
                logger.warning(f"Message from unknown channel: {channel_id}")
                return

            # Log message receipt
            logger.info(f"📩 New message from channel {channel_id} → {pipeline_type} pipeline")

            # Create a background task for processing
            # This is the KEY to non-blocking concurrency
            if pipeline_type == 'translator':
                asyncio.create_task(self._process_translator(message))
            elif pipeline_type == 'analyst':
                asyncio.create_task(self._process_analyst(message))

        except Exception as e:
            logger.error(f"Error in handle_message: {e}", exc_info=True)
            self.metrics['errors'] += 1

    async def _process_translator(self, message: Message):
        """
        Process a message through the Translator pipeline (Pipeline A).

        This runs as an independent task and won't block other messages.

        Args:
            message: Telegram message
        """
        try:
            success = await self.translator_pipeline.process(message)
            if success:
                self.metrics['translator_processed'] += 1
                logger.info("✓ Translator pipeline completed")
            else:
                logger.warning("✗ Translator pipeline failed")
                self.metrics['errors'] += 1
                # Report error to status channel
                await self.status_reporter.report_error(
                    error_type="Translator Pipeline Failure",
                    error_message="Message processing failed in translator pipeline",
                    context={"channel_id": message.chat_id}
                )

        except Exception as e:
            logger.error(f"Error in translator pipeline: {e}", exc_info=True)
            self.metrics['errors'] += 1
            # Report error to status channel
            await self.status_reporter.report_error(
                error_type="Translator Pipeline Exception",
                error_message=str(e),
                context={"channel_id": message.chat_id}
            )

    async def _process_analyst(self, message: Message):
        """
        Process a message through the Analyst pipeline (Pipeline B).

        This runs as an independent task. PDF downloads and AI processing
        happen in the background without blocking other messages.

        Args:
            message: Telegram message
        """
        try:
            success = await self.analyst_pipeline.process(message)
            if success:
                self.metrics['analyst_processed'] += 1
                logger.info("✓ Analyst pipeline completed")
            else:
                logger.warning("✗ Analyst pipeline failed")
                self.metrics['errors'] += 1
                # Report error to status channel
                await self.status_reporter.report_error(
                    error_type="Analyst Pipeline Failure",
                    error_message="PDF processing failed in analyst pipeline",
                    context={"channel_id": message.chat_id}
                )

        except Exception as e:
            logger.error(f"Error in analyst pipeline: {e}", exc_info=True)
            self.metrics['errors'] += 1
            # Report error to status channel
            await self.status_reporter.report_error(
                error_type="Analyst Pipeline Exception",
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

**Messages Processed:** {self.metrics['total_messages']}
**Translator Pipeline:** {self.metrics['translator_processed']}
**Analyst Pipeline:** {self.metrics['analyst_processed']}
**Errors:** {self.metrics['errors']}

_Bot is running and monitoring channels_
"""
            await self.client.send_message(
                self.status_destination_id,
                report,
                parse_mode='Markdown'
            )
            logger.info("Status report sent to status destination")

        except Exception as e:
            logger.error(f"Failed to send status report: {e}")
