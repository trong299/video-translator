"""
Logging utilities using loguru
"""
import sys
from pathlib import Path
from typing import Optional
from loguru import logger
from datetime import datetime


def setup_logger(
    log_file: Optional[Path] = None,
    log_level: str = "INFO",
    format_string: Optional[str] = None
) -> 'logger':
    """
    Setup application logger with console and file handlers
    
    Args:
        log_file: Path to log file (optional)
        log_level: Logging level
        format_string: Custom format string
    
    Returns:
        Configured logger instance
    """
    # Remove default handler
    logger.remove()
    
    # Default format
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    
    # Console handler
    logger.add(
        sys.stderr,
        format=format_string,
        level=log_level,
        colorize=True
    )
    
    # File handler
    if log_file is None:
        log_dir = Path.home() / ".video_translator_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logger.add(
        log_file,
        format=format_string,
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding='utf-8'
    )
    
    return logger


def get_logger(name: Optional[str] = None):
    """
    Get a logger instance
    
    Args:
        name: Logger name (optional, uses module name by default)
    
    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


class LogCapture:
    """Context manager to capture log messages for testing"""
    
    def __init__(self):
        self.messages = []
        self._handler_id = None
    
    def __enter__(self):
        self.messages = []
        self._handler_id = logger.add(
            lambda msg: self.messages.append(str(msg)),
            format="{message}"
        )
        return self
    
    def __exit__(self, *args):
        logger.remove(self._handler_id)
    
    def get_messages(self) -> list:
        return self.messages

