from typing import Optional
from telethon.tl.types import Message
from deep_translator import GoogleTranslator

from .base import BasePipeline
from utils import detect_chinese, retry_async


class TranslatorPipeline(BasePipeline):
    """
    Pipeline A: Chinese-to-English Translation Pipeline

    This pipeline handles messages from Chinese news channels (BWEnews, Foresight News).
    It detects Chinese text and translates it to English using a free translation service.

    Cost: FREE (uses Google Translate via deep-translator)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.translator = GoogleTranslator(source='zh-CN', target='en')
        self.logger.info("TranslatorPipeline initialized with GoogleTranslator")

    async def process(self, message: Message) -> bool:
        """
        Process a message from a Chinese news channel.

        Workflow:
        1. Extract text from message
        2. Detect if Chinese characters are present
        3. If yes, translate to English
        4. Forward translated text with source attribution

        Args:
            message: Incoming message from monitored channel

        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            # Extract message text
            text = self._extract_text(message)
            if not text:
                self.logger.debug("No text content in message, skipping")
                return False

            # Check if translation is needed
            if not detect_chinese(text):
                self.logger.debug("No Chinese detected, forwarding original text")
                return await self._forward_original(message, text)

            # Translate the text
            translated_text = await self._translate_text(text)
            if not translated_text:
                self.logger.warning("Translation failed, forwarding original")
                return await self._forward_original(message, text)

            # Format and forward the result
            source = self._get_source_info(message)
            formatted_message = self._format_translation_result(
                source=source,
                original=text,
                translated=translated_text
            )

            return await self.forward_to_target(formatted_message)

        except Exception as e:
            self.logger.error(f"Error in TranslatorPipeline.process: {e}", exc_info=True)
            return False

    def _extract_text(self, message: Message) -> Optional[str]:
        """
        Extract text content from a message.

        Args:
            message: Telegram message

        Returns:
            str: Extracted text or None
        """
        if message.text:
            return message.text.strip()
        elif message.message:
            return message.message.strip()
        return None

    @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
    async def _translate_text(self, text: str, max_chunk_size: int = 5000) -> Optional[str]:
        """
        Translate Chinese text to English.

        Google Translate has a character limit, so long texts are split into chunks.

        Args:
            text: Text to translate
            max_chunk_size: Maximum characters per translation request

        Returns:
            str: Translated text or None if failed
        """
        try:
            # For short texts, translate directly
            if len(text) <= max_chunk_size:
                import asyncio
                loop = asyncio.get_event_loop()
                translated = await loop.run_in_executor(
                    None,
                    lambda: self.translator.translate(text)
                )
                return translated

            # For long texts, split into chunks
            chunks = self._split_into_chunks(text, max_chunk_size)
            translated_chunks = []

            import asyncio
            loop = asyncio.get_event_loop()

            for chunk in chunks:
                translated_chunk = await loop.run_in_executor(
                    None,
                    lambda c=chunk: self.translator.translate(c)
                )
                translated_chunks.append(translated_chunk)
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

            return '\n\n'.join(translated_chunks)

        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return None

    def _split_into_chunks(self, text: str, max_size: int) -> list[str]:
        """
        Split text into chunks at sentence boundaries.

        Args:
            text: Text to split
            max_size: Maximum chunk size

        Returns:
            list: List of text chunks
        """
        if len(text) <= max_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first, then sentences
        paragraphs = text.split('\n')

        for para in paragraphs:
            if len(current_chunk) + len(para) + 1 <= max_size:
                current_chunk += para + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + '\n'

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _format_translation_result(self, source: str, original: str,
                                     translated: str) -> str:
        """
        Format the translation result for forwarding.

        Args:
            source: Source channel name
            original: Original Chinese text
            translated: Translated English text

        Returns:
            str: Formatted message in Markdown
        """
        # Truncate original text if too long (for reference only)
        original_preview = original[:200] + "..." if len(original) > 200 else original

        return f"""**📰 {source}**

{translated}

---
_Original (CN):_ {original_preview}
"""

    async def _forward_original(self, message: Message, text: str) -> bool:
        """
        Forward the original message without translation.

        Args:
            message: Original message
            text: Message text

        Returns:
            bool: True if forwarded successfully
        """
        source = self._get_source_info(message)
        formatted = f"**📰 {source}**\n\n{text}"
        return await self.forward_to_target(formatted)
