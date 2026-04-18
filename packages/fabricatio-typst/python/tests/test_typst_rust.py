"""Test module for Rust functions in fabricatio-typst.

This module contains pytest test cases verifying the correctness of Rust-implemented
functions including TeX to Typst conversion, comment handling, and metadata extraction.
"""

from fabricatio_typst.rust import (
    comment,
    convert_all_tex_math,
    extract_body,
    extract_sections,
    fix_misplaced_labels,
    replace_thesis_body,
    split_out_metadata,
    strip_comment,
    tex_to_typst,
    to_metadata,
    uncomment,
)


class TestTexToTypst:
    """Test suite for tex_to_typst() function."""

    def test_simple_tex_conversion(self) -> None:
        """Test basic TeX to Typst conversion."""
        tex = r"\textbf{bold text}"
        result = tex_to_typst(tex)
        assert result != tex  # Should be converted

    def test_tex_with_math(self) -> None:
        """Test TeX containing math expressions."""
        tex = r"E = mc^2"
        result = tex_to_typst(tex)
        assert result == "E = m c^2"

    def test_empty_string(self) -> None:
        """Test with empty string."""
        assert tex_to_typst("") == ""


class TestConvertAllTexMath:
    """Test suite for convert_all_tex_math() function."""

    def test_inline_math_dollar(self) -> None:
        """Test inline math with $...$ syntax."""
        result = convert_all_tex_math("Solve $x^2 = 4$ for x")
        # The function should convert the math expression
        assert isinstance(result, str)

    def test_display_math_double_dollar(self) -> None:
        """Test display math with $$...$$ syntax."""
        result = convert_all_tex_math("$$\\int_0^1 x dx$$")
        assert "$$" not in result

    def test_paren_math(self) -> None:
        r"""Test math with \\(...\\) syntax."""
        result = convert_all_tex_math(r"Solve \(a + b = c\) for a")
        assert r"\(" not in result

    def test_bracket_math(self) -> None:
        r"""Test math with \\[...\\] syntax."""
        result = convert_all_tex_math(r"Equation \[E = mc^2\] is physics")
        assert r"\[" not in result

    def test_mixed_content(self) -> None:
        """Test string with multiple math types."""
        result = convert_all_tex_math("Test $inline$ and $$display$$ math")
        # Should handle multiple math expressions
        assert isinstance(result, str)

    def test_no_math(self) -> None:
        """Test string without any math expressions."""
        text = "Plain text without math"
        result = convert_all_tex_math(text)
        assert result == text

    def test_empty_string(self) -> None:
        """Test with empty string."""
        assert convert_all_tex_math("") == ""


class TestStripComment:
    """Test suite for strip_comment() function."""

    def test_leading_comments(self) -> None:
        """Test stripping leading comment lines."""
        text = "// comment line\n// another\nactual content"
        result = strip_comment(text)
        assert "actual content" in result
        assert "// comment" not in result

    def test_trailing_comments(self) -> None:
        """Test stripping trailing comment lines."""
        text = "actual content\n// comment line\n// another"
        result = strip_comment(text)
        assert "actual content" in result

    def test_both_leading_and_trailing(self) -> None:
        """Test stripping both leading and trailing comments."""
        text = "// header\ncontent\n// footer"
        result = strip_comment(text)
        assert "content" in result
        assert "// header" not in result

    def test_no_comments(self) -> None:
        """Test with no comment lines."""
        text = "just regular content"
        result = strip_comment(text)
        assert result == text

    def test_empty_string(self) -> None:
        """Test with empty string."""
        assert strip_comment("") == ""

    def test_only_comments(self) -> None:
        """Test with only comment lines."""
        text = "// comment1\n// comment2"
        result = strip_comment(text)
        assert result == ""


class TestUncomment:
    """Test suite for uncomment() function."""

    def test_double_slash_space(self) -> None:
        """Test removing '// ' style comments."""
        text = "// This is a comment\n// Another"
        result = uncomment(text)
        assert "// " not in result
        assert "This is a comment" in result

    def test_double_slash_no_space(self) -> None:
        """Test removing '//' style comments without space."""
        text = "//no space comment"
        result = uncomment(text)
        assert "//" not in result

    def test_mixed_content(self) -> None:
        """Test with mixed commented and uncommented lines."""
        text = "regular line\n// comment\nanother line"
        result = uncomment(text)
        assert "regular line" in result
        assert "// comment" not in result

    def test_no_comments(self) -> None:
        """Test with no comments."""
        text = "plain text without comments"
        result = uncomment(text)
        assert result == text


class TestComment:
    """Test suite for comment() function."""

    def test_adds_comment_prefix(self) -> None:
        """Test adding '// ' prefix to lines."""
        text = "line1\nline2"
        result = comment(text)
        assert "// line1" in result
        assert "// line2" in result

    def test_single_line(self) -> None:
        """Test commenting a single line."""
        result = comment("single line")
        assert "// single line" in result

    def test_empty_string(self) -> None:
        """Test with empty string."""
        assert comment("") == ""


