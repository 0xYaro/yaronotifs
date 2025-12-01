import asyncio
from pathlib import Path
from typing import Optional, BinaryIO
import aiohttp

from PyPDF2 import PdfReader
from pypdf import PdfReader as PyPdfReader

from config import settings
from utils import get_logger, retry_async, safe_filename, format_file_size

logger = get_logger(__name__)


class PDFService:
    """
    Service for downloading and extracting text from PDF files.

    This service handles PDF operations asynchronously to prevent blocking
    the main event loop during large file downloads.
    """

    def __init__(self):
        self.temp_dir = settings.TEMP_DIR
        self.max_size_mb = settings.MAX_PDF_SIZE_MB
        self.timeout = settings.REQUEST_TIMEOUT

    @retry_async(max_attempts=3, delay=2.0, backoff=2.0)
    async def download_pdf(self, url: str, filename: Optional[str] = None) -> Path:
        """
        Download a PDF file from a URL.

        Args:
            url: The URL to download from
            filename: Optional custom filename (will be sanitized)

        Returns:
            Path: Path to the downloaded file

        Raises:
            ValueError: If file is too large or invalid
            aiohttp.ClientError: If download fails
        """
        if not filename:
            filename = safe_filename(url.split('/')[-1] or 'document.pdf')
        else:
            filename = safe_filename(filename)

        if not filename.endswith('.pdf'):
            filename += '.pdf'

        file_path = self.temp_dir / filename

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()

                    # Check file size from headers
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        size_mb = int(content_length) / (1024 * 1024)
                        if size_mb > self.max_size_mb:
                            raise ValueError(
                                f"PDF too large: {size_mb:.1f}MB (max: {self.max_size_mb}MB)"
                            )

                    # Download file in chunks to avoid blocking
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    total_size = 0

                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            total_size += len(chunk)

                            # Check size during download
                            if total_size > self.max_size_mb * 1024 * 1024:
                                file_path.unlink(missing_ok=True)
                                raise ValueError(f"PDF exceeds size limit during download")

                            f.write(chunk)

            logger.info(f"Downloaded PDF: {filename} ({format_file_size(total_size)})")
            return file_path

        except Exception as e:
            logger.error(f"Failed to download PDF from {url}: {e}")
            file_path.unlink(missing_ok=True)
            raise

    async def extract_text(self, pdf_path: Path) -> str:
        """
        Extract text content from a PDF file.

        This method runs in a thread pool to avoid blocking the event loop
        with CPU-intensive PDF parsing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            str: Extracted text content

        Raises:
            FileNotFoundError: If PDF doesn't exist
            Exception: If extraction fails
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            # Run PDF extraction in thread pool (CPU-intensive operation)
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._extract_text_sync, pdf_path)

            if not text or len(text.strip()) < 100:
                logger.warning(f"Extracted text is too short or empty: {len(text)} chars")

            logger.info(f"Extracted {len(text)} characters from {pdf_path.name}")
            return text

        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            raise

    def _extract_text_sync(self, pdf_path: Path) -> str:
        """
        Synchronous PDF text extraction (runs in thread pool).

        Tries multiple extraction libraries for better compatibility.

        Args:
            pdf_path: Path to PDF file

        Returns:
            str: Extracted text
        """
        text_parts = []

        # Try PyPDF2 first (more compatible with encrypted PDFs)
        try:
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or '')
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed, trying pypdf: {e}")

            # Fallback to pypdf
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPdfReader(file)
                    for page in reader.pages:
                        text_parts.append(page.extract_text() or '')
            except Exception as e2:
                logger.error(f"All PDF extraction methods failed: {e2}")
                raise

        return '\n\n'.join(text_parts).strip()

    async def cleanup_file(self, file_path: Path) -> None:
        """
        Delete a temporary PDF file.

        Args:
            file_path: Path to file to delete
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temporary file: {file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")

    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary PDF files.

        Args:
            max_age_hours: Maximum age of files to keep (in hours)

        Returns:
            int: Number of files deleted
        """
        import time

        deleted_count = 0
        cutoff_time = time.time() - (max_age_hours * 3600)

        try:
            for file_path in self.temp_dir.glob('*.pdf'):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old PDF files")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        return deleted_count
