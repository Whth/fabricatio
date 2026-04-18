"""Test module for show_diff function from fabricatio-diff Rust bindings.

This module contains pytest test cases verifying the correctness of unified
diff generation between two strings.
"""

import pytest
from fabricatio_diff.rust import show_diff


class TestShowDiffFunction:
    """Test suite for the show_diff() function."""

    def test_identical_strings(self) -> None:
        """Test diff of identical strings shows no changes."""
        result = show_diff("hello", "hello")
        assert "-hello" not in result
        assert "+hello" not in result
        assert " hello" in result

    def test_single_line_change(self) -> None:
        """Test diff with a single line change."""
        result = show_diff("hello", "hallo")
        assert "-hello" in result
        assert "+hallo" in result

    def test_single_line_addition(self) -> None:
        """Test diff with a line added."""
        result = show_diff("hello", "hello\nworld")
        # Original line kept, new line added
        assert "-hello" in result
        assert "+world" in result

    def test_single_line_deletion(self) -> None:
        """Test diff with a line removed."""
        result = show_diff("hello\nworld", "hello")
        assert "-world" in result
        # "hello" appears as deleted and added
        assert "-hello" in result

    def test_multiline_identical(self) -> None:
        """Test diff of identical multiline strings."""
        text = "line1\nline2\nline3"
        result = show_diff(text, text)
        assert result.count(" ") == 3  # All lines unchanged

    def test_multiline_changes(self) -> None:
        """Test diff with multiple line changes."""
        a = "a\nb\nc"
        b = "a\nB\nc"
        result = show_diff(a, b)
        assert "-b" in result
        assert "+B" in result

    def test_empty_original(self) -> None:
        """Test diff when original is empty (all additions)."""
        result = show_diff("", "hello\nworld")
        assert "+hello" in result
        assert "+world" in result

    def test_empty_modified(self) -> None:
        """Test diff when modified is empty (all deletions)."""
        result = show_diff("hello\nworld", "")
        assert "-hello" in result
        assert "-world" in result

    def test_both_empty(self) -> None:
        """Test diff when both strings are empty."""
        result = show_diff("", "")
        assert result == ""

    def test_line_order_change(self) -> None:
        """Test diff when lines are reordered."""
        a = "1\n2\n3"
        b = "3\n2\n1"
        result = show_diff(a, b)
        assert "-1" in result
        assert "+3" in result

    def test_preserves_newlines(self) -> None:
        """Test that newlines are preserved in diff output."""
        a = "line1\nline2"
        b = "line1\nline2\n"
        result = show_diff(a, b)
        assert " " in result or "+" in result

    def test_whitespace_difference(self) -> None:
        """Test that whitespace differences are captured in diff."""
        a = "hello"
        b = "hello "
        result = show_diff(a, b)
        # Trailing space difference should show as change
        assert "-hello" in result or "+hello " in result

    def test_mixed_changes(self) -> None:
        """Test diff with multiple mixed changes."""
        a = "start\nmiddle\nend"
        b = "START\nmiddle\nEND"
        result = show_diff(a, b)
        assert "-start" in result
        assert "+START" in result
        assert " middle" in result
        assert "-end" in result
        assert "+END" in result
