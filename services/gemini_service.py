import asyncio
from pathlib import Path
from typing import Any, Optional

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

    async def _upload_and_wait_for_file(self, file_path: Path) -> Any:
        """
        Upload a file to Gemini File API and wait for processing.

        Args:
            file_path: Path to the file to upload

        Returns:
            Uploaded file object ready for use

        Raises:
            FileNotFoundError: If file doesn't exist
            TimeoutError: If file processing times out
            ValueError: If file processing fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Uploading file to Gemini File API: {file_path.name}")

        loop = asyncio.get_event_loop()
        uploaded_file = await loop.run_in_executor(
            None,
            lambda: genai.upload_file(str(file_path))
        )

        logger.info(f"File uploaded: {uploaded_file.name} ({uploaded_file.state.name})")

        # Wait for file processing if needed
        if uploaded_file.state.name == "PROCESSING":
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

        return uploaded_file

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
        try:
            # Upload and wait for file processing
            uploaded_file = await self._upload_and_wait_for_file(pdf_path)

            # Generate analysis using the uploaded file
            prompt = self._build_equity_analysis_prompt()

            loop = asyncio.get_event_loop()
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

    @retry_async(max_attempts=3, delay=2.0, backoff=2.0)
    async def process_text_message(self, text: str, context: dict) -> str:
        """
        Process a text message using LLM to intelligently handle:
        - Language detection and translation
        - Summarization
        - Key insight extraction
        - Contextual analysis

        Args:
            text: The message text to process
            context: Context information about the message (source, language, etc.)

        Returns:
            str: Processed and formatted content

        Raises:
            Exception: If API call fails after retries
        """
        try:
            prompt = self._build_text_processing_prompt(text, context)

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )

            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")

            result = response.text.strip()
            logger.info(f"Processed text message: {len(result)} characters")

            return result

        except Exception as e:
            logger.error(f"Gemini text processing error: {e}")
            raise

    @retry_async(max_attempts=3, delay=2.0, backoff=2.0)
    async def process_document(self, file_path: Path, context: dict) -> str:
        """
        Process a document (PDF, image, etc.) using LLM's multimodal capabilities.

        This method analyzes both text and visual elements to provide:
        - Content type detection
        - Comprehensive analysis
        - Key insights extraction
        - Contextual understanding

        Args:
            file_path: Path to the document file
            context: Context information about the message

        Returns:
            str: Processed and formatted content

        Raises:
            Exception: If API call fails after retries
        """
        try:
            # Upload and wait for file processing
            uploaded_file = await self._upload_and_wait_for_file(file_path)

            # Generate analysis using the uploaded file
            prompt = self._build_document_processing_prompt(context)

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content([uploaded_file, prompt])
            )

            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")

            result = response.text.strip()
            logger.info(f"Processed document: {len(result)} characters")

            # Delete the uploaded file to save quota
            await loop.run_in_executor(
                None,
                lambda: genai.delete_file(uploaded_file.name)
            )
            logger.debug(f"Deleted uploaded file: {uploaded_file.name}")

            return result

        except Exception as e:
            logger.error(f"Gemini document processing error: {e}")
            raise

    def _build_text_processing_prompt(self, text: str, context: dict) -> str:
        """
        Build a prompt for intelligent text processing.

        Args:
            text: The text to process
            context: Context information

        Returns:
            str: Formatted prompt for Gemini
        """
        has_chinese = context.get("has_chinese", False)
        source_channel = context.get("source_channel", "Unknown Source")

        if has_chinese:
            return f"""# Role: Market Intelligence Analyst & Translator

**Source:** {source_channel}

**Task:** Process the following message for a professional investor. The message contains Chinese text.

**Instructions:**
1. **Translate** the Chinese text to English (if present)
2. **Summarize** the key points in bullet format
3. **Extract** any actionable insights, market movements, or important announcements
4. **Format** for readability on Telegram (use markdown)

**Content Type Detection:**
- If this is breaking news, mark it as "🚨 BREAKING"
- If this mentions specific tokens/stocks, highlight them
- If there are numbers/data, preserve them accurately

**Output Format:**
[Translated and summarized content in clear, concise English]

**Tone:** Professional, objective, data-focused
**Length:** 200-400 words maximum

---

**Message to process:**

{text}
"""
        else:
            return f"""# Role: Market Intelligence Analyst

**Source:** {source_channel}

**Task:** Process the following message for a professional investor.

**Instructions:**
1. **Summarize** the key points in bullet format
2. **Extract** any actionable insights, market movements, or important announcements
3. **Highlight** any critical data points or numbers
4. **Format** for readability on Telegram (use markdown)

**Content Type Detection:**
- If this is breaking news, mark it as "🚨 BREAKING"
- If this mentions specific tokens/stocks, highlight them
- If there are numbers/data, preserve them accurately

**Output Format:**
[Summarized content in clear, concise format]

**Tone:** Professional, objective, data-focused
**Length:** 200-400 words maximum

---

**Message to process:**

{text}
"""

    def _build_document_processing_prompt(self, context: dict) -> str:
        """
        Build a prompt for intelligent document processing.

        This prompt instructs the LLM to analyze documents comprehensively,
        including both text and visual elements.

        Args:
            context: Context information

        Returns:
            str: Formatted prompt for Gemini
        """
        source_channel = context.get("source_channel", "Unknown Source")

        return f"""# Role: Senior Market Intelligence Analyst (Buy-Side)

**Source:** {source_channel}

**Objective:** Analyze this document and synthesize it into actionable intelligence for a professional investor.

---

## Analysis Framework:

### **Part 1: Document Type & Context**
* **Document Type:** Identify what this is (equity research report, news article, whitepaper, presentation, etc.)
* **The Trigger:** Why was this document created? (Earnings, M&A, product launch, analyst day, etc.)
* **The Core Update:** What is the single most important new information in this document?

### **Part 2: Key Insights & Data**
* **Visual Analysis:** Analyze any charts, graphs, tables, or visual elements. What story do they tell?
* **The Numbers:** Extract key data points (revenue, growth rates, estimates, valuations, etc.)
* **Consensus Check:** Does this align with or contradict prevailing market sentiment?

### **Part 3: Market Context** (if applicable)
* **Price Action Relevance:** Consider recent market movements related to this content
* **Sector Implications:** What does this mean for the broader sector/industry?
* **Cross-References:** What other companies/assets should we monitor based on this?

### **Part 4: Actionability**
* **Verdict:** Is this "Noise" (ignore), "Maintenance" (monitor), or "Dislocation" (act now)?
* **Key Takeaways:** 3-5 bullet points of what matters most
* **Watchlist:** Related tickers/assets to monitor

---

**Output Requirements:**
- Use markdown formatting for readability on Telegram
- Include bullet points for easy scanning
- Highlight critical data with **bold**
- Keep total length to 400-600 words
- Be objective, cynical, and data-first

**Tone:** Professional, analytical, actionable
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
