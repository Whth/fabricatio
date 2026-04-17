"""Tests for the Rust-backed parsers in fabricatio_core.rust module."""

from fabricatio_core.rust import (
    CodeBlockParser,
    CodeSnippetParser,
    ContentBlockParser,
    GenericBlockParser,
    TextCapturer,
    generic_parser,
    json_parser,
    python_parser,
    snippet_parser,
)
from fabricatio_mock.utils import generic_block


class TestTextCapturer:
    """Test cases for the TextCapturer class."""

    def test_basic_capture_success(self) -> None:
        """Test successful pattern capture."""
        capturer = TextCapturer.with_pattern(r"Hello (\w+)")
        result = capturer.cap("Hello World!")
        assert result == "Hello World!"

    def test_capture_no_match(self) -> None:
        """Test capture returns None when no match."""
        capturer = TextCapturer.with_pattern(r"xyz")
        result = capturer.cap("Hello World")
        assert result is None

    def test_capture_all(self) -> None:
        """Test capture all matches."""
        capturer = TextCapturer.with_pattern(r"(\w+)")
        result = capturer.cap_all("Hello World")
        assert result == ["Hello", "World"]

    def test_capture_empty_text(self) -> None:
        """Test capture with empty text returns None."""
        capturer = TextCapturer.with_pattern(r"pattern")
        result = capturer.cap("")
        assert result is None

    def test_capture_all_empty_text(self) -> None:
        """Test capture_all with empty text returns empty list."""
        capturer = TextCapturer.with_pattern(r"pattern")
        result = capturer.cap_all("")
        assert result == []

    def test_capture_multiline(self) -> None:
        """Test capture with multiline text."""
        capturer = TextCapturer.with_pattern(r"start (.*) end")
        result = capturer.cap("start middle end")
        assert result == "middle"

    def test_capture_special_characters(self) -> None:
        """Test capture with special regex characters."""
        capturer = TextCapturer.with_pattern(r"\$([0-9]+)")
        result = capturer.cap("Price is $100")
        assert result == "100"

    def test_capture_group_only(self) -> None:
        """Test capture returns first group when groups exist."""
        capturer = TextCapturer.with_pattern(r"(\w+) (\w+)")
        result = capturer.cap("Hello World")
        assert result == "Hello"

    def test_capture_no_group_returns_full_match(self) -> None:
        """Test capture returns full match when no groups."""
        capturer = TextCapturer.with_pattern(r"Hello")
        result = capturer.cap("Hello World")
        assert result == "Hello"

    def test_capture_all_with_multiple_matches(self) -> None:
        """Test capture_all with multiple matches."""
        capturer = TextCapturer.with_pattern(r"<(\w+)>")
        result = capturer.cap_all("<a><b><c>")
        assert result == ["a", "b", "c"]

    def test_capture_content_factory(self) -> None:
        """Test capture_content factory method."""
        capturer = TextCapturer.capture_content("[[", "]]")
        result = capturer.cap("[[content]]")
        assert result == "content"

    def test_capture_code_block_factory(self) -> None:
        """Test capture_code_block factory method."""
        capturer = TextCapturer.capture_code_block("rust")
        text = "```rust\nfn main() {}\n```"
        result = capturer.cap(text)
        assert result == "fn main() {}"

    def test_capture_generic_block_factory(self) -> None:
        """Test capture_generic_block factory method."""
        capturer = TextCapturer.capture_generic_block("Config")
        text = "--- Start of Config ---\nname = value\n--- End of Config ---"
        result = capturer.cap(text)
        assert result == "name = value"

    def test_capture_snippet_factory(self) -> None:
        """Test capture_snippet factory method."""
        capturer = TextCapturer.capture_snippet("<<<<<<", ">>>>>>")
        result = capturer.cap("<<<<<<content>>>>>>")
        assert result == "content"


