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
        # OUTPUT_CHANNEL_ID: Where processed intelligence is posted (channel ID, format: -100...)
        self.OUTPUT_CHANNEL_ID = os.getenv('OUTPUT_CHANNEL_ID', '')

        # STATUS_DESTINATION_ID: Optional - where bot metrics/status reports are sent
        # Can be a user ID or channel ID. Leave empty to disable status reports.
        self.STATUS_DESTINATION_ID = os.getenv('STATUS_DESTINATION_ID', '')

        # AI Configuration
        self.GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
        self.GEMINI_MODEL = 'models/gemini-2.5-flash'

        # Application Settings
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

        # Channel Definitions and Routing
        # Pipeline A: Chinese News Channels (Translation)
        self.TRANSLATOR_CHANNELS: List[int] = [
            -1001279597711,    # BWEnews
            -1001526765830,    # Foresight News
            -1003309883285,    # Yaro Notifs [Test Channel]
        ]

        # Pipeline B: PDF Analysis Channels (Gemini Summarization)
        self.ANALYST_CHANNELS: List[int] = [
            -1001750561680,    # DTpapers
        ]

        # All monitored channels
        self.ALL_CHANNELS = self.TRANSLATOR_CHANNELS + self.ANALYST_CHANNELS

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

    def get_pipeline_for_channel(self, channel_id: int) -> str:
        """
        Determine which processing pipeline to use for a given channel.

        Args:
            channel_id: The Telegram channel ID

        Returns:
            str: 'translator', 'analyst', or 'unknown'
        """
        if channel_id in self.TRANSLATOR_CHANNELS:
            return 'translator'
        elif channel_id in self.ANALYST_CHANNELS:
            return 'analyst'
        else:
            return 'unknown'


# Global settings instance
settings = Settings()
