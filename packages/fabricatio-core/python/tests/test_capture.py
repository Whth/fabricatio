"""Tests for the Capture class from fabricatio_core.parser module."""

from unittest.mock import patch

import pytest
from fabricatio_core.parser import Capture, GenericCapture, JsonCapture, PythonCapture


class TestCapture:
    """Test cases for the Capture class."""

    def test_basic_capture_success(self) -> None:
        """Test successful pattern capture."""
        capture = Capture(pattern=r"Hello (\w+)")
        result = capture.capture("Hello World!")
        assert result == "World"

    def test_basic_capture_with_groups(self) -> None:
        """Test capture with multiple groups returns first group."""
        capture = Capture(pattern=r"(\w+) (\w+)")
        result = capture.capture("Hello World")
        assert result == "Hello"

    def test_capture_no_groups_returns_match(self) -> None:
        """Test capture returns full match when pattern has no groups."""
        capture = Capture(pattern=r"Hello")
        result = capture.capture("Hello World")
        assert result == "Hello"

    def test_capture_uses_search_when_match_fails(self) -> None:
        """Test that capture uses search when match fails."""
        capture = Capture(pattern=r"(\w+)$")  # End of string
        result = capture.capture("Hello World")
        assert result == "World"

    def test_fix_json_repair_enabled(self) -> None:
        """Test fix method with JSON repair enabled."""
        with patch("fabricatio_core.parser.CONFIG") as mock_config:
            mock_config.general.use_json_repair = True
            with patch("fabricatio_core.parser.repair_json") as mock_repair:
                mock_repair.return_value = '{"fixed": true}'

                capture = Capture(pattern=r"(.*)", capture_type="json")
                result = capture.fix('{"broken": json}')

                mock_repair.assert_called_once_with('{"broken": json}', ensure_ascii=False)
                assert result == '{"fixed": true}'

    def test_fix_json_repair_disabled(self) -> None:
        """Test fix method with JSON repair disabled."""
        with patch("fabricatio_core.parser.CONFIG") as mock_config:
            mock_config.general.use_json_repair = False

            capture = Capture(pattern=r"(.*)", capture_type="json")
            result = capture.fix('{"broken": json}')

            assert result == '{"broken": json}'

    def test_fix_non_json_type(self) -> None:
        """Test fix method with non-JSON capture type."""
        capture = Capture(pattern=r"(.*)", capture_type="python")
        result = capture.fix("print('hello')")
        assert result == "print('hello')"

    def test_fix_no_capture_type(self) -> None:
        """Test fix method with no capture type."""
        capture = Capture(pattern=r"(.*)")
        result = capture.fix("some text")
        assert result == "some text"

    def test_convert_with_success(self) -> None:
        """Test convert_with method with successful conversion."""
        capture = Capture(pattern=r"(\d+)")
        result = capture.convert_with("The number is 42", int)
        assert result == 42

    def test_convert_with_no_capture(self) -> None:
        """Test convert_with returns None when capture fails."""
        capture = Capture(pattern=r"xyz")
        result = capture.convert_with("Hello World", str.upper)
        assert result is None

    def test_convert_with_conversion_error(self) -> None:
        """Test convert_with returns None when conversion fails."""
        capture = Capture(pattern=r"(\w+)")
        result = capture.convert_with("Hello", int)  # Can't convert "Hello" to int
        assert result is None

    def test_validate_with_success(self) -> None:
        """Test validate_with with successful validation."""
        capture = Capture(pattern=r"(\[.*\])")
        text = "Data: [1, 2, 3]"
        result = capture.validate_with(text, list, int, length=3)
        assert result == [1, 2, 3]

    def test_validate_with_wrong_type(self) -> None:
        """Test validate_with returns None for wrong type."""
        capture = Capture(pattern=r"(\{.*\})")
        text = 'Data: {"key": "value"}'
        result = capture.validate_with(text, list)  # Expect list but get dict
        assert result is None

    def test_validate_with_wrong_element_type(self) -> None:
        """Test validate_with returns None for wrong element type."""
        capture = Capture(pattern=r"(\[.*\])")
        text = 'Data: ["a", "b", "c"]'
        result = capture.validate_with(text, list, int)  # Expect int elements but get str
        assert result is None

    def test_validate_with_wrong_length(self) -> None:
        """Test validate_with returns None for wrong length."""
        capture = Capture(pattern=r"(\[.*\])")
        text = "Data: [1, 2, 3]"
        result = capture.validate_with(text, list, int, length=5)  # Expect 5 but get 3
        assert result is None

    def test_validate_with_custom_deserializer(self) -> None:
        """Test validate_with with custom deserializer."""

        def custom_deserializer(text: str) -> list[str]:
            return text.split(",")

        capture = Capture(pattern=r"(\w+,\w+,\w+)")
        text = "Values: a,b,c"
        result = capture.validate_with(text, list, str, deserializer=custom_deserializer)
        assert result == ["a", "b", "c"]

    def test_validate_with_no_capture(self) -> None:
        """Test validate_with returns None when capture fails."""
        capture = Capture(pattern=r"xyz")
        result = capture.validate_with("Hello World", str)
        assert result is None