class TestJsonParser:
    """Test cases for the JsonParser class."""

    def test_capture_json_block(self) -> None:
        """Test capturing JSON from code block."""
        text = '```json\n{"key": "value"}\n```'
        result = json_parser.capture(text, False)
        assert result == '{"key": "value"}'
        result = json_parser.capture(text, True)
        assert result == '{"key":"value"}'

    def test_capture_all_json_blocks(self) -> None:
        """Test capturing all JSON blocks."""
        text = '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```'
        result = json_parser.capture_all(text)
        assert len(result) == 2

    def test_convert_json(self) -> None:
        """Test converting JSON to Python object."""
        text = '{"key": "value"}'
        result = json_parser.convert(text)
        assert result == {"key": "value"}

    def test_convert_list(self) -> None:
        """Test converting JSON list to Python list."""
        text = '["a", "b", "c"]'
        result = json_parser.convert(text)
        assert result == ["a", "b", "c"]

    def test_convert_nested_json(self) -> None:
        """Test converting nested JSON."""
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = json_parser.convert(text)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_validate_list(self) -> None:
        """Test validating a JSON list."""
        text = '["a", "b", "c"]'
        result = json_parser.validate_list(text, elements_type=str, length=3)
        assert result == ["a", "b", "c"]

    def test_validate_list_with_length(self) -> None:
        """Test validating list with exact length."""
        text = '["x", "y"]'
        result = json_parser.validate_list(text, elements_type=str, length=2)
        assert result == ["x", "y"]

    def test_validate_list_wrong_length(self) -> None:
        """Test validating list with wrong length returns None."""
        text = '["a", "b", "c"]'
        result = json_parser.validate_list(text, elements_type=str, length=5)
        assert result is None

    def test_validate_list_wrong_element_type(self) -> None:
        """Test validating list with wrong element type returns None."""
        text = '["a", "b", "c"]'
        result = json_parser.validate_list(text, elements_type=int, length=None)
        assert result is None

    def test_validate_dict(self) -> None:
        """Test validating a JSON dict."""
        text = '{"key": "value"}'
        result = json_parser.validate_dict(text, key_type=str, value_type=str, length=None)
        assert result == {"key": "value"}

    def test_validate_dict_with_length(self) -> None:
        """Test validating dict with exact length."""
        text = '{"a": 1, "b": 2}'
        result = json_parser.validate_dict(text, key_type=str, value_type=int, length=2)
        assert result == {"a": 1, "b": 2}

    def test_validate_dict_wrong_key_type(self) -> None:
        """Test validating dict with wrong key type returns None."""
        text = '{"a": 1, "b": 2}'
        result = json_parser.validate_dict(text, key_type=int, value_type=int, length=None)
        assert result is None

    def test_validate_dict_wrong_value_type(self) -> None:
        """Test validating dict with wrong value type returns None."""
        text = '{"a": "str", "b": "str"}'
        result = json_parser.validate_dict(text, key_type=str, value_type=int, length=None)
        assert result is None

    def test_convert_all(self) -> None:
        """Test convert_all extracts all JSON objects."""
        text = '```json\n{"a": 1}\n``` and ```json\n{"b": 2}\n```'
        result = json_parser.convert_all(text)
        assert len(result) == 2
        assert result[0] == {"a": 1}
        assert result[1] == {"b": 2}

    def test_capture_no_json_block(self) -> None:
        """Test capture returns None when no JSON block found."""
        text = "no json here"
        result = json_parser.capture(text)
        assert result is None


class TestCodeBlockParser:
    """Test cases for the CodeBlockParser class."""

    def test_capture_python_block(self) -> None:
        """Test capturing Python code block."""
        text = "```python\nprint('hello')\n```"
        result = python_parser.capture(text)
        assert result == "print('hello')"

    def test_capture_all_python_blocks(self) -> None:
        """Test capturing all Python code blocks."""
        text = "```python\na = 1\n```\n```python\nb = 2\n```"
        result = python_parser.capture_all(text)
        assert len(result) == 2

    def test_custom_language_parser(self) -> None:
        """Test creating parser for custom language."""
        cpp_parser = CodeBlockParser.with_language("cpp")
        text = "```cpp\nint x = 42;\n```"
        result = cpp_parser.capture(text)
        assert result == "int x = 42;"

    def test_capture_javascript_block(self) -> None:
        """Test capturing JavaScript code block."""
        js_parser = CodeBlockParser.with_language("javascript")
        text = "```javascript\nconst x = () => 42;\n```"
        result = js_parser.capture(text)
        assert result == "const x = () => 42;"

    def test_capture_all_with_language(self) -> None:
        """Test capturing all blocks of specific language."""
        rust_parser = CodeBlockParser.with_language("rust")
        text = "```rust\nfn a() {}\n```\n```python\ndef b():\n```\n```rust\nfn c() {}\n```"
        result = rust_parser.capture_all(text)
        assert len(result) == 2
        assert "fn a()" in result[0]
        assert "fn c()" in result[1]

    def test_capture_no_code_block(self) -> None:
        """Test capture returns None when no code block found."""
        text = "no code block here"
        result = python_parser.capture(text)
        assert result is None

    def test_capture_language_property(self) -> None:
        """Test language property returns correct language."""
        parser = CodeBlockParser.with_language("go")
        assert parser.language == "go"

    def test_capture_multiline_code_block(self) -> None:
        """Test capturing multiline code block."""
        text = """```python
def func():
    if True:
        return "indented"
    return "not reached"
```"""
        result = python_parser.capture(text)
        assert "def func():" in result
        assert 'return "indented"' in result

    def test_capture_with_special_characters(self) -> None:
        """Test capturing code block with special characters."""
        text = '```python\nprint("hello #{world}")\n```'
        result = python_parser.capture(text)
        assert result == 'print("hello #{world}")'


