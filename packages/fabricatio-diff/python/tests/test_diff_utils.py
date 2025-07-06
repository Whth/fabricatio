"""Test module for match_lines function."""

from typing import Optional

import pytest
from fabricatio_diff.utils import match_lines

test_cases = [
    # Exact match cases
    ("line1\nline2\nline3", "line2\nline3", 1.0, "line2\nline3"),
    # No match case
    ("line1\nline2\nline3", "line4\nline5", 1.0, None),
    # Partial match with lower precision
    ("hello world\nthis is a test", "helo world\nthis was a test", 0.8, "hello world\nthis is a test"),
    # Empty haystack
    ("", "line1", 1.0, None),
    # Empty needle
    ("line1\nline2", "", 1.0, ""),
    # Single line match
    ("exact match line", "exact match line", 1.0, "exact match line"),
]


@pytest.mark.parametrize(
    ("haystack", "needle", "match_precision", "expected"),
    test_cases,
    ids=[
        "exact_match",
        "no_match",
        "partial_match_with_tolerance",
        "empty_haystack",
        "empty_needle",
        "single_line_match",
    ],
)
def test_match_lines(haystack: str, needle: str, match_precision: float, expected: Optional[str]) -> None:
    """Test the match_lines function with various input scenarios.

    Args:
        haystack: The string to search within.
        needle: The string to search for.
        match_precision: The similarity threshold for matching lines.
        expected: The expected result from the match_lines function.
    """
    result = match_lines(haystack, needle, match_precision)
    assert result == expected
