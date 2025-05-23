"""Logging setup for the project."""

import logging
import sys

from loguru import logger

from fabricatio_core.rust import CONFIG


class InterceptHandler(logging.Handler):
    def emit(self, record) -> None:
        # 获取 loguru 对应的 level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        message = record.getMessage()
        if record.stack_info:
            message += "\n" + record.stack_info

        # Forward exception info (including traceback) to Loguru.
        # Loguru will use its configured `backtrace` setting for formatting.
        logger_opt = logger.opt(depth=7, exception=record.exc_info)
        logger_opt.log(level, message)


logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)

logger.remove()
logger.add(sys.stderr, level=CONFIG.debug.log_level)

__all__ = ["logger"]
