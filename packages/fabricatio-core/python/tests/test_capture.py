"""Test module for parser functionality including TextCapturer, JsonParser, CodeBlockParser, and related classes.

This module contains pytest test cases for verifying the correctness of text parsing,
pattern capture, JSON parsing and validation, code block extraction, and snippet parsing
operations exposed from the Rust implementation via PyO3.

Tests cover both successful execution paths and error handling scenarios.
"""

from fabricatio_core.rust import (
    CodeBlockParser,
    CodeSnippet,
    CodeSnippetParser,
    ContentBlockParser,
    GenericBlockParser,
    JsonParser,
    TextCapturer,
    generic_parser,
    json_parser,
    python_parser,
    snippet_parser,
)

# =============================================================================
# TextCapturer Tests
# =============================================================================


class TestTextCapturer:
    """Test suite for TextCapturer class."""

    def test_with_pattern_basic_capture(self) -> None:
        """Test creating a TextCapturer with a basic pattern and capturing."""
        capturer = TextCapturer.with_pattern(r"hello (\w+) world")
        result = capturer.cap1("hello foo world")
        assert result == "foo"

    def test_cap1_returns_none_when_no_match(self) -> None:
        """Test that cap1 returns None when no match is found."""
        capturer = TextCapturer.with_pattern(r"hello (\w+) world")
        result = capturer.cap1("goodbye foo world")
        assert result is None

    def test_cap1_all_multiple_matches(self) -> None:
        """Test cap1_all returns all matches."""
        capturer = TextCapturer.with_pattern(r"(\d+)")
        result = capturer.cap1_all("123 456 789")
        assert result == ["123", "456", "789"]

    def test_cap1_all_empty_when_no_match(self) -> None:
        """Test cap1_all returns empty list when no matches."""
        capturer = TextCapturer.with_pattern(r"(\d+)")
        result = capturer.cap1_all("abc def ghi")
        assert result == []

    def test_cap2_single_match(self) -> None:
        """Test cap2 captures two groups."""
        capturer = TextCapturer.with_pattern(r"(\w+) (\w+)")
        result = capturer.cap2("hello world")
        assert result == ("hello", "world")

    def test_cap2_all_multiple_matches(self) -> None:
        """Test cap2_all returns all two-group matches."""
        capturer = TextCapturer.with_pattern(r"(\w+)-(\w+)")
        result = capturer.cap2_all("foo-bar baz-qux")
        assert result == [("foo", "bar"), ("baz", "qux")]

    def test_cap3_single_match(self) -> None:
        """Test cap3 captures three groups."""
        capturer = TextCapturer.with_pattern(r"(\w+)\s+(\w+)\s+(\w+)")
        result = capturer.cap3("one two three")
        assert result == ("one", "two", "three")

    def test_cap3_all_multiple_matches(self) -> None:
        """Test cap3_all returns all three-group matches."""
        capturer = TextCapturer.with_pattern(r"(\w+):(\w+):(\w+)")
        result = capturer.cap3_all("a:b:c x:y:z")
        assert result == [("a", "b", "c"), ("x", "y", "z")]

    def test_capture_code_block_default_language(self) -> None:
        """Test capture_code_block factory method with default language."""
        capturer = TextCapturer.capture_code_block()
        text = "Some text\n```\ncode here\n```\nMore text"
        result = capturer.cap1(text)
        assert result == "code here"

    def test_capture_code_block_specific_language(self) -> None:
        """Test capture_code_block factory method with specific language."""
        capturer = TextCapturer.capture_code_block("python")
        text = "Some text\n```python\nprint('hello')\n```\nMore text"
        result = capturer.cap1(text)
        assert result == "print('hello')"

    def test_capture_code_block_no_match_different_language(self) -> None:
        """Test capture_code_block returns None when language doesn't match."""
        capturer = TextCapturer.capture_code_block("python")
        text = "Some text\n```javascript\nconsole.log('hello')\n```\nMore text"
        result = capturer.cap1(text)
        assert result is None

    def test_capture_generic_block_default_type(self) -> None:
        """Test capture_generic_block with default block type 'String'."""
        capturer = TextCapturer.capture_generic_block()
        text = "--- Start of String ---\nSome content\n--- End of String ---"
        result = capturer.cap1(text)
        assert result == "Some content"

    def test_capture_generic_block_custom_type(self) -> None:
        """Test capture_generic_block with custom block type."""
        capturer = TextCapturer.capture_generic_block("CustomType")
        text = "--- Start of CustomType ---\nCustom content\n--- End of CustomType ---"
        result = capturer.cap1(text)
        assert result == "Custom content"

    def test_case_insensitive_matching(self) -> None:
        """Test that patterns are matched case-insensitively due to (?smi) prefix."""
        capturer = TextCapturer.with_pattern(r"HELLO (\w+)")
        result = capturer.cap1("hello world")
        assert result == "world"


