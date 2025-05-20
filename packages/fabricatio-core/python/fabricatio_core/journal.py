"""Logging setup for the project."""

import sys

from loguru import logger

from fabricatio_core.rust import CONFIG

logger.remove()
logger.add(sys.stderr, level=CONFIG.debug.log_level)

__all__ = ["logger"]
