import pytest
from fabricatio import parser


def test_capture_init():
    """Test basic initialization of Capture class."""
    # Test with minimal parameters
    capture = parser.Capture(pattern="test")
    assert capture.pattern == "test"
    assert capture.flags == parser.re.DOTALL | parser.re.MULTILINE | parser.re.IGNORECASE
    assert capture.capture_type is None
    assert capture.target_groups == tuple()

    # Test with all parameters
    capture = parser.Capture(pattern="test", flags=parser.re.ASCII, capture_type="json", target_groups=(1, 2))
    assert capture.pattern == "test"
    assert capture.flags == parser.re.ASCII
    assert capture.capture_type == "json"
    assert capture.target_groups == (1, 2)


def test_capture_method():
    """Test the capture method with different patterns and inputs."""
    # Test simple capture
    capture = parser.Capture(pattern="hello")
    result = capture.capture("hello world")
    assert result == "hello"

    # Test capture with groups
    capture = parser.Capture(pattern="(\\w+) (\\d+)", target_groups=(1, 2))
    result = capture.capture("name 42")
    assert isinstance(result, tuple)
    assert result == ("name", "42")

    # Test failed capture
    capture = parser.Capture(pattern="goodbye")
    result = capture.capture("hello world")
    assert result is None


def test_fix_method():
    """Test the fix method with different capture_types."""
    # Test without JSON repair
    capture = parser.Capture(pattern="test")
    assert capture.fix("simple text") == "simple text"

    # Test with JSON repair when use_json_repair is False
    capture = parser.Capture(pattern="test", capture_type="json")
    assert capture.fix("{invalid}") == "{invalid}"

    # Test with JSON repair when use_json_repair is True
    capture = parser.Capture(pattern="test", capture_type="json")
    capture.CONFIG = type("Config", (), {"general": type("General", (), {"use_json_repair": True})})

    # Test valid JSON stays unchanged
    valid_json = '{"valid": "json"}'
    assert capture.fix(valid_json) == {"valid": "json"}

    # Test invalid JSON gets repaired
    invalid_json = "{invalid} json"
    result = capture.fix(invalid_json)
    assert isinstance(result, dict)
    assert "error" in result or "valid" in result  # The exact behavior depends on repair_json


def test_convert_with():
    """Test the convert_with method with different functions."""
    capture = parser.Capture(pattern=r"(\d+)", target_groups=(1,))

    # Test successful conversion
    def to_int(x):
        return int(x)

    result = capture.convert_with("age: 42", to_int)
    assert result == 42

    # Test failed conversion
    def fail_func(x):
        raise ValueError("Conversion failed")

    result = capture.convert_with("age: 42", fail_func)
    assert result is None


def test_validate_with():
    """Test the validate_with method with different types."""
    capture = parser.Capture(pattern=r"(\d+)", target_groups=(1,))

    # Test basic type validation
    result = capture.validate_with("age: 42", int)
    assert result == 42

    # Test list validation
    result = capture.validate_with("[1, 2, 3]", list, elements_type=int)
    assert result == [1, 2, 3]

    # Test length validation
    result = capture.validate_with("[1, 2]", list, length=2)
    assert result == [1, 2]

    # Test failure cases
    assert capture.validate_with("not a number", int) is None
    assert capture.validate_with("[1, 'a']", list, elements_type=int) is None
    assert capture.validate_with("[1, 2, 3]", list, length=2) is None


def test_class_methods():
    """Test the class methods for capturing code blocks."""
    # Test capture_code_block
    code_block = parser.Capture.capture_code_block("python")
    assert "```python" in code_block.pattern
    assert code_block.capture_type == "python"

    # Test capture_generic_block
    generic_block = parser.Capture.capture_generic_block("string")
    assert "--- Start of string ---" in generic_block.pattern
    assert generic_block.capture_type == "string"


def test_json_and_python_capture():
    """Test the pre-configured JSON and Python capture instances."""
    # Test JsonCapture
    json_content = '{\n    "key": "value"\n}'
    json_block = f"```json\n{json_content}\n```"
    result = parser.JsonCapture.capture(json_block)
    assert result == json_content

    # Test PythonCapture
    python_content = "print('hello')"
    python_block = f"```python\n{python_content}\n```"
    result = parser.PythonCapture.capture(python_block)
    assert result == python_content


def test_capture_edge_cases():
    """Test edge cases for the Capture class."""
    # Test empty pattern
    with pytest.raises(parser.re.error):
        parser.Capture(pattern="")

    # Test invalid regex
    with pytest.raises(parser.re.error):
        parser.Capture(pattern="*invalid_regex")

    # Test capture with multiple matches
    capture = parser.Capture(pattern="(\\w+) (\\d+)")
    result = capture.capture("name 42 age 30")
    assert result == ("name", "42")

    # Test capture with no match
    result = capture.capture("no numbers here")
    assert result is None


def test_convert_all():
    """Test the full capture -> convert -> validate workflow."""
    capture = parser.Capture(pattern=r"(\d+)", target_groups=(1,))

    # Test string to int conversion
    result = capture.convert_with("age: 42", lambda x: int(x))
    assert result == 42

    # Test string to str conversion (should work too)
    result = capture.convert_with("age: 42", str)
    assert result == "42"

    # Test failed conversion
    result = capture.convert_with("age: forty-two", lambda x: int(x))
    assert result is None


def test_capture_code_block_invalid_input():
    """Test code block capture with invalid input."""
    code_block = parser.Capture.capture_code_block("python")
    # Test with non-matching input
    result = code_block.capture("this is not a code block")
    assert result is None

    # Test with partial code block
    partial_block = "```python\nprint('hello')"
    result = code_block.capture(partial_block)
    assert result is None


def test_capture_generic_block_invalid_input():
    """Test generic block capture with invalid input."""
    generic_block = parser.Capture.capture_generic_block("string")

    # Test with non-matching input
    result = generic_block.capture("not a block")
    assert result is None

    # Test with partial block
    partial_block = "--- Start of string ---\nSome content"
    result = generic_block.capture(partial_block)
    assert result is None
