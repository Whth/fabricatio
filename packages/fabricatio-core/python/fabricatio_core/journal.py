"""Logging setup for the project."""

import sys

from loguru import logger as _logger

from fabricatio_core.rust import CONFIG

logger = _logger

logger.remove()
logger.add(
    sys.stderr,
    level=CONFIG.debug.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}:{function}</cyan> - <level>{message}</level>",
)

__all__ = ["logger"]
