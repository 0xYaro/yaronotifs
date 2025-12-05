import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """
    Centralized configuration management for the Telegram Intelligence Bot.

    This class loads all configuration from environment variables and provides
    typed access to application settings. It also defines the channel routing rules.
    """

    def __init__(self):
        # Base directories
        self.BASE_DIR = Path(__file__).parent.parent
        self.TEMP_DIR = Path(os.getenv('TEMP_DIR', './temp'))
        self.TEMP_DIR.mkdir(exist_ok=True)

        # Telegram Configuration
        self.TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
        self.TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
        self.TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE', '')
        self.SESSION_NAME = os.getenv('SESSION_NAME', 'yaronotifs_session')

        # Output Destinations
        # OUTPUT_CHANNEL_ID: Default/fallback output channel (kept for backward compatibility)
        self.OUTPUT_CHANNEL_ID = os.getenv('OUTPUT_CHANNEL_ID', '')

        # Smart Channel Routing: Route messages to different output channels based on source
        self.CRYPTO_OUTPUT_CHANNEL = os.getenv('CRYPTO_OUTPUT_CHANNEL', '@cryptonotifs')
        self.EQUITIES_OUTPUT_CHANNEL = os.getenv('EQUITIES_OUTPUT_CHANNEL', '@equitiesnotifs')

        # STATUS_DESTINATION_ID: Optional - where bot metrics/status reports are sent
        # Can be a user ID or channel ID. Leave empty to disable status reports.
        self.STATUS_DESTINATION_ID = os.getenv('STATUS_DESTINATION_ID', '')

        # AI Configuration
        self.GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
        self.GEMINI_MODEL = 'models/gemini-2.5-flash'

        # Application Settings
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

        # Channel Definitions
        # All channels are processed through the UnifiedPipeline
        # The LLM intelligently determines what processing is needed
        self.MONITORED_CHANNELS: List[int] = [
            -1001279597711,    # BWEnews (Chinese news)
            -1001526765830,    # Foresight News (Chinese news)
            -1001750561680,    # DTpapers (Equity research PDFs)
            -1003309883285,    # Yaro Notifs [Test Channel]
        ]

        # Channel Routing Map: Maps source channel IDs to output channels
        # This enables smart routing where crypto news goes to crypto channel
        # and equity research goes to equities channel
        self.CHANNEL_ROUTING: Dict[int, str] = {
            -1001279597711: self.CRYPTO_OUTPUT_CHANNEL,    # BWEnews → Crypto
            -1001526765830: self.CRYPTO_OUTPUT_CHANNEL,    # Foresight News → Crypto
            -1001750561680: self.EQUITIES_OUTPUT_CHANNEL,  # DTpapers → Equities
            -1003309883285: self.CRYPTO_OUTPUT_CHANNEL,    # Test Channel → Crypto (for testing)
        }

        # Retry Configuration
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 2  # seconds
        self.BACKOFF_MULTIPLIER = 2

        # File Processing Limits
        self.MAX_PDF_SIZE_MB = 50
        self.REQUEST_TIMEOUT = 60  # seconds

    def validate(self) -> bool:
        """
        Validate that all required configuration is present.

        Returns:
            bool: True if configuration is valid, raises ValueError otherwise
        """
        errors = []

        if not self.TELEGRAM_API_ID or self.TELEGRAM_API_ID == 0:
            errors.append("TELEGRAM_API_ID is required")

        if not self.TELEGRAM_API_HASH:
            errors.append("TELEGRAM_API_HASH is required")

        if not self.TELEGRAM_PHONE:
            errors.append("TELEGRAM_PHONE is required")

        if not self.OUTPUT_CHANNEL_ID:
            errors.append("OUTPUT_CHANNEL_ID is required")

        if not self.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        return True

    def is_monitored_channel(self, channel_id: int) -> bool:
        """
        Check if a channel is being monitored.

        Args:
            channel_id: The Telegram channel ID

        Returns:
            bool: True if channel is monitored, False otherwise
        """
        return channel_id in self.MONITORED_CHANNELS

    def get_output_channel(self, source_channel_id: int) -> str:
        """
        Get the appropriate output channel for a given source channel.

        Uses smart routing to direct crypto news to crypto channel
        and equity research to equities channel.

        Args:
            source_channel_id: ID of the source channel

        Returns:
            str: Output channel ID/username to forward messages to
        """
        # Use routing map if available, otherwise fall back to default
        return self.CHANNEL_ROUTING.get(source_channel_id, self.OUTPUT_CHANNEL_ID)


# Global settings instance
settings = Settings()
