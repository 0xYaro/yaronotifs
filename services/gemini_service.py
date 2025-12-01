import asyncio
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from config import settings
from utils import get_logger, retry_async

logger = get_logger(__name__)


class GeminiService:
    """
    Service for interacting with Google Gemini API.

    This service handles all communication with the Gemini API, including
    rate limiting, error handling, and retry logic.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini service.

        Args:
            api_key: Gemini API key (defaults to settings.GEMINI_API_KEY)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)

        # Configure the model
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        logger.info(f"Gemini service initialized with model: {settings.GEMINI_MODEL}")

    @retry_async(max_attempts=3, delay=2.0, backoff=2.0)
    async def analyze_pdf_file(self, pdf_path: Path) -> str:
        """
        Analyze a crypto research PDF using Gemini's File API with multimodal capabilities.

        This method uploads the PDF directly to Gemini, allowing it to analyze both:
        - Text content
        - Visual elements (charts, graphs, token unlock schedules)

        This is superior to text extraction as it captures visual data that would
        otherwise be lost.

        Args:
            pdf_path: Path to the PDF file to analyze

        Returns:
            str: Markdown-formatted summary with key insights

        Raises:
            Exception: If API call fails after retries
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            # Upload the PDF file to Gemini
            logger.info(f"Uploading PDF to Gemini File API: {pdf_path.name}")

            loop = asyncio.get_event_loop()
            uploaded_file = await loop.run_in_executor(
                None,
                lambda: genai.upload_file(str(pdf_path))
            )

            logger.info(f"File uploaded: {uploaded_file.name} ({uploaded_file.state.name})")

            # Wait for file processing if needed
            if uploaded_file.state.name == "PROCESSING":
                import time
                max_wait = 60  # Maximum 60 seconds
                wait_time = 0

                while uploaded_file.state.name == "PROCESSING" and wait_time < max_wait:
                    await asyncio.sleep(2)
                    wait_time += 2
                    uploaded_file = await loop.run_in_executor(
                        None,
                        lambda: genai.get_file(uploaded_file.name)
                    )

                if uploaded_file.state.name == "PROCESSING":
                    raise TimeoutError("File processing timed out")

            if uploaded_file.state.name == "FAILED":
                raise ValueError(f"File processing failed: {uploaded_file.state}")

            # Generate analysis using the uploaded file
            prompt = self._build_crypto_analysis_prompt()

            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content([uploaded_file, prompt])
            )

            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")

            summary = response.text.strip()
            logger.info(f"Generated summary: {len(summary)} characters")

            # Delete the uploaded file to save quota
            await loop.run_in_executor(
                None,
                lambda: genai.delete_file(uploaded_file.name)
            )
            logger.debug(f"Deleted uploaded file: {uploaded_file.name}")

            return summary

        except Exception as e:
            logger.error(f"Gemini File API error: {e}")
            raise

    def _build_crypto_analysis_prompt(self) -> str:
        """
        Build the analysis prompt for crypto reports.

        This prompt is designed for multimodal analysis (text + visual elements).

        Returns:
            str: Formatted prompt for Gemini
        """
        return """You are a crypto intelligence analyst. Analyze this research report comprehensively, examining BOTH textual content AND visual elements (charts, graphs, tables, token unlock schedules).

YOUR TASK:
Extract and summarize the key information in the following format:

## Executive Summary
[2-3 sentence overview of the main thesis]

## Key Alpha Opportunities
- [Specific trading or investment insights from text and charts]
- [Price targets, entry points, or strategic recommendations]
- [Insights from token unlock schedules or vesting charts]

## Catalysts & Timeline
- [Upcoming events, releases, or developments that could move price]
- [Expected timeframes for these catalysts]
- [Key dates from roadmaps or timelines in charts]

## Visual Data Insights
- [Important findings from charts, graphs, or tables]
- [Token economics or unlock schedules]
- [Market data or performance metrics from visual elements]

## Risks & Considerations
- [Key risks or counter-arguments to be aware of]

IMPORTANT:
- Analyze BOTH text and visual content thoroughly
- Pay special attention to charts, graphs, and token unlock schedules
- Extract numerical data from both text and visual elements
- Be concise but specific (aim for 400-600 words total)
- Focus on actionable intelligence, not generic analysis
- Use bullet points for clarity
- Highlight numerical data (price targets, percentages, dates, unlock schedules)
"""

    async def health_check(self) -> bool:
        """
        Verify that the Gemini API is accessible and functioning.

        Returns:
            bool: True if API is healthy, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content("Hello")
            )
            return bool(response and response.text)
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False
