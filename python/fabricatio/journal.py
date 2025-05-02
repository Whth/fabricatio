"""Logging setup for the project."""

import sys

from fabricatio.rust import CONFIG
from loguru import logger
from rich import pretty, traceback

pretty.install()
traceback.install()
logger.remove()
logger.add(sys.stderr, level=CONFIG.debug.log_level)

__all__ = ["logger"]
