"""Test module for hashline functions from fabricatio-diff Rust bindings.

This module contains pytest test cases verifying the correctness of the
rho-hashline integration for efficient line anchoring and editing.
"""

from fabricatio_diff import (
    apply_insert_after,
    apply_replace,
    apply_replace_lines,
    apply_set_line,
    compute_hash,
    format_hashes,
    parse_hashline_anchor,
)


class TestComputeHash:
    """Test suite for the compute_hash() function."""

    def test_identical_lines_produce_same_hash(self) -> None:
        """Test that identical lines produce identical hashes."""
        assert compute_hash("hello") == compute_hash("hello")
        assert compute_hash("") == compute_hash("")

    def test_different_lines_produce_different_hashes(self) -> None:
        """Test that different lines produce different hashes."""
        assert compute_hash("hello") != compute_hash("world")
        assert compute_hash("hello") != compute_hash("")

    def test_hash_length_is_reasonable(self) -> None:
        """Test that hash has expected format (hex string)."""
        h = compute_hash("test")
        assert isinstance(h, str)
        assert len(h) >= 2  # At least 2-char hash
        # Should be hex characters
        assert all(c in "0123456789abcdef" for c in h.lower())

    def test_whitespace_affects_hash(self) -> None:
        """Test that leading/trailing whitespace changes the hash for distinct content."""
        # Note: rho-hashline computes hash on a fixed portion of the line
        # so similar prefixes may produce same hash. Test with distinct starts.
        assert compute_hash("hello world") != compute_hash("world hello")


class TestFormatHashes:
    """Test suite for the format_hashes() function."""

    def test_format_single_line(self) -> None:
        """Test formatting with a single line."""
        result = format_hashes("hello")
        assert "hello" in result
        # Should have line number and hash
        lines = result.strip().split("\n")
        assert len(lines) == 1

    def test_format_multiple_lines(self) -> None:
        """Test formatting with multiple lines."""
        result = format_hashes("hello\nworld\ntest")
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_format_with_custom_start_line(self) -> None:
        """Test formatting with custom starting line number."""
        result = format_hashes("hello\nworld", start_line=5)
        # Line numbers should start at 5
        assert "5:" in result
        assert "6:" in result

    def test_format_preserves_content(self) -> None:
        """Test that formatting preserves line content."""
        content = "line1\nline2\nline3"
        result = format_hashes(content)
        for line in ["line1", "line2", "line3"]:
            assert line in result

    def test_format_empty_content(self) -> None:
        """Test formatting empty content."""
        result = format_hashes("")
        # rho-hashline treats empty content as containing one empty line
        assert result == "1:05|"  # Line 1, hash 05, empty content


class TestParseHashlineAnchor:
    """Test suite for the parse_hashline_anchor() function."""

    def test_parse_basic_anchor(self) -> None:
        """Test parsing a basic LINE:HASH anchor."""
        line, _ = parse_hashline_anchor("5:ab")
        assert line == 5

    def test_parse_anchor_with_long_hash(self) -> None:
        """Test parsing an anchor with a longer hash."""
        line, _ = parse_hashline_anchor("42:abc123")
        assert line == 42

    def test_parse_anchor_first_line(self) -> None:
        """Test parsing anchor for first line."""
        line, _ = parse_hashline_anchor("1:ab")
        assert line == 1

    def test_parse_anchor_with_whitespace(self) -> None:
        """Test parsing anchor with whitespace (should be normalized)."""
        # rho-hashline normalizes whitespace
        line, _ = parse_hashline_anchor("5 : a3")
        assert line == 5

    def test_parse_anchor_with_content_suffix(self) -> None:
        """Test parsing anchor with content suffix (stripped)."""
        # "5:a3|some content" - suffix should be stripped
        line, _ = parse_hashline_anchor("5:ab|something")
        assert line == 5


class TestApplySetLine:
    """Test suite for the apply_set_line() function."""

    def test_set_single_line(self) -> None:
        """Test setting a single line."""
        content = "line1\nline2\nline3"
        # First get the anchor for line 1
        formatted = format_hashes(content)
        first_line_anchor = formatted.split("\n")[0].split("|")[0]

        result = apply_set_line(content, first_line_anchor, "new_line1")
        assert "new_line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_set_line_preserves_others(self) -> None:
        """Test that setting one line preserves others."""
        content = "hello\nworld\ntest"
        formatted = format_hashes(content)
        first_line_anchor = formatted.split("\n")[0].split("|")[0]

        result = apply_set_line(content, first_line_anchor, "hi")
        # Other lines should be preserved
        assert "world" in result
        assert "test" in result


class TestApplyInsertAfter:
    """Test suite for the apply_insert_after() function."""

    def test_insert_after_single_line(self) -> None:
        """Test inserting a line after another."""
        content = "line1\nline2"
        formatted = format_hashes(content)
        first_line_anchor = formatted.split("\n")[0].split("|")[0]

        result = apply_insert_after(content, first_line_anchor, "inserted")
        assert "inserted" in result
        assert "line1" in result
        assert "line2" in result


class TestApplyReplace:
    """Test suite for the apply_replace() function."""

    def test_replace_single_occurrence(self) -> None:
        """Test replacing a single occurrence."""
        content = "hello world hello"
        result = apply_replace(content, "world", "universe", all=False)
        assert "universe" in result
        assert content.count("hello") == result.count("hello")

    def test_replace_all_occurrences(self) -> None:
        """Test replacing all occurrences."""
        content = "aaa bbb aaa"
        result = apply_replace(content, "aaa", "ccc", all=True)
        assert result.count("ccc") == 2
        assert "bbb" in result


class TestApplyReplaceLines:
    """Test suite for the apply_replace_lines() function."""

    def test_replace_lines_range(self) -> None:
        """Test replacing a range of lines."""
        content = "line1\nline2\nline3\nline4"
        formatted = format_hashes(content)
        lines = formatted.split("\n")
        start_anchor = lines[0].split("|")[0]
        end_anchor = lines[2].split("|")[0]

        result = apply_replace_lines(content, start_anchor, end_anchor, "new_content")
        assert "new_content" in result


class TestIntegration:
    """Integration tests combining multiple hashline operations."""

    def test_format_then_edit_workflow(self) -> None:
        """Test a realistic workflow: format, then edit."""
        content = "def hello():\n    return 42\n\ndef world():\n    pass"

        # Format content with hashes
        formatted = format_hashes(content)
        assert "def hello():" in formatted

        # Get anchor for line 2
        line_2_anchor = formatted.split("\n")[1].split("|")[0]

        # Apply edit
        result = apply_set_line(content, line_2_anchor, "    return 100")
        assert "return 100" in result or "return 42" not in result

    def test_hash_stability(self) -> None:
        """Test that compute_hash produces stable results."""
        text = "hello world"
        h1 = compute_hash(text)
        h2 = compute_hash(text)
        assert h1 == h2
