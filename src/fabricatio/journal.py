"""Logging setup for the project."""

import sys

from loguru import logger
from rich import traceback

from fabricatio.config import configs

traceback.install()
logger.remove()
logger.add(
    configs.debug.log_file, level=configs.debug.log_level, rotation="1 weeks", retention="1 month", compression="zip"
)
logger.add(sys.stderr, level=configs.debug.log_level)

if __name__ == "__main__":
    logger.debug("This is a trace message.")
    logger.info("This is an information message.")
    logger.success("This is a success message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")
