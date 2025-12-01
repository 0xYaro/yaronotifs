import asyncio
import re
from functools import wraps
from typing import Callable, Any, TypeVar, Optional
from pathlib import Path

from .logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


def retry_async(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0,
                exceptions: tuple = (Exception,)):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @retry_async(max_attempts=3, delay=2.0)
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            raise last_exception

        return wrapper
    return decorator


def detect_chinese(text: str) -> bool:
    """
    Detect if text contains Chinese characters.

    Args:
        text: Input text to check

    Returns:
        bool: True if Chinese characters are found, False otherwise
    """
    if not text:
        return False

    # Unicode ranges for Chinese characters (CJK Unified Ideographs)
    chinese_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]+')
    return bool(chinese_pattern.search(text))


def safe_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize a filename by removing unsafe characters.

    Args:
        filename: Original filename
        max_length: Maximum length for the filename

    Returns:
        str: Sanitized filename
    """
    # Remove path separators and other unsafe characters
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

    # Trim whitespace
    safe = safe.strip()

    # Limit length
    if len(safe) > max_length:
        name, ext = Path(safe).stem, Path(safe).suffix
        safe = name[:max_length - len(ext)] + ext

    return safe or 'unnamed_file'


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        str: Formatted file size (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def truncate_text(text: str, max_length: int = 4000, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length, adding suffix if truncated.

    Args:
        text: Input text
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        str: Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
