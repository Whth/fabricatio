import sys

import pytest
from fabricatio import journal


def test_logger_level(caplog):
    # Test that the logger level is set from CONFIG
    # Note: loguru's level property returns an object, so we check by name
    assert journal.logger.level.name == journal.CONFIG.debug.log_level


def test_logger_output(caplog):
    # Test that the logger outputs to stderr
    journal.logger.info("Test log message")

    assert "Test log message" in caplog.text


def test_logger_add():
    # Test adding a new logger
    # Use DEBUG level explicitly as string for better type checking
    result = journal.logger.add(sys.stderr, level="DEBUG")
    assert result is not None

    # Remove the handler after test
    journal.logger.remove(result)


def test_logger_remove():
    # Test removing a logger
    handler_id = journal.logger.add(sys.stderr, level="DEBUG")
    journal.logger.remove(handler_id)

    # After removal, logging should not raise an error
    try:
        journal.logger.info("After removal")
    except Exception as e:
        pytest.fail(f"Logger raised {e} after handler removal")


def test_logger_exception(caplog):
    # Test exception logging
    try:
        1 / 0
    except ZeroDivisionError:
        journal.logger.exception("Division by zero occurred")

    # Check that both the message and traceback are present
    assert "Division by zero occurred" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "ZeroDivisionError" in caplog.text


def test_logger_bind(caplog):
    # Test binding additional context to logger
    bound_logger = journal.logger.bind(context="test_context")
    bound_logger.info("Bound log message")

    assert "context=test_context" in caplog.text
    assert "Bound log message" in caplog.text


def test_logger_levels(caplog):
    # Test different log levels
    journal.logger.debug("Debug message")
    journal.logger.info("Info message")
    journal.logger.warning("Warning message")
    journal.logger.error("Error message")

    assert "Debug message" in caplog.text
    assert "Info message" in caplog.text
    assert "Warning message" in caplog.text
    assert "Error message" in caplog.text


def test_logger_configuration():
    # Test that changing CONFIG affects logger
    original_level = journal.CONFIG.debug.log_level

    # Change the log level and verify it's applied
    new_level = "DEBUG"
    journal.CONFIG.debug.log_level = new_level

    try:
        assert journal.logger.level == new_level
    finally:
        # Restore original level
        journal.CONFIG.debug.log_level = original_level


def test_logger_with_function(caplog):
    def sample_function():
        return "function_result"

    # Test lazy evaluation of functions in log messages
    journal.logger.info("Function result: {}", sample_function)
    assert "function_result" in caplog.text


def test_logger_multiple_handlers():
    # Test adding multiple handlers
    # Get initial handler count
    initial_handler_count = len(journal.logger._handlers)

    handler1 = journal.logger.add(sys.stdout, level="INFO")
    handler2 = journal.logger.add(sys.stderr, level="DEBUG")

    try:
        # Verify new handlers were added
        assert len(journal.logger._handlers) == initial_handler_count + 2
    finally:
        # Clean up added handlers
        journal.logger.remove(handler1)
        journal.logger.remove(handler2)


def test_logger_patching():
    # Test patching functionality
    def patching_func(record):
        record["patched"] = True

    # Create a patcher
    patcher = journal.logger.patch(patching_func)

    # Add the patcher to the logger
    journal.logger.add(sys.stderr, level="DEBUG", backtrace=False, diagnose=False)
    try:
        # Apply the patcher
        with patcher:
            journal.logger.info("Patched message")
            # The patched attribute should be present in the record
            assert hasattr(journal.logger, "patched")
    finally:
        # Remove all handlers
        journal.logger.remove()
