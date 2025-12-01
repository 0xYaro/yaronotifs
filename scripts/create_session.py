#!/usr/bin/env python3
"""
Session Creation Helper Script

This script must be run LOCALLY on your machine (not on the server).
It will:
1. Prompt for your phone number
2. Send a verification code to Telegram
3. Optionally handle 2FA password
4. Generate a .session file that can be uploaded to AWS

Usage:
    python scripts/create_session.py

After completion:
    Upload the generated .session file to your AWS server in the project root directory.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config import settings


async def create_session():
    """
    Interactive session creation process.
    """
    print("=" * 60)
    print("TELEGRAM SESSION CREATOR")
    print("=" * 60)
    print()
    print("This script will help you authenticate with Telegram and")
    print("create a session file that can be used on your AWS server.")
    print()

    # Check configuration
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        print("❌ ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        print()
        print("Please create a .env file based on .env.example and add your credentials.")
        return False

    print(f"API ID: {settings.TELEGRAM_API_ID}")
    print(f"Session Name: {settings.SESSION_NAME}")
    print()

    # Get phone number
    phone = input("Enter your phone number (with country code, e.g. +1234567890): ").strip()
    if not phone:
        print("❌ Phone number is required")
        return False

    # Create session file path
    session_path = settings.BASE_DIR / f"{settings.SESSION_NAME}.session"

    # Check if session already exists
    if session_path.exists():
        overwrite = input(f"\n⚠️  Session file already exists: {session_path}\n"
                         f"Do you want to overwrite it? (yes/no): ").strip().lower()
        if overwrite not in ['yes', 'y']:
            print("Aborted.")
            return False
        session_path.unlink()

    print()
    print("Connecting to Telegram...")
    print()

    # Create client
    client = TelegramClient(
        str(settings.BASE_DIR / settings.SESSION_NAME),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH
    )

    try:
        await client.connect()

        # Request code
        await client.send_code_request(phone)
        print(f"✓ Code sent to {phone}")
        print()

        # Get verification code
        code = input("Enter the verification code you received: ").strip()
        if not code:
            print("❌ Verification code is required")
            return False

        try:
            # Try to sign in
            await client.sign_in(phone, code)

        except SessionPasswordNeededError:
            # 2FA is enabled
            print()
            print("🔐 Two-factor authentication is enabled for this account.")
            password = input("Enter your 2FA password: ").strip()

            if not password:
                print("❌ Password is required")
                return False

            await client.sign_in(password=password)

        # Verify successful login
        me = await client.get_me()
        print()
        print("=" * 60)
        print("✓ SUCCESS!")
        print("=" * 60)
        print(f"Logged in as: {me.first_name} {me.last_name or ''}")
        print(f"Username: @{me.username or 'N/A'}")
        print(f"Phone: {me.phone}")
        print()
        print(f"Session file created: {session_path}")
        print()
        print("NEXT STEPS:")
        print("1. Copy this session file to your AWS server")
        print(f"   scp {session_path.name} user@your-server:/path/to/yaronotifs/")
        print()
        print("2. Make sure the .env file on your server has:")
        print(f"   TELEGRAM_API_ID={settings.TELEGRAM_API_ID}")
        print(f"   TELEGRAM_API_HASH={settings.TELEGRAM_API_HASH}")
        print(f"   TELEGRAM_PHONE={phone}")
        print()
        print("3. Run the bot on your server:")
        print("   python main.py")
        print()

        return True

    except Exception as e:
        print()
        print(f"❌ ERROR: {e}")
        print()
        return False

    finally:
        await client.disconnect()


def main():
    """
    Main entry point.
    """
    try:
        success = asyncio.run(create_session())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
