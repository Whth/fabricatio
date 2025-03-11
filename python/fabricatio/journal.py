"""Logging setup for the project."""

import sys

from loguru import logger
from rich import pretty, traceback

from fabricatio.config import configs

pretty.install()
traceback.install()
logger.remove()
logger.add(
    configs.debug.log_file,
    level=configs.debug.log_level,
    rotation=f"{configs.debug.rotation} weeks",
    retention=f"{configs.debug.retention} weeks",
)
logger.add(sys.stderr, level=configs.debug.log_level)

__all__ = ["logger"]