# =============================================================================
# JsonParser Tests
# =============================================================================


class TestJsonParser:
    """Test suite for JsonParser class."""

    def test_with_pattern_creates_parser(self) -> None:
        """Test creating a JsonParser with a custom pattern."""
        parser = JsonParser.with_pattern(r"\{.*\}")
        assert parser is not None

    def test_capture_valid_json(self) -> None:
        """Test capturing a valid JSON string."""
        parser = JsonParser.with_pattern(r"```json\s*(.*?)\s*```")
        text = '```json\n{"key": "value"}\n```'
        result = parser.capture(text, fix=False)
        assert result == '{"key": "value"}'

    def test_capture_with_json_repair(self) -> None:
        """Test capturing with JSON repair enabled."""
        parser = JsonParser.with_pattern(r"```json\s*(.*?)\s*```")
        # Missing closing brace - should be repaired
        text = '```json\n{"key": "value"\n```'
        result = parser.capture(text, fix=True)
        assert result is not None
        assert '"key"' in result

    def test_capture_returns_none_when_no_match(self) -> None:
        """Test that capture returns None when no match is found."""
        parser = JsonParser.with_pattern(r"```json\s*(.*?)\s*```")
        text = "No JSON here"
        result = parser.capture(text, fix=False)
        assert result is None

    def test_capture_all_multiple_json_blocks(self) -> None:
        """Test capturing all JSON blocks from text."""
        parser = JsonParser.with_pattern(r"```json\s*(.*?)\s*```")
        text = '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```'
        result = parser.capture_all(text, fix=False)
        assert len(result) == 2
        assert result[0] == '{"a": 1}'
        assert result[1] == '{"b": 2}'

    def test_convert_to_python_dict(self) -> None:
        """Test converting captured JSON to Python dict."""
        parser = JsonParser.with_pattern(r"\{[^}]+\}")
        text = '{"key": "value"}'
        result = parser.convert(text, fix=False)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_convert_to_python_list(self) -> None:
        """Test converting captured JSON to Python list."""
        parser = JsonParser.with_pattern(r"\[[^\]]+\]")
        text = "[1, 2, 3]"
        result = parser.convert(text, fix=False)
        assert isinstance(result, list)
        assert result == [1, 2, 3]

    def test_convert_all_multiple_json_objects(self) -> None:
        """Test converting all captured JSON objects."""
        parser = JsonParser.with_pattern(r"```json\s*(.*?)\s*```")
        text = '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```'
        results = parser.convert_all(text, fix=False)
        assert len(results) == 2
        assert results[0]["a"] == 1
        assert results[1]["b"] == 2

    def test_validate_list_success(self) -> None:
        """Test validate_list with valid list."""
        parser = JsonParser.with_pattern(r"\[.*\]")
        text = '["a", "b", "c"]'
        result = parser.validate_list(text, length=3, fix=False)
        assert result is not None
        assert len(result) == 3

    def test_validate_list_wrong_length(self) -> None:
        """Test validate_list returns None when length doesn't match."""
        parser = JsonParser.with_pattern(r"\[.*\]")
        text = '["a", "b", "c"]'
        result = parser.validate_list(text, length=5, fix=False)
        assert result is None

    def test_validate_dict_success(self) -> None:
        """Test validate_dict with valid dict."""
        parser = JsonParser.with_pattern(r"\{.*\}")
        text = '{"key": "value"}'
        result = parser.validate_dict(text, length=1, fix=False)
        assert result is not None
        assert len(result) == 1

    def test_validate_dict_wrong_length(self) -> None:
        """Test validate_dict returns None when length doesn't match."""
        parser = JsonParser.with_pattern(r"\{.*\}")
        text = '{"key": "value"}'
        result = parser.validate_dict(text, length=5, fix=False)
        assert result is None


# =============================================================================
# CodeBlockParser Tests
# =============================================================================


