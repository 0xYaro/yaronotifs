"""
Daily Summary Service

This service retrieves all messages from specified Telegram channels over the past 24 hours
and generates a comprehensive summary using LLM intelligence.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Message

from config import settings
from utils import get_logger
from services import GeminiService

logger = get_logger(__name__)


class DailySummaryService:
    """
    Service for generating daily summaries of Telegram channel messages.

    Crawls all messages (not just from @yaronotifs) from the past 24 hours
    and generates a comprehensive summary with both high-level overview and detailed breakdown.
    """

    def __init__(self, client: TelegramClient):
        """
        Initialize the daily summary service.

        Args:
            client: Authenticated Telegram client
        """
        self.client = client
        self.gemini = GeminiService()

        # Output channels to monitor and summarize
        self.crypto_channel = settings.CRYPTO_OUTPUT_CHANNEL
        self.equities_channel = settings.EQUITIES_OUTPUT_CHANNEL

        logger.info("DailySummaryService initialized")

    async def generate_daily_summary(self) -> bool:
        """
        Generate and send daily summaries for both crypto and equities channels.

        Returns:
            bool: True if summaries were generated successfully
        """
        try:
            logger.info("=" * 60)
            logger.info("GENERATING DAILY SUMMARIES")
            logger.info("=" * 60)

            # Generate summary for crypto channel
            await self._generate_channel_summary(
                channel=self.crypto_channel,
                channel_name="Crypto"
            )

            # Generate summary for equities channel
            await self._generate_channel_summary(
                channel=self.equities_channel,
                channel_name="Equities"
            )

            logger.info("Daily summaries generated successfully")
            return True

        except Exception as e:
            logger.error(f"Error generating daily summaries: {e}", exc_info=True)
            return False

    async def _generate_channel_summary(
        self,
        channel: str,
        channel_name: str
    ) -> None:
        """
        Generate and send a daily summary for a specific channel.

        Args:
            channel: Channel username or ID
            channel_name: Human-readable channel name for logging
        """
        try:
            logger.info(f"Generating summary for {channel_name} channel ({channel})...")

            # Retrieve messages from the past 24 hours
            messages = await self._get_channel_messages(channel, hours=24)

            if not messages:
                logger.info(f"No messages found in {channel_name} channel for the past 24 hours")

                # Send a message indicating no activity
                summary = self._format_no_activity_message(channel_name)
                await self.client.send_message(channel, summary)
                return

            logger.info(f"Retrieved {len(messages)} messages from {channel_name} channel")

            # Generate summary using LLM
            summary = await self._create_summary(messages, channel_name)

            # Split and send the summary to the channel (Telegram limit: 4096 chars)
            await self._send_long_message(channel, summary)

            logger.info(f"✓ Sent daily summary to {channel_name} channel")

        except Exception as e:
            logger.error(f"Error generating summary for {channel_name} channel: {e}", exc_info=True)
            raise

    async def _send_long_message(self, channel: str, message: str) -> None:
        """
        Send a message to Telegram, splitting it if it exceeds the character limit.

        Telegram's message limit is 4096 characters. This function splits long messages
        intelligently at paragraph breaks.

        Args:
            channel: Channel username or ID
            message: The message to send
        """
        MAX_LENGTH = 4000  # Leave some buffer below the 4096 limit

        if len(message) <= MAX_LENGTH:
            # Message fits in one piece
            await self.client.send_message(channel, message)
            return

        # Split long messages into multiple parts
        parts = []
        current_part = ""

        # Split by paragraphs (double newline)
        paragraphs = message.split('\n\n')

        for paragraph in paragraphs:
            # If adding this paragraph exceeds the limit, save current part and start new one
            if len(current_part) + len(paragraph) + 2 > MAX_LENGTH:
                if current_part:
                    parts.append(current_part)
                    current_part = paragraph
                else:
                    # Single paragraph is too long, split by single newlines
                    lines = paragraph.split('\n')
                    for line in lines:
                        if len(current_part) + len(line) + 1 > MAX_LENGTH:
                            if current_part:
                                parts.append(current_part)
                            current_part = line
                        else:
                            current_part += '\n' + line if current_part else line
            else:
                current_part += '\n\n' + paragraph if current_part else paragraph

        # Add the last part
        if current_part:
            parts.append(current_part)

        # Send all parts
        for i, part in enumerate(parts, 1):
            if i == 1:
                # First part - send as is
                await self.client.send_message(channel, part)
            else:
                # Subsequent parts - add part indicator (must fit within limit)
                header = f"📄 Part {i}/{len(parts)}\n\n"
                # Ensure header + part fits within limit
                if len(header + part) > 4096:
                    # Trim the part to make room for header
                    max_part_len = 4000 - len(header)
                    part = part[:max_part_len]
                await self.client.send_message(channel, header + part)

            # Small delay between messages to avoid rate limiting
            if i < len(parts):
                await asyncio.sleep(1)

        logger.info(f"Sent long message in {len(parts)} parts")

    async def _get_channel_messages(
        self,
        channel: str,
        hours: int = 24
    ) -> List[Message]:
        """
        Retrieve all messages from a channel within the specified time window.

        This retrieves ALL messages in the channel, not just those sent by the bot,
        to capture all information including messages from other sources.

        Args:
            channel: Channel username or ID
            hours: Number of hours to look back

        Returns:
            List of Telegram messages
        """
        try:
            # Calculate the cutoff time (24 hours ago)
            cutoff_time = datetime.now() - timedelta(hours=hours)

            messages = []

            # Iterate through messages in the channel starting from newest
            # We iterate from newest to oldest and stop when we hit messages older than cutoff
            async for message in self.client.iter_messages(channel):
                # Check if message is within our time window
                # message.date is timezone-aware (UTC), so we compare properly
                message_time = message.date.replace(tzinfo=None)

                # Stop if we've gone past our cutoff time
                if message_time < cutoff_time:
                    break

                # Only include messages with text content
                if message.text:
                    messages.append(message)

            # Sort messages chronologically (oldest first)
            messages.sort(key=lambda m: m.date)

            logger.info(f"Retrieved {len(messages)} messages from past {hours} hours")

            return messages

        except Exception as e:
            logger.error(f"Error retrieving messages from {channel}: {e}", exc_info=True)
            return []

    async def _create_summary(
        self,
        messages: List[Message],
        channel_name: str
    ) -> str:
        """
        Create a comprehensive summary using LLM intelligence.

        Args:
            messages: List of Telegram messages
            channel_name: Name of the channel for context

        Returns:
            Formatted summary text with #dailysummary hashtag
        """
        try:
            # Prepare message data for LLM
            message_texts = []
            for i, msg in enumerate(messages, 1):
                timestamp = msg.date.strftime("%Y-%m-%d %H:%M:%S")
                sender = "Bot" if msg.out else "Other"
                message_texts.append(f"[{i}] {timestamp} | {sender}:\n{msg.text}\n")

            combined_text = "\n".join(message_texts)

            # Build the summarization prompt
            prompt = self._build_summary_prompt(
                channel_name=channel_name,
                message_count=len(messages),
                messages_text=combined_text
            )

            logger.info(f"Sending {len(messages)} messages to LLM for summarization...")

            # Generate summary using Gemini
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.gemini.model.generate_content(prompt)
            )

            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")

            summary_text = response.text.strip()

            # Add header with requested format: #dailysummary DD MMM
            date_str = datetime.now().strftime('%d %b')  # e.g., "07 Dec"
            header = f"#dailysummary {date_str}\n"
            header += f"**{channel_name}** | {len(messages)} messages analyzed\n\n"

            full_summary = header + summary_text

            return full_summary

        except Exception as e:
            logger.error(f"Error creating summary: {e}", exc_info=True)
            raise

    def _build_summary_prompt(
        self,
        channel_name: str,
        message_count: int,
        messages_text: str
    ) -> str:
        """
        Build the LLM prompt for daily summary generation.

        Args:
            channel_name: Name of the channel
            message_count: Total number of messages
            messages_text: Combined text of all messages

        Returns:
            Formatted prompt for Gemini
        """
        return f"""# Role: Market Intelligence Summarization Analyst