class TestGenericBlockParser:
    """Test cases for the GenericBlockParser class."""

    def test_capture_generic_block(self) -> None:
        """Test capturing generic block."""
        text = generic_block("some data")
        result = generic_parser.capture(text)
        assert result == "some data"

    def test_capture_all_generic_blocks(self) -> None:
        """Test capturing all generic blocks."""
        text = "--- Start of String ---\ndata1\n--- End of String ---\n--- Start of String ---\ndata2\n--- End of String ---"
        result = generic_parser.capture_all(text)
        assert len(result) == 2
        assert result[0] == "data1"
        assert result[1] == "data2"

    def test_custom_block_type(self) -> None:
        """Test creating parser for custom block type."""
        custom_parser = GenericBlockParser.with_block_type("CustomType")
        text = "--- Start of CustomType ---\ncontent\n--- End of CustomType ---"
        result = custom_parser.capture(text)
        assert result == "content"

    def test_block_type_property(self) -> None:
        """Test block_type property returns correct type."""
        parser = GenericBlockParser.with_block_type("MyType")
        assert parser.block_type == "MyType"

    def test_capture_no_generic_block(self) -> None:
        """Test capture returns None when no generic block found."""
        text = "no generic block here"
        result = generic_parser.capture(text)
        assert result is None

    def test_capture_generic_block_multiline(self) -> None:
        """Test capturing multiline generic block."""
        text = """--- Start of String ---\nname = "test"\nversion = 1.0\nenabled = true\n--- End of String ---"""
        result = generic_parser.capture(text)
        assert result
        assert 'name = "test"' in result
        assert "version = 1.0" in result

    def test_capture_different_types(self) -> None:
        """Test capturing blocks of different types separately."""
        parser_a = GenericBlockParser.with_block_type("A")
        parser_b = GenericBlockParser.with_block_type("B")
        text = """--- Start of A ---
content A
--- End of A ---
--- Start of B ---
content B
--- End of B ---"""
        result_a = parser_a.capture(text)
        result_b = parser_b.capture(text)
        assert result_a == "content A"
        assert result_b == "content B"


class TestContentBlockParser:
    """Test cases for the ContentBlockParser class."""

    def test_capture_with_same_delimiters(self) -> None:
        """Test capture with same left and right delimiters."""
        parser = ContentBlockParser.with_delimiters("***")
        text = "***important***"
        result = parser.capture(text)
        assert result == "important"

    def test_capture_with_different_delimiters(self) -> None:
        """Test capture with different left and right delimiters."""
        parser = ContentBlockParser.with_delimiters("<<", ">>")
        text = "<<captured>>"
        result = parser.capture(text)
        assert result == "captured"

    def test_capture_all(self) -> None:
        """Test capturing all content blocks."""
        parser = ContentBlockParser.with_delimiters("[[", "]]")
        text = "[[first]] and [[second]]"
        result = parser.capture_all(text)
        assert result == ["first", "second"]

    def test_delimiter_properties(self) -> None:
        """Test delimiter properties return correct values."""
        parser = ContentBlockParser.with_delimiters("LEFT", "RIGHT")
        assert parser.left_delimiter == "LEFT"
        assert parser.right_delimiter == "RIGHT"

    def test_capture_no_match(self) -> None:
        """Test capture returns None when no match."""
        parser = ContentBlockParser.with_delimiters("[[", "]]")
        text = "no match here"
        result = parser.capture(text)
        assert result is None

    def test_capture_all_no_matches(self) -> None:
        """Test capture_all returns empty list when no matches."""
        parser = ContentBlockParser.with_delimiters("[[", "]]")
        text = "no match here"
        result = parser.capture_all(text)
        assert result == []

    def test_capture_with_newlines(self) -> None:
        """Test capture with newlines in delimiters."""
        parser = ContentBlockParser.with_delimiters("<<<", ">>>")
        text = "<<<\nmultiline\ncontent\n>>>"
        result = parser.capture(text)
        assert result == "\nmultiline\ncontent\n"

    def test_capture_xml_like(self) -> None:
        """Test capturing XML-like content."""
        parser = ContentBlockParser.with_delimiters("<tag>", "</tag>")
        text = "<tag>content here</tag>"
        result = parser.capture(text)
        assert result == "content here"

    def test_capture_all_multiple_matches(self) -> None:
        """Test capturing multiple non-overlapping blocks."""
        parser = ContentBlockParser.with_delimiters("{{", "}}")
        text = "{{a}}{{b}}{{c}}"
        result = parser.capture_all(text)
        assert result == ["a", "b", "c"]


