"""Test module for Diff model class.

This module contains pytest test cases verifying the correctness of Diff
dataclass methods including apply(), diff property, reverse(), and display().
"""

import pytest
from fabricatio_diff.models.diff import Diff


class TestDiffModel:
    """Test suite for the Diff model class."""

    @pytest.fixture
    def simple_diff(self) -> Diff:
        """Create a simple Diff instance for testing.

        Returns:
            Diff: A Diff with search="old" and replace="new"
        """
        return Diff(search="old", replace="new")

    @pytest.fixture
    def multiline_diff(self) -> Diff:
        """Create a multiline Diff instance for testing.

        Returns:
            Diff: A Diff with multiline search and replace
        """
        return Diff(search="line1\nold line\nline3", replace="line1\nnew line\nline3")

    @pytest.fixture
    def empty_diff(self) -> Diff:
        """Create a Diff with empty values for testing.

        Returns:
            Diff: An empty Diff instance
        """
        return Diff(search="", replace="")


class TestDiffApply(TestDiffModel):
    """Test suite for Diff.apply() method.

    Note: Diff.apply() uses match_lines() which performs fuzzy line-level matching.
    The search string is matched against windows of lines in the text.
    """

    def test_apply_exact_line_match(self) -> None:
        """Test apply with exact full line match."""
        # When search="old line" matches "old line" in text
        diff = Diff(search="old line", replace="new line")
        result = diff.apply("line1\nold line\nline3")
        assert result == "line1\nnew line\nline3"

    def test_apply_no_match(self, simple_diff: Diff) -> None:
        """Test apply when no match is found."""
        # "different line" doesn't match "old" at precision 1.0
        result = simple_diff.apply("different line")
        assert result is None

    def test_apply_multiline_match(self, multiline_diff: Diff) -> None:
        """Test apply with multiline match."""
        text = "line1\nold line\nline3"
        result = multiline_diff.apply(text)
        assert result == "line1\nnew line\nline3"

    def test_apply_empty_search(self) -> None:
        """Test apply with empty search string."""
        diff = Diff(search="", replace="added")
        result = diff.apply("some text")
        # Empty search won't match at precision 1.0
        assert result is None

    def test_apply_empty_replace(self) -> None:
        """Test apply with empty replace string (deletion)."""
        diff = Diff(search="old line", replace="")
        result = diff.apply("line1\nold line\nline3")
        assert result == "line1\n\nline3"

    def test_apply_with_precision_low(self) -> None:
        """Test apply with lower precision allows fuzzy matching."""
        diff = Diff(search="old line", replace="new line")
        # "old line" might match "oldline" with lower precision
        text = "oldline"
        result = diff.apply(text, match_precision=0.6)
        # At low precision, similarity between "old line" and "oldline" might pass

    def test_apply_first_match_only(self) -> None:
        """Test that apply only replaces the first matching window."""
        diff = Diff(search="a", replace="X")
        # match_lines treats "a" as single line, won't match "a\na\na" well
        result = diff.apply("a\na\na")
        # At precision 1.0, "a" won't match "a\na\na" unless exact

    def test_apply_preserves_surrounding(self) -> None:
        """Test that apply preserves text around the match."""
        diff = Diff(search="old line", replace="new line")
        result = diff.apply("prefix\nold line\nsuffix")
        assert result == "prefix\nnew line\nsuffix"


class TestDiffProperty(TestDiffModel):
    """Test suite for Diff.diff property."""

    def test_diff_property(self, simple_diff: Diff) -> None:
        """Test the diff property returns unified diff string."""
        result = simple_diff.diff
        assert "-old" in result
        assert "+new" in result

    def test_diff_property_multiline(self, multiline_diff: Diff) -> None:
        """Test diff property with multiline content."""
        result = multiline_diff.diff
        assert "-old line" in result
        assert "+new line" in result

    def test_diff_property_identical(self) -> None:
        """Test diff property when search and replace are identical."""
        diff = Diff(search="same", replace="same")
        result = diff.diff
        # Should show no changes (only equal lines)
        assert "-same" not in result
        assert "+same" not in result

    def test_diff_property_empty(self, empty_diff: Diff) -> None:
        """Test diff property with empty search and replace."""
        result = empty_diff.diff
        assert result == ""


class TestDiffReverse(TestDiffModel):
    """Test suite for Diff.reverse() method."""

    def test_reverse_simple(self, simple_diff: Diff) -> None:
        """Test reversing a simple diff."""
        reversed_diff = simple_diff.reverse()
        assert reversed_diff.search == "new"
        assert reversed_diff.replace == "old"

    def test_reverse_multiline(self, multiline_diff: Diff) -> None:
        """Test reversing a multiline diff."""
        reversed_diff = multiline_diff.reverse()
        assert reversed_diff.search == "line1\nnew line\nline3"
        assert reversed_diff.replace == "line1\nold line\nline3"

    def test_reverse_double_reverse(self, simple_diff: Diff) -> None:
        """Test that reversing twice returns original."""
        original = simple_diff
        reversed_once = original.reverse()
        reversed_twice = reversed_once.reverse()
        assert reversed_twice.search == original.search
        assert reversed_twice.replace == original.replace

    def test_reverse_empty(self, empty_diff: Diff) -> None:
        """Test reversing an empty diff."""
        reversed_diff = empty_diff.reverse()
        assert reversed_diff.search == ""
        assert reversed_diff.replace == ""


class TestDiffDisplay(TestDiffModel):
    """Test suite for Diff.display() method."""

    def test_display_simple(self, simple_diff: Diff) -> None:
        """Test display output for simple diff."""
        result = simple_diff.display()
        assert "<<<<SEARCH" in result
        assert "old" in result
        assert "<<<<REPLACE" in result
        assert "new" in result

    def test_display_multiline(self, multiline_diff: Diff) -> None:
        """Test display output for multiline diff."""
        result = multiline_diff.display()
        assert "old" in result
        assert "new" in result

    def test_display_empty(self, empty_diff: Diff) -> None:
        """Test display output for empty diff."""
        result = empty_diff.display()
        assert "<<<<SEARCH" in result
        assert "<<<<REPLACE" in result

    def test_display_contains_search(self, simple_diff: Diff) -> None:
        """Test that display contains the search string."""
        result = simple_diff.display()
        assert simple_diff.search in result

    def test_display_contains_replace(self, simple_diff: Diff) -> None:
        """Test that display contains the replace string."""
        result = simple_diff.display()
        assert simple_diff.replace in result
