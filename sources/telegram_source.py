"""
Telegram source provider.

Wraps the existing Telegram client to conform to the BaseSource interface.
"""

from typing import AsyncIterator, List
from telethon.tl.types import Message
import asyncio

from .base import BaseSource, SourceMessage
from core import TelegramClientWrapper
from utils import get_logger

logger = get_logger(__name__)


class TelegramSource(BaseSource):
    """
    Telegram channel source provider.

    This wraps the existing TelegramClientWrapper to conform to the
    modular source interface, allowing it to coexist with other sources.
    """

    def __init__(
        self,
        name: str = "Telegram",
        source_id: str = "telegram",
        monitored_channels: List[int] = None
    ):
        """
        Initialize Telegram source.

        Args:
            name: Human-readable name
            source_id: Unique identifier
            monitored_channels: List of channel IDs to monitor
        """
        super().__init__(name, source_id)
        self.monitored_channels = monitored_channels or []
        self.client: TelegramClientWrapper = None
        self.message_queue: asyncio.Queue = asyncio.Queue()

    async def start(self) -> bool:
        """
        Start the Telegram client and begin monitoring channels.

        Returns:
            bool: True if started successfully
        """
        try:
            self.client = TelegramClientWrapper()

            if not await self.client.start():
                logger.error("Failed to start Telegram client")
                return False

            # Refresh dialog cache
            await self.client.client.get_dialogs()

            # Register message handler
            self.client.on_new_message(
                chat_ids=self.monitored_channels,
                handler=self._on_message
            )

            self.running = True
            logger.info(f"✓ TelegramSource started, monitoring {len(self.monitored_channels)} channels")
            return True

        except Exception as e:
            logger.error(f"Failed to start TelegramSource: {e}", exc_info=True)
            return False

    async def stop(self) -> None:
        """
        Stop the Telegram client and cleanup.
        """
        self.running = False
        if self.client:
            await self.client.stop()
        logger.info("TelegramSource stopped")

    async def _on_message(self, message: Message) -> None:
        """
        Callback for new Telegram messages.

        Converts Telegram message to SourceMessage and queues it.
        """
        import time
        start_time = time.time()

        try:
            logger.info(f"⏱️ [TIMING] Event triggered for message {message.id} from chat {message.chat_id}")

            convert_start = time.time()
            source_message = await self._convert_telegram_message(message)
            convert_time = time.time() - convert_start

            logger.info(f"⏱️ [TIMING] Message conversion took {convert_time:.2f}s")

            await self.message_queue.put(source_message)

            total_time = time.time() - start_time
            logger.info(f"⏱️ [TIMING] Total event handling took {total_time:.2f}s")
        except Exception as e:
            logger.error(f"Error converting Telegram message: {e}", exc_info=True)

    async def _convert_telegram_message(self, message: Message) -> SourceMessage:
        """
        Convert a Telegram message to a SourceMessage.

        Args:
            message: Telethon Message object

        Returns:
            SourceMessage: Standardized message object
        """
        from pathlib import Path
        from services import PDFService
        from utils import safe_filename

        # Get source info
        source_name = "Telegram"
        try:
            chat = await message.get_chat()
            source_name = getattr(chat, 'title', 'Telegram')
        except:
            pass

        # Get message link
        url = None
        if hasattr(message, 'chat_id') and hasattr(message, 'id'):
            chat_id = str(message.chat_id).replace('-100', '')
            url = f"https://t.me/c/{chat_id}/{message.id}"

        # Extract text
        text = message.text or message.message

        # Handle documents - download if it's a PDF
        document_path = None
        document_mime_type = None
        if message.document:
            document_mime_type = message.document.mime_type
            filename = message.file.name if message.file else 'document.pdf'

            # Download PDF documents immediately for processing
            if document_mime_type == 'application/pdf' or filename.endswith('.pdf'):
                try:
                    pdf_service = PDFService()
                    safe_name = safe_filename(filename)
                    file_path = pdf_service.temp_dir / safe_name

                    await self.client.client.download_media(message.document, file=str(file_path))
                    document_path = file_path
                    logger.info(f"Downloaded PDF: {safe_name}")
                except Exception as e:
                    logger.error(f"Failed to download PDF: {e}")
                    # Continue without document - text might still be processable

        return SourceMessage(
            text=text,
            source_name=source_name,
            source_id=f"telegram_{message.chat_id}",
            timestamp=message.date,
            document_path=document_path,
            document_mime_type=document_mime_type,
            url=url,
            message_id=str(message.id),
            metadata={
                'chat_id': message.chat_id,
                'telegram_message': message  # Keep original for reference
            }
        )

    async def get_messages(self) -> AsyncIterator[SourceMessage]:
        """
        Get messages from the Telegram source as they arrive.

        Yields:
            SourceMessage: Standardized message objects
        """
        while self.running:
            try:
                # Wait for messages with timeout to allow clean shutdown
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error getting Telegram message: {e}")
                await asyncio.sleep(1)