**Objective:** Extract KEY INSIGHTS (not just observations) from {channel_name} intelligence with source attribution.

**Context:**
- Channel: {channel_name}
- Time Period: Past 24 hours
- Total Messages: {message_count}
- Date: {datetime.now().strftime('%Y-%m-%d')}

---

## Output Format

You MUST output in this exact format:

**Key Insights:**
- [Actionable insight with specific data/implications] [source message numbers]
- [Actionable insight with specific data/implications] [source message numbers]
- [Actionable insight with specific data/implications] [source message numbers]

**Example of GOOD insights (not mere observations):**
- **BTC** ETF inflows hit $500M, signaling institutional rotation from bonds [1][3]
- SEC expected to provide crypto clarity Q1 2025, potentially bullish for alts [2][5]
- **ETH** staking yields compressed to 3.2%, making DeFi protocols more competitive [4]

---

## Critical Instructions:

1. **Insights Not Observations:** Extract WHY something matters, implications, connections
2. **Source Attribution:** After each point, cite message numbers like [1][2][3]
3. **Consolidate:** Group related info from multiple messages into one insight
4. **Prioritize Actionability:** Most important/tradeable insights first
5. **Be Specific:** Include exact numbers, dates, tickers, percentages
6. **Maximum 3000 characters:** CRITICAL - keep output under 3000 chars total
7. **No sections/headers:** Just bullet points starting with "-"
8. **Bold key terms:** Use **bold** for tickers, companies, important numbers

**What makes a GOOD insight:**
- Shows cause/effect relationships
- Highlights market implications
- Identifies divergences or anomalies
- Connects dots across multiple data points
- Flags risks or opportunities

**Tone:** Analytical, insight-driven, zero fluff
**Length:** 15-25 bullet points, under 3000 characters total

---

## Messages to Summarize:

{messages_text}

---

Generate the point-form summary now. Remember: bullets only, cite sources, maximum 3500 characters.
"""

    def _format_no_activity_message(self, channel_name: str) -> str:
        """
        Format a message when there's no activity in the past 24 hours.

        Args:
            channel_name: Name of the channel

        Returns:
            Formatted message
        """
        header = f"📊 **Daily Summary - {channel_name}**\n"
        header += f"📅 {datetime.now().strftime('%Y-%m-%d')} | Past 24 Hours\n\n"
        header += "─" * 50 + "\n\n"

        body = "🔕 **No Activity**\n\n"
        body += "No messages were posted in this channel over the past 24 hours.\n"

        footer = "\n\n─" * 50 + "\n"
        footer += "#dailysummary"

        return header + body + footer
