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

    def _get_message_link(self, message: Message) -> Optional[str]:
        """
        Generate a Telegram message link for the given message.

        Args:
            message: Telegram message

        Returns:
            str: Message link in format t.me/... or None if unable to generate
        """
        try:
            chat = message.chat
            message_id = message.id

            # For channels/groups with username
            if hasattr(chat, 'username') and chat.username:
                return f"https://t.me/{chat.username}/{message_id}"

            # For channels/groups without username (private, use ID)
            # Format: t.me/c/{channel_id_without_prefix}/{message_id}
            chat_id = str(chat.id)
            if chat_id.startswith('-100'):
                # Remove the -100 prefix for private channel links
                channel_id = chat_id[4:]
                return f"https://t.me/c/{channel_id}/{message_id}"

            return None
        except Exception as e:
            self.logger.warning(f"Failed to generate message link: {e}")
            return None

    def _format_via_source(self, message: Message) -> str:
        """
        Format the "via Channel_Name (link)" footer for messages.

        Args:
            message: Telegram message

        Returns:
            str: Formatted source attribution with hyperlink
        """
        channel_name = self._get_source_info(message)
        message_link = self._get_message_link(message)

        if message_link:
            return f"via [{channel_name}]({message_link})"
        else:
            return f"via {channel_name}"
