from pathlib import Path
from typing import Optional
from telethon.tl.types import Message

from .base import BasePipeline
from services import GeminiService, PDFService
from utils import truncate_text


class AnalystPipeline(BasePipeline):
    """
    Pipeline B: PDF Research Report Analysis Pipeline

    This pipeline handles messages from DTpapers channel containing equity research reports.
    It downloads PDFs and sends them directly to Gemini's File API for multimodal analysis.

    Key Feature: Uses Gemini's native PDF processing to analyze both text AND visual
    elements (charts, graphs, financial tables, valuation models) - not just text extraction.

    Cost: METERED (Gemini API - approximately $0.001-0.002 per report)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemini = GeminiService()
        self.pdf_service = PDFService()
        self.logger.info("AnalystPipeline initialized with Gemini and PDF services")

    async def process(self, message: Message) -> bool:
        """
        Process a message containing a PDF research report.

        Workflow:
        1. Check if message has a PDF attachment
        2. Download the PDF file
        3. Upload PDF to Gemini File API (multimodal analysis)
        4. Receive analysis of both text and visual elements
        5. Forward summary + original PDF to target user
        6. Cleanup temporary files

        Args:
            message: Incoming message from DTpapers channel

        Returns:
            bool: True if processing succeeded, False otherwise
        """
        pdf_path = None

        try:
            # Check for PDF document
            if not message.document:
                self.logger.debug("No document in message, skipping")
                return False

            # Verify it's a PDF
            mime_type = message.document.mime_type
            filename = message.file.name if message.file else 'document.pdf'

            if not (mime_type == 'application/pdf' or filename.endswith('.pdf')):
                self.logger.debug(f"Not a PDF document: {mime_type}, skipping")
                return False

            self.logger.info(f"Processing PDF: {filename}")

            # Download the PDF using Telethon's download method
            pdf_path = await self._download_pdf_from_message(message, filename)

            # Analyze PDF directly using Gemini's File API (multimodal)
            # This captures both text and visual elements (charts, graphs, unlock schedules)
            summary = await self.gemini.analyze_pdf_file(pdf_path)

            # Format and forward the result with the PDF attached
            formatted_message = self._format_analysis_result(
                message=message,
                filename=filename,
                summary=summary
            )

            success = await self.forward_to_target(
                text=formatted_message,
                file_path=str(pdf_path)
            )

            return success

        except Exception as e:
            self.logger.error(f"Error in AnalystPipeline.process: {e}", exc_info=True)

            # Try to send error notification to user
            try:
                error_msg = f"⚠️ Failed to process PDF report: {str(e)[:200]}"
                await self.forward_to_target(error_msg)
            except:
                pass

            return False

        finally:
            # Always cleanup temporary PDF file
            if pdf_path:
                await self.pdf_service.cleanup_file(pdf_path)

    async def _download_pdf_from_message(self, message: Message, filename: str) -> Path:
        """
        Download PDF directly from Telegram message.

        Uses Telethon's built-in download method for efficiency.

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
            # Download using Telethon's optimized method
            await self.client.download_media(message.document, file=str(file_path))
            self.logger.info(f"Downloaded PDF: {safe_name}")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to download PDF: {e}")
            raise

    def _format_analysis_result(self, message: Message, filename: str, summary: str) -> str:
        """
        Format the analysis result for forwarding.

        Args:
            message: Original Telegram message
            filename: PDF filename
            summary: Gemini-generated summary

        Returns:
            str: Formatted message in Markdown
        """
        via_source = self._format_via_source(message)

        return f"""{summary}

from: {via_source}"""
