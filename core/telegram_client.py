import asyncio
from pathlib import Path
from typing import Optional, Callable

from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError
)
from telethon.tl.types import Message

from config import settings
from utils import get_logger

logger = get_logger(__name__)


class TelegramClientWrapper:
    """
    Wrapper around Telethon TelegramClient with automatic reconnection and error handling.

    This class manages the Telegram client lifecycle, including:
    - Session management
    - Auto-reconnection on network failures
    - Event handler registration
    - Graceful shutdown
    """

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_name: Optional[str] = None,
        phone: Optional[str] = None
    ):
        """
        Initialize the Telegram client wrapper.

        Args:
            api_id: Telegram API ID (defaults to settings)
            api_hash: Telegram API hash (defaults to settings)
            session_name: Session file name (defaults to settings)
            phone: Phone number for authentication (defaults to settings)
        """
        self.api_id = api_id or settings.TELEGRAM_API_ID
        self.api_hash = api_hash or settings.TELEGRAM_API_HASH
        self.session_name = session_name or settings.SESSION_NAME
        self.phone = phone or settings.TELEGRAM_PHONE

        # Session file path
        self.session_path = settings.BASE_DIR / f"{self.session_name}.session"

        # Initialize the client
        self.client = TelegramClient(
            str(settings.BASE_DIR / self.session_name),
            self.api_id,
            self.api_hash,
            connection_retries=5,
            retry_delay=2,
            auto_reconnect=True,
            flood_sleep_threshold=60
        )

        self._running = False
        self._message_handlers = []

        logger.info(f"TelegramClientWrapper initialized (session: {self.session_name})")

    async def start(self, force_login: bool = False) -> bool:
        """
        Start the Telegram client and authenticate if necessary.

        Args:
            force_login: Force interactive login even if session exists

        Returns:
            bool: True if started successfully, False otherwise
        """
        try:
            logger.info("Starting Telegram client...")

            if force_login or not self.session_path.exists():
                logger.warning("Session file not found or force_login=True")
                logger.warning("Please run create_session.py first to authenticate locally")
                return False

            # Connect using existing session
            await self.client.start(phone=self.phone)

            # Verify authentication
            if not await self.client.is_user_authorized():
                logger.error("Session file exists but user is not authorized")
                logger.error("Please delete the session file and run create_session.py again")
                return False

            # Get user info
            me = await self.client.get_me()
            logger.info(f"✓ Connected as: {me.first_name} (@{me.username or 'N/A'})")

            self._running = True
            return True

        except Exception as e:
            logger.error(f"Failed to start Telegram client: {e}", exc_info=True)
            return False

    async def stop(self):
        """
        Stop the Telegram client gracefully.
        """
        logger.info("Stopping Telegram client...")
        self._running = False

        try:
            if self.client.is_connected():
                await self.client.disconnect()
            logger.info("✓ Telegram client stopped")
        except Exception as e:
            logger.error(f"Error during client shutdown: {e}")

    def is_running(self) -> bool:
        """
        Check if the client is running.

        Returns:
            bool: True if running, False otherwise
        """
        return self._running and self.client.is_connected()

    def on_new_message(self, chat_ids: list[int], handler: Callable):
        """
        Register a handler for new messages from specific chats.

        Args:
            chat_ids: List of chat IDs to monitor
            handler: Async function to handle messages
        """
        @self.client.on(events.NewMessage(chats=chat_ids))
        async def message_wrapper(event):
            try:
                # Process in background to avoid blocking other messages
                asyncio.create_task(handler(event.message))
            except Exception as e:
                logger.error(f"Error in message handler: {e}", exc_info=True)

        self._message_handlers.append(message_wrapper)
        logger.info(f"Registered message handler for {len(chat_ids)} chat(s)")

    async def run_until_disconnected(self):
        """
        Run the client until it's disconnected.

        This method includes automatic reconnection logic.
        """
        reconnect_delay = 5
        max_reconnect_delay = 300  # 5 minutes

        while self._running:
            try:
                logger.info("Client is running. Listening for messages...")
                await self.client.run_until_disconnected()

            except FloodWaitError as e:
                logger.warning(f"Flood wait: sleeping for {e.seconds} seconds")
                await asyncio.sleep(e.seconds)

            except Exception as e:
                logger.error(f"Client disconnected: {e}")

                if not self._running:
                    break

                logger.info(f"Attempting to reconnect in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)

                # Exponential backoff
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

                # Try to reconnect
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                        logger.info("✓ Reconnected successfully")
                        reconnect_delay = 5  # Reset delay on success
                except Exception as reconnect_error:
                    logger.error(f"Reconnection failed: {reconnect_error}")

    async def send_message(self, user_id: str, text: str, **kwargs):
        """
        Send a message to a user or channel.

        Args:
            user_id: Target user ID (positive), channel ID (negative, e.g., -100...), or username
            text: Message text
            **kwargs: Additional arguments for send_message
        """
        return await self.client.send_message(user_id, text, **kwargs)

    async def send_file(self, user_id: str, file, **kwargs):
        """
        Send a file to a user or channel.

        Args:
            user_id: Target user ID (positive), channel ID (negative, e.g., -100...), or username
            file: File path or file object
            **kwargs: Additional arguments for send_file
        """
        return await self.client.send_file(user_id, file, **kwargs)

    async def download_media(self, message: Message, file: str):
        """
        Download media from a message.

        Args:
            message: Telegram message
            file: Target file path
        """
        return await self.client.download_media(message, file=file)
