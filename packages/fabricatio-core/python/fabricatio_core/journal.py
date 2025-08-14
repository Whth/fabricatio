"""Logging setup for the project."""

from fabricatio_core.rust import logger as _logger

logger = _logger
"""The logger instance for the fabricatio project."""

__all__ = ["logger"]
