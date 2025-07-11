"""Logging setup for the project."""

import sys

from loguru import logger as _logger

from fabricatio_core.rust import CONFIG

logger = _logger
"""The logger instance for the fabricatio project."""

logger.remove()
logger.add(
    sys.stderr,
    level=CONFIG.debug.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}:{function}</cyan> - <level>{message}</level>",
)

if CONFIG.debug.log_file:
    logger.add(
        CONFIG.debug.log_file,
        rotation=f"{CONFIG.debug.rotation} MB" if CONFIG.debug.rotation else None,
        retention=f"{CONFIG.debug.retention} days" if CONFIG.debug.retention else None,
        level=CONFIG.debug.log_level,
    )


__all__ = ["logger"]
