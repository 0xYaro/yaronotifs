#!/usr/bin/env python3
"""
Test script to send messages to the test channel
This will verify the UnifiedPipeline is working correctly
"""

import asyncio
from telethon import TelegramClient
from config import settings

# Test channel
TEST_CHANNEL_ID = -1003309883285  # Yaro Notifs Test Channel


async def send_test_messages():
    """Send test messages to verify UnifiedPipeline processing"""

    # Initialize Telegram client
    client = TelegramClient(
        str(settings.BASE_DIR / settings.SESSION_NAME),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )

    try:
        await client.start()

        print("=" * 60)
        print("SENDING TEST MESSAGES TO TEST CHANNEL")
        print("=" * 60)
        print()

        # Test 1: English text message
        print("Test 1: Sending English text message...")
        await client.send_message(
            TEST_CHANNEL_ID,
            "🧪 **UnifiedPipeline Test #1**\n\n"
            "This is a test English message to verify the UnifiedPipeline is working. "
            "The bot should process this, extract key insights, and forward to the output channel.\n\n"
            "Key points to test:\n"
            "• Text processing ✓\n"
            "• Summarization ✓\n"
            "• Forwarding ✓"
        )
        print("✓ Test 1 sent\n")
        await asyncio.sleep(2)

        # Test 2: Chinese text message
        print("Test 2: Sending Chinese text message...")
        await client.send_message(
            TEST_CHANNEL_ID,
            "🧪 **UnifiedPipeline 测试 #2**\n\n"
            "这是一条中文测试消息，用于验证统一管道架构。\n"
            "机器人应该检测到中文，翻译成英文，并转发到输出频道。\n\n"
            "比特币今天上涨了5%，达到了新的历史高点。"
        )
        print("✓ Test 2 sent\n")
        await asyncio.sleep(2)

        # Test 3: Mixed language
        print("Test 3: Sending mixed English/Chinese message...")
        await client.send_message(
            TEST_CHANNEL_ID,
            "🧪 **UnifiedPipeline Test #3**\n\n"
            "Breaking News: 以太坊 (Ethereum) 宣布重大更新。\n"
            "The upgrade will include 更快的交易速度 and lower fees.\n\n"
            "Expected launch: Q1 2025"
        )
        print("✓ Test 3 sent\n")

        print("=" * 60)
        print("ALL TEST MESSAGES SENT!")
        print("=" * 60)
        print()
        print("Now check the bot logs to see if messages are being processed...")
        print("Also check your OUTPUT_CHANNEL to see forwarded messages")

    finally:
        await client.disconnect()


if __name__ == '__main__':
    asyncio.run(send_test_messages())