class TestCodeBlockParser:
    """Test suite for CodeBlockParser class."""

    def test_with_language_python(self) -> None:
        """Test creating a CodeBlockParser for Python."""
        parser = CodeBlockParser.with_language("python")
        assert parser is not None
        assert parser.language == "python"

    def test_with_language_javascript(self) -> None:
        """Test creating a CodeBlockParser for JavaScript."""
        parser = CodeBlockParser.with_language("javascript")
        assert parser.language == "javascript"

    def test_capture_single_code_block(self) -> None:
        """Test capturing a single code block."""
        parser = CodeBlockParser.with_language("python")
        text = "Some text\n```python\nprint('hello')\n```\nMore text"
        result = parser.capture(text)
        assert result == "print('hello')"

    def test_capture_no_match(self) -> None:
        """Test capture returns None when no matching code block."""
        parser = CodeBlockParser.with_language("python")
        text = "Some text\n```javascript\nconsole.log('hello')\n```\nMore text"
        result = parser.capture(text)
        assert result is None

    def test_capture_all_multiple_code_blocks(self) -> None:
        """Test capturing all code blocks of specified language."""
        parser = CodeBlockParser.with_language("python")
        text = "```python\ncode1\n```\n```python\ncode2\n```\n```javascript\njs_code\n```"
        result = parser.capture_all(text)
        assert len(result) == 2
        assert result[0] == "code1"
        assert result[1] == "code2"

    def test_capture_all_no_matches(self) -> None:
        """Test capture_all returns empty list when no matches."""
        parser = CodeBlockParser.with_language("rust")
        text = "```python\ncode1\n```\n```python\ncode2\n```"
        result = parser.capture_all(text)
        assert result == []

    def test_capture_with_default_language(self) -> None:
        """Test capturing code block with default (any) language."""
        parser = CodeBlockParser.with_language(".*?")
        text = "```\nany code\n```"
        result = parser.capture(text)
        assert result == "any code"

    def test_capture_multiline_code(self) -> None:
        """Test capturing multiline code block."""
        parser = CodeBlockParser.with_language("python")
        text = "```python\ndef foo():\n    return 42\n```"
        result = parser.capture(text)
        assert "def foo():" in result
        assert "return 42" in result


# =============================================================================
# CodeSnippetParser Tests
# =============================================================================


class TestCodeSnippetParser:
    """Test suite for CodeSnippetParser class."""

    def test_with_separators_default(self) -> None:
        """Test creating a CodeSnippetParser with default separators."""
        parser = CodeSnippetParser.with_separators()
        assert parser is not None
        assert parser.left_sep == ">>>>>"
        assert parser.right_sep == "<<<<<"

    def test_with_separators_custom(self) -> None:
        """Test creating a CodeSnippetParser with custom separators."""
        parser = CodeSnippetParser.with_separators("<<<<", ">>>>")
        assert parser.left_sep == "<<<<"
        assert parser.right_sep == ">>>>"

    def test_parse_single_snippet(self) -> None:
        r"""Test parsing a single snippet with correct format.

        Format: {prefix}\n{sep}{language}\n{source}\n{rsep}$
        """
        parser = CodeSnippetParser.with_separators()
        # Pattern: ^(.*?)\n{l_sep}(.*?)\n(.*?)\n{r_sep}$
        # Groups: prefix, language, source
        # Note: separator and language are directly adjacent: >>>>>python
        text = "path\n>>>>>python\nprint('hello')\n<<<<<"
        result = parser.parse(text)
        assert len(result) == 1
        assert result[0].language == "python"
        assert result[0].source == "print('hello')"

    def test_parse_multiple_snippets(self) -> None:
        """Test parsing multiple snippets."""
        parser = CodeSnippetParser.with_separators()
        # Need \n\n between closing <<<<< and next prefix
        text = "path1\n>>>>>python\ncode1\n<<<<<\n\npath2\n>>>>>javascript\ncode2\n<<<<<"
        result = parser.parse(text)
        assert len(result) == 2
        assert result[0].language == "python"
        assert result[1].language == "javascript"

    def test_parse_returns_code_snippet_objects(self) -> None:
        """Test that parse returns CodeSnippet objects."""
        parser = CodeSnippetParser.with_separators()
        text = "path\n>>>>>python\npass\n<<<<<"
        result = parser.parse(text)
        assert len(result) == 1
        assert isinstance(result[0], CodeSnippet)
        assert hasattr(result[0], "source")
        assert hasattr(result[0], "language")
        assert hasattr(result[0], "write_to")

    def test_parse_no_matches(self) -> None:
        """Test parse returns empty list when no snippets found."""
        parser = CodeSnippetParser.with_separators()
        text = "No snippets here"
        result = parser.parse(text)
        assert result == []


# =============================================================================
# GenericBlockParser Tests
# =============================================================================


