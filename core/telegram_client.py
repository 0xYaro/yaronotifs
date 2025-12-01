import asyncio
import os
import time
from pathlib import Path
from typing import Optional, Callable

from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
    AuthKeyDuplicatedError
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
        self.lock_file = settings.BASE_DIR / f"{self.session_name}.lock"

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

            # Check for existing lock file (prevents multiple instances)
            if self._check_existing_lock():
                logger.error("=" * 60)
                logger.error("CRITICAL: Another instance of this bot is already running!")
                logger.error("Running multiple instances with the same session will cause:")
                logger.error("  - Telegram session conflicts (AuthKeyDuplicatedError)")
                logger.error("  - IP address bans from Telegram")
                logger.error("  - Account suspension")
                logger.error("")
                logger.error("Please stop the other instance before starting this one.")
                logger.error(f"Lock file: {self.lock_file}")
                logger.error("=" * 60)
                return False

            if force_login or not self.session_path.exists():
                logger.warning("Session file not found or force_login=True")
                logger.warning("Please run create_session.py first to authenticate locally")
                return False

            # Create lock file to prevent concurrent access
            self._create_lock_file()

            # Connect using existing session
            await self.client.start(phone=self.phone)

            # Verify authentication
            if not await self.client.is_user_authorized():
                logger.error("Session file exists but user is not authorized")
                logger.error("Please delete the session file and run create_session.py again")
                self._remove_lock_file()
                return False

            # Get user info
            me = await self.client.get_me()
            logger.info(f"✓ Connected as: {me.first_name} (@{me.username or 'N/A'})")

            self._running = True
            return True

        except AuthKeyDuplicatedError as e:
            logger.error("=" * 60)
            logger.error("CRITICAL: Session is being used from another IP address!")
            logger.error("This happens when the same session file is used simultaneously")
            logger.error("from multiple locations (e.g., local machine + AWS server).")
            logger.error("")
            logger.error("ACTION REQUIRED:")
            logger.error("  1. Stop ALL other instances of this bot")
            logger.error("  2. Wait 60 seconds for Telegram to release the session")
            logger.error("  3. Only run ONE instance at a time")
            logger.error("  4. DO NOT copy session files between machines")
            logger.error("=" * 60)
            self._remove_lock_file()
            return False
        except Exception as e:
            logger.error(f"Failed to start Telegram client: {e}", exc_info=True)
            self._remove_lock_file()
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
        finally:
            # Always remove lock file on shutdown
            self._remove_lock_file()

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
        print(f"DEBUG: on_new_message() registering for {len(chat_ids)} chats: {chat_ids}")

        async def message_wrapper(event):
            print(f"DEBUG: !!!EVENT TRIGGERED!!! Chat: {event.chat_id}, Message ID: {event.message.id}")
            try:
                # Call handler directly (not in background task)
                await handler(event.message)
                print(f"DEBUG: Handler completed successfully")
            except Exception as e:
                logger.error(f"Error in message handler: {e}", exc_info=True)
                print(f"DEBUG: ERROR in handler: {e}")
                import traceback
                traceback.print_exc()

        # Use add_event_handler instead of decorator - works better with running clients
        self.client.add_event_handler(
            message_wrapper,
            events.NewMessage(chats=chat_ids, incoming=True)
        )

        self._message_handlers.append(message_wrapper)
        print(f"DEBUG: Handler registered successfully for chats: {chat_ids}")
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

    def _check_existing_lock(self) -> bool:
        """
        Check if a lock file exists and is still valid.

        Returns:
            bool: True if another instance is running, False otherwise
        """
        if not self.lock_file.exists():
            return False

        try:
            # Read lock file to get PID and timestamp
            with open(self.lock_file, 'r') as f:
                data = f.read().strip().split('\n')
                if len(data) >= 2:
                    pid = int(data[0])
                    timestamp = float(data[1])

                    # Check if the process is still running
                    try:
                        os.kill(pid, 0)  # Signal 0 just checks if process exists
                        # Process exists
                        age_hours = (time.time() - timestamp) / 3600
                        if age_hours > 24:
                            # Stale lock file (older than 24 hours), remove it
                            logger.warning(f"Removing stale lock file (age: {age_hours:.1f} hours)")
                            self.lock_file.unlink()
                            return False
                        return True
                    except ProcessLookupError:
                        # Process doesn't exist, remove stale lock file
                        logger.warning("Removing lock file from dead process")
                        self.lock_file.unlink()
                        return False
        except Exception as e:
            logger.warning(f"Error checking lock file: {e}")
            # If we can't read the lock file, remove it
            try:
                self.lock_file.unlink()
            except:
                pass
            return False

        return False

    def _create_lock_file(self):
        """
        Create a lock file with current process ID and timestamp.
        """
        try:
            with open(self.lock_file, 'w') as f:
                f.write(f"{os.getpid()}\n")
                f.write(f"{time.time()}\n")
            logger.info(f"Created lock file: {self.lock_file}")
        except Exception as e:
            logger.error(f"Failed to create lock file: {e}")

    def _remove_lock_file(self):
        """
        Remove the lock file when shutting down.
        """
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
                logger.info("Removed lock file")
        except Exception as e:
            logger.warning(f"Failed to remove lock file: {e}")
