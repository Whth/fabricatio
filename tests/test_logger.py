from loguru import logger

from fabricatio.logger import configs


def test_logger_config():
    assert configs.debug.log_level == "INFO"
    assert configs.debug.log_file.endswith(".log")


def test_logger_output(capsys):
    logger.info("Test log message")
    captured = capsys.readouterr()
    assert "Test log message" in captured.out
