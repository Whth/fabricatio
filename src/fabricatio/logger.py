from loguru import logger

from fabricatio.config import configs

logger.level(configs.debug.log_level)
logger.add(configs.debug.log_file, rotation="1 weeks", retention="1 month", compression="zip")

if __name__ == "__main__":
    logger.debug("This is a trace message.")
    logger.info("This is an information message.")
    logger.success("This is a success message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")
