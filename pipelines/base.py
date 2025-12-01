from abc import ABC, abstractmethod
from typing import Any, Optional
from telethon import TelegramClient
from telethon.tl.types import Message

from utils import get_logger

logger = get_logger(__name__)


class BasePipeline(ABC):
    """
    Abstract base class for all message processing pipelines.

    All pipelines must implement the `process` method which handles
    the business logic for transforming and routing messages.
    """

    def __init__(self, client: TelegramClient, output_channel_id: str):
        """
        Initialize the pipeline.

        Args:
            client: Authenticated Telegram client
            output_channel_id: The channel ID to post processed intelligence to (format: -100...)
        """
        self.client = client
        self.output_channel_id = output_channel_id
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def process(self, message: Message) -> bool:
        """
        Process a message according to the pipeline's business logic.

        This method should:
        1. Extract and transform the message content
        2. Apply any necessary processing (translation, summarization, etc.)
        3. Forward the result to the output channel

        Args:
            message: The incoming Telegram message

        Returns:
            bool: True if processing succeeded, False otherwise
        """
        pass

    async def forward_to_target(self, text: str, file_path: Optional[str] = None,
                                 parse_mode: str = 'Markdown') -> bool:
        """
        Forward a processed message to the output channel.

        Args:
            text: The message text to send
            file_path: Optional file to attach
            parse_mode: Telegram parse mode (Markdown or HTML)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            if file_path:
                await self.client.send_file(
                    self.output_channel_id,
                    file_path,
                    caption=text,
                    parse_mode=parse_mode
                )
                self.logger.info(f"Sent message with file to output channel")
            else:
                await self.client.send_message(
                    self.output_channel_id,
                    text,
                    parse_mode=parse_mode
                )
                self.logger.info(f"Sent message to output channel")

            return True

        except Exception as e:
            self.logger.error(f"Failed to forward to output channel: {e}")
            return False

    def _get_source_info(self, message: Message) -> str:
        """
        Extract source channel information from a message.

        Args:
            message: Telegram message

        Returns:
            str: Formatted source information
        """
        try:
            chat = message.chat
            if hasattr(chat, 'title'):
                return chat.title
            elif hasattr(chat, 'username'):
                return f"@{chat.username}"
            else:
                return f"Channel {message.chat_id}"
        except Exception:
            return "Unknown Source"