class TestGenericBlockParser:
    """Test suite for GenericBlockParser class."""

    def test_with_block_type_default(self) -> None:
        """Test creating a GenericBlockParser with default type 'String'."""
        parser = GenericBlockParser.with_block_type()
        assert parser is not None
        assert parser.block_type == "String"

    def test_with_block_type_custom(self) -> None:
        """Test creating a GenericBlockParser with custom type."""
        parser = GenericBlockParser.with_block_type("MyType")
        assert parser.block_type == "MyType"

    def test_capture_single_block(self) -> None:
        """Test capturing a single generic block."""
        parser = GenericBlockParser.with_block_type()
        text = "--- Start of String ---\nBlock content\n--- End of String ---"
        result = parser.capture(text)
        assert result == "Block content"

    def test_capture_no_match(self) -> None:
        """Test capture returns None when block doesn't match."""
        parser = GenericBlockParser.with_block_type()
        text = "--- Start of Number ---\nBlock content\n--- End of Number ---"
        result = parser.capture(text)
        assert result is None

    def test_capture_all_multiple_blocks(self) -> None:
        """Test capturing all generic blocks of specified type."""
        parser = GenericBlockParser.with_block_type()
        text = "--- Start of String ---\nBlock 1\n--- End of String ---\n--- Start of String ---\nBlock 2\n--- End of String ---"
        result = parser.capture_all(text)
        assert len(result) == 2
        assert result[0] == "Block 1"
        assert result[1] == "Block 2"

    def test_capture_all_no_matches(self) -> None:
        """Test capture_all returns empty list when no matches."""
        parser = GenericBlockParser.with_block_type("OtherType")
        text = "--- Start of String ---\nBlock\n--- End of String ---"
        result = parser.capture_all(text)
        assert result == []

    def test_capture_multiline_content(self) -> None:
        """Test capturing multiline generic block content."""
        parser = GenericBlockParser.with_block_type()
        text = "--- Start of String ---\nLine 1\nLine 2\nLine 3\n--- End of String ---"
        result = parser.capture(text)
        assert result == "Line 1\nLine 2\nLine 3"


# =============================================================================
# ContentBlockParser Tests
# =============================================================================


class TestContentBlockParser:
    """Test suite for ContentBlockParser class."""

    def test_with_delimiters_same_delimiter(self) -> None:
        """Test creating a ContentBlockParser with same left and right delimiter."""
        parser = ContentBlockParser.with_delimiters("||")
        assert parser is not None
        assert parser.left_delimiter == "||"
        assert parser.right_delimiter == "||"

    def test_with_delimiters_different_delimiters(self) -> None:
        """Test creating a ContentBlockParser with different delimiters."""
        parser = ContentBlockParser.with_delimiters("[[", "]]")
        assert parser.left_delimiter == "[["
        assert parser.right_delimiter == "]]"


# =============================================================================
# Module-level Parser Instances Tests
# =============================================================================


class TestModuleLevelParsers:
    """Test suite for module-level parser instances."""

    def test_json_parser_exists(self) -> None:
        """Test that json_parser instance exists."""
        assert json_parser is not None
        assert isinstance(json_parser, JsonParser)

    def test_python_parser_exists(self) -> None:
        """Test that python_parser instance exists."""
        assert python_parser is not None
        assert isinstance(python_parser, CodeBlockParser)
        assert python_parser.language == "python"

    def test_generic_parser_exists(self) -> None:
        """Test that generic_parser instance exists."""
        assert generic_parser is not None
        assert isinstance(generic_parser, GenericBlockParser)
        assert generic_parser.block_type == "String"

    def test_snippet_parser_exists(self) -> None:
        """Test that snippet_parser instance exists."""
        assert snippet_parser is not None
        assert isinstance(snippet_parser, CodeSnippetParser)
        assert snippet_parser.left_sep == ">>>>>"
        assert snippet_parser.right_sep == "<<<<<"

    def test_json_parser_capture_with_defaults(self) -> None:
        """Test json_parser can capture JSON code blocks."""
        text = '```json\n{"key": "value"}\n```'
        result = json_parser.capture(text, fix=False)
        assert result is not None
        assert "key" in result

    def test_python_parser_capture_code(self) -> None:
        """Test python_parser can capture Python code blocks."""
        text = "```python\nprint('hello')\n```"
        result = python_parser.capture(text)
        assert result is not None
        assert "print" in result

    def test_generic_parser_capture_block(self) -> None:
        """Test generic_parser can capture generic blocks."""
        text = "--- Start of String ---\nContent\n--- End of String ---"
        result = generic_parser.capture(text)
        assert result == "Content"