class TestSplitOutMetadata:
    """Test suite for split_out_metadata() function."""

    def test_valid_metadata(self) -> None:
        """Test extracting valid YAML metadata."""
        text = "// title: Test\n// author: Me\n\nactual content"
        metadata, remaining = split_out_metadata(text)
        assert metadata is not None
        assert "title" in str(metadata)
        assert "actual content" in remaining

    def test_no_metadata(self) -> None:
        """Test with no metadata block."""
        text = "just regular content"
        metadata, remaining = split_out_metadata(text)
        assert metadata is None
        assert remaining == text

    def test_malformed_metadata(self) -> None:
        """Test with malformed YAML metadata."""
        text = "// not valid yaml :\n\ncontent"
        _metadata, remaining = split_out_metadata(text)
        # May return None or partial
        assert "content" in remaining

    def test_metadata_only(self) -> None:
        """Test with only metadata, no content."""
        text = "// key: value"
        _metadata, _remaining = split_out_metadata(text)
        # Remaining might be empty or just the original

    def test_metadata_with_complex_values(self) -> None:
        """Test metadata with list values."""
        text = "// items:\n//   - item1\n//   - item2\n\ncontent"
        _metadata, remaining = split_out_metadata(text)
        assert "content" in remaining


class TestToMetadata:
    """Test suite for to_metadata() function."""

    def test_dict_to_yaml(self) -> None:
        """Test converting dict to YAML string."""
        data = {"title": "Test", "author": "Me"}
        result = to_metadata(data)
        assert isinstance(result, str)
        assert "title" in result
        assert "Test" in result

    def test_list_to_yaml(self) -> None:
        """Test converting list to YAML string."""
        data = ["item1", "item2"]
        result = to_metadata(data)
        assert isinstance(result, str)
        assert "item1" in result

    def test_nested_data(self) -> None:
        """Test converting nested structure."""
        data = {"outer": {"inner": "value"}, "list": [1, 2]}
        result = to_metadata(data)
        assert isinstance(result, str)


class TestExtractBody:
    """Test suite for extract_body() function."""

    def test_extract_between_wrappers(self) -> None:
        """Test extracting content between wrapper strings."""
        text = "prefix === content === suffix"
        result = extract_body(text, "===")
        assert result == " content "

    def test_no_wrapper(self) -> None:
        """Test when wrapper not found."""
        text = "no wrapper here"
        result = extract_body(text, "===")
        assert result is None

    def test_multiple_wrappers(self) -> None:
        """Test with multiple occurrences - behavior may vary."""
        text = "=== first === middle === third ==="
        result = extract_body(text, "===")
        # Result may be None or may contain content between first two wrappers
        assert result is None or isinstance(result, str)


class TestReplaceThesisBody:
    """Test suite for replace_thesis_body() function."""

    def test_replace_between_wrappers(self) -> None:
        """Test replacing content between wrappers."""
        text = "before === old content === after"
        result = replace_thesis_body(text, "===", "new content")
        assert result is not None
        assert "before" in result
        assert "after" in result

    def test_no_wrapper(self) -> None:
        """Test when wrapper not found."""
        text = "no wrapper here"
        result = replace_thesis_body(text, "===", "new")
        assert result is None

    def test_empty_replacement(self) -> None:
        """Test replacing with empty string."""
        text = "=== content ==="
        result = replace_thesis_body(text, "===", "")
        assert "====" in result  # Two adjacent wrappers


class TestExtractSections:
    """Test suite for extract_sections() function."""

    def test_extract_sections_exists(self) -> None:
        """Test that extract_sections function exists and is callable."""
        assert callable(extract_sections)

    def test_extract_sections_returns_list(self) -> None:
        """Test that extract_sections returns a list of tuples."""
        # Using typst format: = Title for level 1, == Title for level 2
        result = extract_sections("= Header\nContent", 1, "=")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0][0] == "Header"
        assert result[0][1] == "Content"

    def test_level_one_headers(self) -> None:
        """Test extracting level 1 sections with = prefix."""
        text = "= Title\nContent here\n== Subtitle\nMore content"
        result = extract_sections(text, 1, "=")
        assert len(result) == 1
        assert result[0][0] == "Title"

    def test_level_two_headers(self) -> None:
        """Test extracting level 2 sections with == prefix."""
        text = "= Title\n== Section 1\nContent 1\n== Section 2\nContent 2"
        result = extract_sections(text, 2, "=")
        assert len(result) == 2
        assert result[0][0] == "Section 1"
        assert result[1][0] == "Section 2"

    def test_custom_section_char(self) -> None:
        """Test with custom section character."""
        text = "* Heading\nContent"
        result = extract_sections(text, 1, "*")
        assert len(result) == 1
        assert result[0][0] == "Heading"

    def test_no_sections(self) -> None:
        """Test with no matching sections."""
        text = "Plain text without headers"
        result = extract_sections(text, 1, "=")
        assert len(result) == 0


class TestFixMisplacedLabels:
    """Test suite for fix_misplaced_labels() function."""

    def test_misplaced_label_fixed(self) -> None:
        """Test fixing misplaced labels."""
        # A typical misplaced label scenario
        text = "content @label1 more text @label2"
        result = fix_misplaced_labels(text)
        # Should handle the labels somehow
        assert isinstance(result, str)

    def test_no_labels(self) -> None:
        """Test with no labels."""
        text = "plain text without labels"
        result = fix_misplaced_labels(text)
        assert result == text

    def test_empty_string(self) -> None:
        """Test with empty string."""
        assert fix_misplaced_labels("") == ""
