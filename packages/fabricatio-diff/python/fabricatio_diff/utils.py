"""Utils module for fabricatio_diff."""

from enum import StrEnum

from fabricatio_core.rust import ContentBlockParser


class Delimiters(StrEnum):
    """Enum class representing delimiters used for search and replace operations."""

    SEARCH_LEFT = "<<<<SEARCH"
    """Left delimiter for search blocks."""
    SEARCH_RIGHT = "SEARCH<<<<"
    """Right delimiter for search blocks."""
    REPLACE_LEFT = "<<<<REPLACE"
    """Left delimiter for replace blocks."""
    REPLACE_RIGHT = "REPLACE<<<<"
    """Right delimiter for replace blocks."""


SearchCapture = ContentBlockParser.with_delimiters(Delimiters.SEARCH_LEFT, Delimiters.SEARCH_RIGHT)
"""Capture instance for search blocks."""
ReplaceCapture = ContentBlockParser.with_delimiters(Delimiters.REPLACE_LEFT, Delimiters.REPLACE_RIGHT)
"""Capture instance for replace blocks."""
