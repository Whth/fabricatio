"""Logging setup for the project."""

from fabricatio_core.rust import CONFIG
from fabricatio_core.rust import logger as _logger

logger = _logger
"""The logger instance for the fabricatio project."""

if CONFIG.debug.log_file:
    # TODO: add log file
    pass


__all__ = ["logger"]
