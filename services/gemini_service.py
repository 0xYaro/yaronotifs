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
            prompt = self._build_equity_analysis_prompt()

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

    def _build_equity_analysis_prompt(self) -> str:
        """
        Build the analysis prompt for equity research reports.

        This prompt is designed for multimodal analysis (text + visual elements).

        Returns:
            str: Formatted prompt for Gemini
        """
        return """# Role: Senior Market Intelligence Analyst (Buy-Side)
**Objective:** Synthesize the attached Equity Research Report into a "Coverage Note" for the CIO.
**Constraint:** Do not just summarize the PDF. You must **contextualize** it against the current market environment using live data.

---

### **Part 1: The "Delta" (What Changed?)**
* **The Trigger:** Why was this report written? (Earnings release, M&A rumor, Analyst Day, or just a maintenance update?)
* **The Core Update:** What is the single most important new data point in this file?
* **Consensus Check:** Does this report fundamentally change the street's view, or is it reinforcing the echo chamber?

### **Part 2: Live Context Cross-Reference (CRITICAL)**
* **Instruction:** Use your browser/search tools to check the following against *live* market data:
    1.  **Price Action:** Look at the ticker's performance over the last 5 days. Did the market *already* react to this news before the report was published?
    2.  **Sector Sentiment:** Search for "[Sector Name] ETF performance YTD" or recent news. Is this stock moving with its sector or diverging?
    3.  **Fact Check:** If the report claims a "catalyst" is coming (e.g., "FDA approval next week"), verify if that date has shifted or passed.
* **Output:** Explicitly state: *"Live Check: The report is bullish, BUT the stock is down 5% this week, suggesting the market disagrees."*

### **Part 3: Key Insights & Visuals**
* **Visual Synthesis:** Describe the most "telling" chart in the report. What anomaly does it show?
* **The Numbers:** Extract the revised estimates (Revenue/EPS). Are they raising or cutting guidance?

### **Part 4: The Bottom Line (Actionability)**
* **Verdict:** Is this "Noise" (ignore), "Maintenance" (monitor), or a "dislocation" (act now)?
* **Lateral Watchlist:** Based on this report, which *other* tickers should we be watching? (e.g., "If their cloud growth is slowing, check if Amazon AWS is taking their share").

---

**Tone:** Objective, cynical, and data-first.
**Format:** Bullet points. Maximum 300-500 words, optimized for reading as a message on Telegram
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
