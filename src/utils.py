"""
Utility functions for the Facebook scraper project.
Contains common helper functions used across the application.
"""

import os
import json
import csv
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse, parse_qs
import pandas as pd
from loguru import logger


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Set up logging configuration with loguru.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, only logs to console.
    """
    # Remove default logger
    logger.remove()
    
    # Add console logger with colors
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # Add file logger if specified
    if log_file:
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip"
        )
    
    logger.info(f"Logging setup complete. Level: {log_level}")


def validate_url(url: str) -> bool:
    """
    Validate if a URL is properly formatted.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def is_facebook_url(url: str) -> bool:
    """
    Check if URL is a Facebook URL.
    
    Args:
        url: URL to check
        
    Returns:
        True if it's a Facebook URL
    """
    if not validate_url(url):
        return False
    
    parsed = urlparse(url)
    facebook_domains = ['facebook.com', 'www.facebook.com', 'm.facebook.com']
    return parsed.netloc.lower() in facebook_domains


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Add a random delay to avoid being detected as a bot.
    
    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Sleeping for {delay:.2f} seconds")
    time.sleep(delay)


def human_like_delay() -> None:
    """Add a human-like delay between actions."""
    delays = [
        (1, 2),      # Quick action
        (2, 4),      # Normal action  
        (3, 6),      # Thoughtful action
        (0.5, 1.5),  # Very quick
    ]
    min_delay, max_delay = random.choice(delays)
    random_delay(min_delay, max_delay)


def ensure_directory_exists(directory_path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, create it if it doesn't.
    
    Args:
        directory_path: Path to directory
        
    Returns:
        Path object of the directory
    """
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Directory ensured: {path}")
    return path


def save_json(data: Any, filepath: Union[str, Path], indent: int = 2) -> None:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        filepath: Output file path
        indent: JSON indentation
    """
    filepath = Path(filepath)
    ensure_directory_exists(filepath.parent)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    
    logger.info(f"Data saved to JSON: {filepath}")


def load_json(filepath: Union[str, Path]) -> Any:
    """
    Load data from a JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Loaded data
    """
    filepath = Path(filepath)
    if not filepath.exists():
        logger.error(f"JSON file not found: {filepath}")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"Data loaded from JSON: {filepath}")
    return data


def save_csv(data: List[Dict], filepath: Union[str, Path], fieldnames: Optional[List[str]] = None) -> None:
    """
    Save data to a CSV file.
    
    Args:
        data: List of dictionaries to save
        filepath: Output file path
        fieldnames: Optional list of field names for column order
    """
    if not data:
        logger.warning("No data to save to CSV")
        return
    
    filepath = Path(filepath)
    ensure_directory_exists(filepath.parent)
    
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    logger.info(f"Data saved to CSV: {filepath} ({len(data)} rows)")


def load_csv(filepath: Union[str, Path]) -> List[Dict]:
    """
    Load data from a CSV file.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        List of dictionaries
    """
    filepath = Path(filepath)
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    
    logger.info(f"Data loaded from CSV: {filepath} ({len(data)} rows)")
    return data


def clean_text(text: str) -> str:
    """
    Clean scraped text by removing extra whitespace and special characters.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove common unwanted characters
    text = text.replace('\u00a0', ' ')  # Non-breaking space
    text = text.replace('\u200b', '')   # Zero-width space
    text = text.replace('\u200c', '')   # Zero-width non-joiner
    text = text.replace('\u200d', '')   # Zero-width joiner
    
    return text.strip()


def get_timestamp(format_string: str = "%Y%m%d_%H%M%S") -> str:
    """
    Get current timestamp as formatted string.
    
    Args:
        format_string: strftime format string
        
    Returns:
        Formatted timestamp string
    """
    return datetime.now().strftime(format_string)


def create_data_filename(prefix: str, extension: str = "json") -> str:
    """
    Create a timestamped filename for data files.
    
    Args:
        prefix: Filename prefix
        extension: File extension without dot
        
    Returns:
        Timestamped filename
    """
    timestamp = get_timestamp()
    return f"{prefix}_{timestamp}.{extension}"


def safe_get_element_text(element, default: str = "") -> str:
    """
    Safely get text from a web element.
    
    Args:
        element: Selenium WebElement or None
        default: Default value if element is None or has no text
        
    Returns:
        Element text or default value
    """
    try:
        if element is None:
            return default
        text = element.text.strip()
        return clean_text(text) if text else default
    except Exception as e:
        logger.warning(f"Error getting element text: {e}")
        return default


def parse_facebook_url(url: str) -> Dict[str, Any]:
    """
    Parse a Facebook URL to extract useful information.
    
    Args:
        url: Facebook URL to parse
        
    Returns:
        Dictionary with parsed URL components
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    return {
        'full_url': url,
        'path': parsed.path,
        'query_params': query_params,
        'is_profile': '/profile.php' in parsed.path or parsed.path.count('/') == 1,
        'is_post': '/posts/' in parsed.path,
        'is_photo': '/photo/' in parsed.path,
        'is_video': '/videos/' in parsed.path,
    }


def retry_on_exception(max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """
    Decorator to retry a function on exception.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff_factor: Factor to multiply delay after each retry
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
        return wrapper
    return decorator


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    Returns:
        Path to project root
    """
    current_file = Path(__file__).resolve()
    # Assuming utils.py is in src/ directory
    return current_file.parent.parent


def setup_data_directories() -> Dict[str, Path]:
    """
    Set up and return data directories.
    
    Returns:
        Dictionary of data directory paths
    """
    root = get_project_root()
    directories = {
        'data': root / 'data',
        'raw': root / 'data' / 'raw',
        'processed': root / 'data' / 'processed',
        'logs': root / 'logs',
    }
    
    for name, path in directories.items():
        ensure_directory_exists(path)
    
    return directories


# Configuration for common scraping patterns
COMMON_SELECTORS = {
    'facebook': {
        'post_content': '[data-ad-preview="message"]',
        'author_name': '[data-testid="story-subtitle"] a',
        'timestamp': '[data-testid="story-subtitle"] a[href*="/posts/"]',
        'like_count': '[aria-label*="reactions"]',
        'comment_count': '[aria-label*="comments"]',
        'share_count': '[aria-label*="shares"]',
    }
}


# Initialize logging when module is imported
setup_logging()