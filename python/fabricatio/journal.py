"""Logging setup for the project."""

import sys

from fabricatio.rust import CONFIG
from loguru import logger

logger.remove()
logger.add(sys.stderr, level=CONFIG.debug.log_level)

__all__ = ["logger"]