class TestCaptureClassMethods:
    """Test cases for Capture class methods."""

    def test_capture_code_block(self) -> None:
        """Test capture_code_block class method."""
        capture = Capture.capture_code_block("python")
        text = "```python\nprint('hello')\n```"
        result = capture.capture(text)
        assert result == "print('hello')"
        assert capture.capture_type == "python"

    def test_capture_code_block_caching(self) -> None:
        """Test that capture_code_block results are cached."""
        capture1 = Capture.capture_code_block("python")
        capture2 = Capture.capture_code_block("python")
        assert capture1 is capture2  # Same object due to caching

    def test_capture_generic_block(self) -> None:
        """Test capture_generic_block class method."""
        capture = Capture.capture_generic_block("Data")
        text = "--- Start of Data ---\nsome data here\n--- End of Data ---"
        result = capture.capture(text)
        assert result == "some data here"
        assert capture.capture_type == "Data"

    def test_capture_generic_block_caching(self) -> None:
        """Test that capture_generic_block results are cached."""
        capture1 = Capture.capture_generic_block("Data")
        capture2 = Capture.capture_generic_block("Data")
        assert capture1 is capture2  # Same object due to caching

    def test_capture_content_with_same_delimiters(self) -> None:
        """Test capture_content with same left and right delimiters."""
        capture = Capture.capture_content(r"\*\*\*")
        text = "***important content***"
        result = capture.capture(text)
        assert result == "important content"

    def test_capture_content_with_different_delimiters(self) -> None:
        """Test capture_content with different left and right delimiters."""
        capture = Capture.capture_content("<<", ">>")
        text = "<<captured text>>"
        result = capture.capture(text)
        assert result == "captured text"

    def test_capture_content_caching(self) -> None:
        """Test that capture_content results are cached."""
        capture1 = Capture.capture_content("***")
        capture2 = Capture.capture_content("***")
        assert capture1 is capture2  # Same object due to caching


class TestPredefinedCaptures:
    """Test cases for predefined capture instances."""

    def test_json_capture(self) -> None:
        """Test JsonCapture predefined instance."""
        text = '```json\n{"key": "value"}\n```'
        result = JsonCapture.capture(text)
        assert result == '{"key": "value"}'
        assert JsonCapture.capture_type == "json"

    def test_python_capture(self) -> None:
        """Test PythonCapture predefined instance."""
        text = "```python\nprint('hello')\n```"
        result = PythonCapture.capture(text)
        assert result == "print('hello')"
        assert PythonCapture.capture_type == "python"

    def test_generic_capture(self) -> None:
        """Test GenericCapture predefined instance."""
        text = "--- Start of String ---\nsome string data\n--- End of String ---"
        result = GenericCapture.capture(text)
        assert result == "some string data"
        assert GenericCapture.capture_type == "String"


class TestCaptureFlags:
    """Test cases for regex flags behavior."""

    def test_default_flags(self) -> None:
        """Test that default flags work correctly."""
        capture = Capture(pattern=r"hello (\w+)")

        # Test IGNORECASE
        result = capture.capture("HELLO world")
        assert result == "world"

        # Test MULTILINE and DOTALL
        multiline_text = "hello\nworld\ntest"
        capture_multiline = Capture(pattern=r"hello\n(.*)\ntest")
        result = capture_multiline.capture(multiline_text)
        assert result == "world"

    def test_custom_flags(self) -> None:
        """Test capture with custom flags."""
        import re

        capture = Capture(pattern=r"hello (\w+)", flags=re.IGNORECASE)

        result = capture.capture("HELLO world")
        assert result == "world"


class TestCaptureEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_pattern(self) -> None:
        """Test capture with empty pattern."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            _ = Capture(pattern=r"")

    def test_complex_nested_pattern(self) -> None:
        """Test capture with complex nested pattern."""
        capture = Capture(pattern=r"data:\s*\{([^}]+)\}")
        text = "data: {name: 'test', value: 42}"
        result = capture.capture(text)
        assert "name: 'test', value: 42" in result