class TestCodeSnippetParser:
    """Test cases for the CodeSnippetParser class."""

    def test_default_separators(self) -> None:
        """Test default separator properties."""
        assert snippet_parser.left_sep == ">>>>>"
        assert snippet_parser.right_sep == "<<<<<"

    def test_parse_basic(self) -> None:
        """Test basic snippet parsing."""
        text = "file1.txt\n<<<<<<\ncontent1\n>>>>>>\nfile2.txt\n<<<<<<\ncontent2\n>>>>>>"
        result = snippet_parser.parse(text)
        assert len(result) == 2

    def test_custom_separators(self) -> None:
        """Test creating parser with custom separators."""
        custom = CodeSnippetParser.with_separators("<<<<<<", ">>>>>>")
        assert custom.left_sep == "<<<<<<"
        assert custom.right_sep == ">>>>>>"

    def test_parse_single_snippet(self) -> None:
        """Test parsing single snippet."""
        text = "path/to/file.txt\n<<<<<<\nfile content\n>>>>>>"
        result = snippet_parser.parse(text)
        assert len(result) == 1

    def test_parse_empty_text(self) -> None:
        """Test parsing empty text returns empty list."""
        result = snippet_parser.parse("")
        assert result == []

    def test_parse_no_snippets(self) -> None:
        """Test parsing text with no snippets."""
        text = "just some regular text without snippets"
        result = snippet_parser.parse(text)
        assert result == []


class TestParserEdgeCases:
    """Test edge cases across all parser types."""

    def test_json_capture_empty_json(self) -> None:
        """Test capturing empty JSON object."""
        text = "```json\n{}\n```"
        result = json_parser.capture(text)
        assert result == "{}"

    def test_json_capture_empty_list(self) -> None:
        """Test capturing empty JSON list."""
        text = "```json\n[]\n```"
        result = json_parser.capture(text)
        assert result == "[]"

    def test_json_validate_empty_dict(self) -> None:
        """Test validating empty dict."""
        text = "{}"
        result = json_parser.validate_dict(text, key_type=None, value_type=None, length=0)
        assert result == {}

    def test_json_validate_empty_list(self) -> None:
        """Test validating empty list."""
        text = "[]"
        result = json_parser.validate_list(text, elements_type=None, length=0)
        assert result == []

    def test_code_capture_empty_block(self) -> None:
        """Test capturing empty code block."""
        text = "```python\n\n```"
        result = python_parser.capture(text)
        assert result == ""

    def test_generic_capture_empty_block(self) -> None:
        """Test capturing empty generic block."""
        text = "--- Start of Empty ---\n\n--- End of Empty ---"
        result = generic_parser.capture(text)
        assert result == ""

    def test_content_capture_empty_block(self) -> None:
        """Test capturing empty content block."""
        parser = ContentBlockParser.with_delimiters("|", "|")
        text = "||"
        result = parser.capture(text)
        assert result == ""

    def test_special_characters_in_json(self) -> None:
        """Test JSON with special characters."""
        text = '{"emoji": "🎉", "unicode": "\\u2028"}'
        result = json_parser.convert(text)
        assert result["emoji"] == "🎉"

    def test_code_block_with_emoji(self) -> None:
        """Test code block containing emoji."""
        text = "```python\nmessage = 'Hello 👋'\n```"
        result = python_parser.capture(text)
        assert "Hello 👋" in result

    def test_whitespace_handling(self) -> None:
        """Test handling of extra whitespace."""
        text = '```json\n  {"key": "value"}  \n```'
        result = json_parser.capture(text)
        assert '"key"' in result
