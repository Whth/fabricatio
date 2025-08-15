"""Utils module for fabricatio_diff."""

from enum import StrEnum

from fabricatio_core.parser import Capture


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
