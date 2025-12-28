"""Logging setup"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "video_service",
    level: str = "INFO",
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """Setup and configure logger"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "video_service") -> logging.Logger:
    """Get existing logger or create new one"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        # If no handlers, setup default logger
        setup_logger(name)
    return logger

