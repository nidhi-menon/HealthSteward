"""Logging configuration using loguru."""

import sys
from pathlib import Path

from loguru import logger

from src.config import get_settings


def setup_logging() -> None:
    """Configure loguru logging with stderr and file rotation."""
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Add stderr handler
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Ensure log directory exists
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Add file handler with rotation
    logger.add(
        settings.log_file,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
    )

    logger.info(f"Logging initialized at level {settings.log_level}")


def get_logger(name: str):
    """Get a logger instance with the given name."""
    return logger.bind(name=name)
