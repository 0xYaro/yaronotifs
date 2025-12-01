#!/usr/bin/env python3
"""
Configuration Verification Script

This script checks that all required environment variables are properly configured.
It also verifies that the STATUS_DESTINATION_ID is set if status updates are desired.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_config():
    """Check all configuration values."""
    print("=" * 60)
    print("Configuration Verification")
    print("=" * 60)
    print()

    errors = []
    warnings = []

    # Required variables
    required_vars = {
        'TELEGRAM_API_ID': os.getenv('TELEGRAM_API_ID'),
        'TELEGRAM_API_HASH': os.getenv('TELEGRAM_API_HASH'),
        'TELEGRAM_PHONE': os.getenv('TELEGRAM_PHONE'),
        'OUTPUT_CHANNEL_ID': os.getenv('OUTPUT_CHANNEL_ID'),
        'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
    }

    # Optional variables
    optional_vars = {
        'STATUS_DESTINATION_ID': os.getenv('STATUS_DESTINATION_ID'),
        'SESSION_NAME': os.getenv('SESSION_NAME', 'yaronotifs_session'),
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
    }

    # Check required variables
    print("Required Configuration:")
    print("-" * 60)
    for var, value in required_vars.items():
        if not value or value == '0':
            print(f"❌ {var}: NOT SET")
            errors.append(f"{var} is required but not set")
        else:
            # Mask sensitive values
            if 'KEY' in var or 'HASH' in var:
                masked = value[:8] + "..." if len(value) > 8 else "***"
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")

    print()
    print("Optional Configuration:")
    print("-" * 60)
    for var, value in optional_vars.items():
        if not value:
            if var == 'STATUS_DESTINATION_ID':
                print(f"⚠️  {var}: NOT SET (status updates disabled)")
                warnings.append("STATUS_DESTINATION_ID not set - bot will not send status updates")
            else:
                print(f"ℹ️  {var}: Using default")
        else:
            print(f"✅ {var}: {value}")

    print()
    print("=" * 60)

    # Print summary
    if errors:
        print("ERRORS FOUND:")
        for error in errors:
            print(f"  ❌ {error}")
        print()
        print("Please update your .env file and try again.")
        return False

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print()

    print("✅ Configuration is valid!")
    print()

    # Check session file
    session_name = optional_vars['SESSION_NAME']
    session_file = Path.cwd() / f"{session_name}.session"

    print("Session File Check:")
    print("-" * 60)
    if session_file.exists():
        print(f"✅ Session file found: {session_file}")
    else:
        print(f"❌ Session file NOT found: {session_file}")
        print("   Please run: python scripts/create_session.py")
        return False

    print()
    print("=" * 60)
    print("🎉 All checks passed! You're ready to run the bot.")
    print("=" * 60)

    return True

if __name__ == '__main__':
    success = check_config()
    sys.exit(0 if success else 1)
