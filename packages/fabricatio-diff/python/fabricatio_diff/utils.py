"""Utils module for fabricatio_diff."""

from enum import StrEnum

from fabricatio_core.parser import Capture
from Levenshtein.StringMatcher import ratio
from more_itertools import windowed


def match_lines(haystack: str, needle: str, match_precision: float = 1.0) -> str | None:
    """Matches lines in `haystack` with the content of `needle` using approximate string matching.

    This function searches for a sequence of lines in `haystack` that closely matches the lines
    in `needle` based on the provided precision threshold.

    Args:
        haystack (str): The full text to search within.
        needle (str): The text to find within the haystack.
        match_precision (float, optional): Threshold for similarity score (0.0 to 1.0).
                                           A value of 1.0 means an exact match is required.
                                           Defaults to 1.0.

    Returns:
        str | None: The matched block of lines as a single string if a match is found,
                    otherwise None.
    """
    haystack_lines = haystack.splitlines()
    needle_lines = needle.splitlines()
    windows = windowed(haystack_lines, len(needle_lines))

    joined_windows = ("\n".join(window) for window in windows)

    return next(
        (window for window in joined_windows if ratio(needle, window, score_cutoff=match_precision)),
        None,
    )


class Delimiters(StrEnum):
    """Enum class representing delimiters used for search and replace operations."""

    SEARCH_LEFT = "<<<<SEARCH\n"
    """Left delimiter for search blocks."""
    SEARCH_RIGHT = "\nSEARCH<<<<"
    """Right delimiter for search blocks."""
    REPLACE_LEFT = "<<<<REPLACE\n"
    """Left delimiter for replace blocks."""
    REPLACE_RIGHT = "\nREPLACE<<<<"
    """Right delimiter for replace blocks."""


SearchCapture = Capture.capture_content(Delimiters.SEARCH_LEFT, Delimiters.SEARCH_RIGHT)
"""Capture instance for search blocks."""
ReplaceCapture = Capture.capture_content(Delimiters.REPLACE_LEFT, Delimiters.REPLACE_RIGHT)
"""Capture instance for replace blocks."""
