from pathlib import Path
from typing import Optional, Dict, Any
from telethon.tl.types import Message

from .base import BasePipeline
from services import GeminiService, PDFService
from utils import detect_chinese


class UnifiedPipeline(BasePipeline):
    """
    Unified Message Processing Pipeline

    This pipeline replaces the separate TranslatorPipeline and AnalystPipeline with
    a single, intelligent LLM-powered processor that:

    1. Analyzes incoming content (text, PDFs, images, etc.)
    2. Determines what processing is needed (translation, summarization, analysis)
    3. Executes all necessary processing steps via LLM
    4. Formats and forwards unified output

    Key advantages:
    - Single code path for all message types
    - LLM makes intelligent decisions about processing
    - Extensible to new input sources (web scrapers, RSS, etc.)
    - Consistent output format
    - Easier to maintain

    Cost: Uses Gemini for all processing (~$0.0001-0.001 per message)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemini = GeminiService()
        self.pdf_service = PDFService()
        self.logger.info("UnifiedPipeline initialized with Gemini service")

    async def process(self, message: Message) -> bool:
        """
        Process any incoming message through the unified pipeline.

        The LLM automatically determines what processing is needed based on:
        - Content type (text, PDF, image, etc.)
        - Language detection
        - Content analysis

        Workflow:
        1. Extract content from message
        2. Detect content type and characteristics
        3. Route to appropriate processing method
        4. Format and forward unified output

        Args:
            message: Incoming message from any source

        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            # Check for PDF document first
            if message.document:
                return await self._process_document(message)

            # Otherwise process as text message
            elif message.text or message.message:
                return await self._process_text(message)

            else:
                self.logger.debug("Message has no processable content, skipping")
                return False

        except Exception as e:
            self.logger.error(f"Error in UnifiedPipeline.process: {e}", exc_info=True)

            # Try to send error notification
            try:
                error_msg = f"⚠️ Failed to process message: {str(e)[:200]}"
                await self.forward_to_target(error_msg)
            except:
                pass

            return False

    async def _process_text(self, message: Message) -> bool:
        """
        Process text messages using LLM.

        The LLM will:
        - Detect language and translate if needed
        - Summarize if content is long
        - Extract key insights
        - Format for output

        Args:
            message: Text message

        Returns:
            bool: True if successful
        """
        try:
            # Extract text
            text = self._extract_text(message)
            if not text:
                self.logger.debug("No text content in message")
                return False

            self.logger.info(f"Processing text message ({len(text)} chars)")

            # Detect if Chinese text is present
            has_chinese = detect_chinese(text)

            # Build context for LLM
            context = self._build_message_context(message, has_chinese)

            # Process with LLM
            processed_content = await self.gemini.process_text_message(
                text=text,
                context=context
            )

            if not processed_content:
                self.logger.warning("LLM returned empty response")
                return False

            # Format and forward
            formatted_message = self._format_output(
                content=processed_content,
                message=message,
                content_type="text"
            )

            return await self.forward_to_target(formatted_message)

        except Exception as e:
            self.logger.error(f"Error processing text message: {e}", exc_info=True)
            return False

    async def _process_document(self, message: Message) -> bool:
        """
        Process document messages (PDFs, images, etc.) using LLM.

        The LLM will:
        - Analyze document content (text + visual elements)
        - Determine document type (research report, news article, etc.)
        - Extract key insights
        - Provide contextual analysis

        Args:
            message: Message with document attachment

        Returns:
            bool: True if successful
        """
        pdf_path = None

        try:
            # Verify it's a PDF (can be extended to other document types)
            mime_type = message.document.mime_type
            filename = message.file.name if message.file else 'document.pdf'

            if not (mime_type == 'application/pdf' or filename.endswith('.pdf')):
                self.logger.debug(f"Not a PDF document: {mime_type}, skipping")
                return False

            self.logger.info(f"Processing PDF document: {filename}")

            # Download the PDF
            pdf_path = await self._download_pdf_from_message(message, filename)

            # Build context for LLM
            context = self._build_message_context(message, has_chinese=False)

            # Process with LLM (multimodal - analyzes text + visuals)
            processed_content = await self.gemini.process_document(
                file_path=pdf_path,
                context=context
            )

            if not processed_content:
                self.logger.warning("LLM returned empty response for document")
                return False

            # Format and forward with PDF attached
            formatted_message = self._format_output(
                content=processed_content,
                message=message,
                content_type="document"
            )

            success = await self.forward_to_target(
                text=formatted_message,
                file_path=str(pdf_path)
            )

            return success

        except Exception as e:
            self.logger.error(f"Error processing document: {e}", exc_info=True)
            return False

        finally:
            # Always cleanup temporary files
            if pdf_path:
                await self.pdf_service.cleanup_file(pdf_path)

    async def _download_pdf_from_message(self, message: Message, filename: str) -> Path:
        """
        Download PDF from Telegram message.

        Args:
            message: Telegram message with document
            filename: Target filename

        Returns:
            Path: Path to downloaded file

        Raises:
            Exception: If download fails
        """
        from utils import safe_filename

        safe_name = safe_filename(filename)
        file_path = self.pdf_service.temp_dir / safe_name

        try:
            await self.client.download_media(message.document, file=str(file_path))
            self.logger.info(f"Downloaded PDF: {safe_name}")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to download PDF: {e}")
            raise

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

    def _build_message_context(self, message: Message, has_chinese: bool = False) -> Dict[str, Any]:
        """
        Build contextual information about the message for LLM processing.

        Args:
            message: Telegram message
            has_chinese: Whether Chinese text was detected

        Returns:
            dict: Context information
        """
        source_name = self._get_source_info(message)

        return {
            "source_channel": source_name,
            "channel_id": message.chat_id,
            "has_chinese": has_chinese,
            "message_link": self._get_message_link(message),
        }

    def _format_output(self, content: str, message: Message, content_type: str) -> str:
        """
        Format the processed content for output.

        Args:
            content: Processed content from LLM
            message: Original message
            content_type: Type of content ("text" or "document")

        Returns:
            str: Formatted message in Markdown
        """
        via_source = self._format_via_source(message)

        return f"""{content}

from: {via_source}"""
