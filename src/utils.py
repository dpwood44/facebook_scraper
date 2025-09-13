"""
Enhanced utility functions for the Facebook scraper project.
Contains common helper functions used across the application with improved logging.
"""

import os
import json
import csv
import time
import random
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse, parse_qs
import pandas as pd
from loguru import logger as loguru_logger


def setup_enhanced_logging(log_level: str = "DEBUG", log_file: Optional[str] = None) -> None:
    """
    Enhanced logging setup that captures all modules consistently.
    
    Args:
        log_level: Logging level for console output (DEBUG, INFO, WARNING, ERROR, CRITICAL)  
        log_file: Optional log file path. If None, only logs to console.
    """
    # Remove default loguru logger
    loguru_logger.remove()
    
    # Add console logger with enhanced format
    loguru_logger.add(
        sink=sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        colorize=True,
        enqueue=True,  # Thread-safe for async operations
        catch=True     # Catch exceptions in logging
    )
    
    # Add file logger with comprehensive detail (always DEBUG level)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        loguru_logger.add(
            log_file,
            level="DEBUG",  # Always capture all details to file
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {process.name}:{thread.name} | {extra} | {message}",
            rotation="50 MB",
            retention="10 days", 
            compression="zip",
            enqueue=True,
            catch=True
        )
    
    # Bridge standard logging to loguru for module consistency
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = loguru_logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            loguru_logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Replace all standard logging handlers with our interceptor
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Ensure all existing loggers use our handler
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    
    # Set specific levels for noisy third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    
    loguru_logger.info(f"Enhanced logging setup complete. Console: {log_level}, File: {'DEBUG' if log_file else 'None'}")


def get_module_logger(module_name: str):
    """
    Get a properly configured logger for any module with context binding.
    
    Args:
        module_name: Usually __name__ from the calling module
        
    Returns:
        Loguru logger instance with module context
    """
    return loguru_logger.bind(module=module_name)


def create_scraper_logger(session_id: str, module_name: str, **extra_context):
    """
    Create a logger specifically for scraper components with rich context.
    
    Args:
        session_id: Scraping session identifier
        module_name: Module name (usually __name__)
        **extra_context: Additional context to bind to logger
        
    Returns:
        Loguru logger with scraper context
    """
    context = {
        'session_id': session_id,
        'module': module_name,
        **extra_context
    }
    return loguru_logger.bind(**context)


def log_method_entry(func_name: str, **kwargs):
    """Log method entry with parameters for debugging."""
    params = ', '.join(f"{k}={v}" for k, v in kwargs.items())
    loguru_logger.debug(f"ENTER: {func_name}({params})")


def log_method_exit(func_name: str, result=None, duration_ms: Optional[float] = None):
    """Log method exit with result and timing."""
    timing = f" [{duration_ms:.1f}ms]" if duration_ms else ""
    result_str = f" -> {type(result).__name__}" if result is not None else ""
    loguru_logger.debug(f"EXIT: {func_name}{result_str}{timing}")


def log_performance_metric(operation: str, duration_ms: float, **metrics):
    """Log performance metrics for analysis."""
    metric_str = ', '.join(f"{k}={v}" for k, v in metrics.items())
    loguru_logger.info(f"PERF: {operation} completed in {duration_ms:.1f}ms | {metric_str}")


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
    loguru_logger.debug(f"Random delay: {delay:.2f}s")
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
    loguru_logger.debug(f"Directory ensured: {path}")
    return path


def save_json(data: Any, filepath: Union[str, Path], indent: int = 2) -> None:
    """
    Save data to a JSON file with logging.
    
    Args:
        data: Data to save
        filepath: Output file path
        indent: JSON indentation
    """
    filepath = Path(filepath)
    ensure_directory_exists(filepath.parent)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        
        file_size = filepath.stat().st_size
        loguru_logger.info(f"JSON saved: {filepath} ({file_size:,} bytes)")
        
    except Exception as e:
        loguru_logger.error(f"Failed to save JSON to {filepath}: {e}")
        raise


def load_json(filepath: Union[str, Path]) -> Any:
    """
    Load data from a JSON file with logging.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Loaded data
    """
    filepath = Path(filepath)
    if not filepath.exists():
        loguru_logger.error(f"JSON file not found: {filepath}")
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_size = filepath.stat().st_size
        loguru_logger.info(f"JSON loaded: {filepath} ({file_size:,} bytes)")
        return data
        
    except Exception as e:
        loguru_logger.error(f"Failed to load JSON from {filepath}: {e}")
        return None


def save_csv(data: List[Dict], filepath: Union[str, Path], fieldnames: Optional[List[str]] = None) -> None:
    """
    Save data to a CSV file with logging.
    
    Args:
        data: List of dictionaries to save
        filepath: Output file path
        fieldnames: Optional list of field names for column order
    """
    if not data:
        loguru_logger.warning("No data to save to CSV")
        return
    
    filepath = Path(filepath)
    ensure_directory_exists(filepath.parent)
    
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        file_size = filepath.stat().st_size
        loguru_logger.info(f"CSV saved: {filepath} ({len(data)} rows, {file_size:,} bytes)")
        
    except Exception as e:
        loguru_logger.error(f"Failed to save CSV to {filepath}: {e}")
        raise


def load_csv(filepath: Union[str, Path]) -> List[Dict]:
    """
    Load data from a CSV file with logging.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        List of dictionaries
    """
    filepath = Path(filepath)
    if not filepath.exists():
        loguru_logger.error(f"CSV file not found: {filepath}")
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        file_size = filepath.stat().st_size
        loguru_logger.info(f"CSV loaded: {filepath} ({len(data)} rows, {file_size:,} bytes)")
        return data
        
    except Exception as e:
        loguru_logger.error(f"Failed to load CSV from {filepath}: {e}")
        return []


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


def retry_on_exception(max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """
    Decorator to retry a function on exception with logging.
    
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
                        loguru_logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    loguru_logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
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
    Set up and return data directories with logging.
    
    Returns:
        Dictionary of data directory paths
    """
    root = get_project_root()
    directories = {
        'data': root / 'data',
        'raw': root / 'data' / 'raw',
        'processed': root / 'data' / 'processed',
        'logs': root / 'logs',
        'models': root / 'models',
        'scrapes': root / 'scrapes',
    }
    
    for name, path in directories.items():
        ensure_directory_exists(path)
    
    loguru_logger.debug(f"Data directories setup: {list(directories.keys())}")
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


# Global logger for module-level functions
module_logger = get_module_logger(__name__)