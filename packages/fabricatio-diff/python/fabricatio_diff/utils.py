"""Utils module for fabricatio_diff."""

import re
from enum import StrEnum

from fabricatio_core.rust import ContentBlockParser, TextCapturer


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


class HashLineType(StrEnum):
    """The vocabulary of fenced block kinds used in hashline LLM responses.

    Each member corresponds to one op kind the LLM can emit. Delimiter strings
    in `HashlineDelimiters` are derived from the member names via
    `f"<<<<{HashLineType.X}"` and `f"{HashLineType.X}<<<<"`, so renaming a
    member here automatically updates every delimiter and capture.
    """

    SET = "SET"
    """Single-line replace (`set_line`)."""
    RANGE = "RANGE"
    """Multi-line replace (`replace_lines`)."""
    INSERT_AFTER = "INSERT_AFTER"
    """Insert text after an anchored line (`insert_after`)."""
    REPLACE = "REPLACE"
    """Fuzzy text substitution (`replace`)."""


class HashlineDelimiters(StrEnum):
    """Block delimiters for hashline LLM responses.

    Each pair wraps one op of the corresponding kind. All values are derived
    from `HashLineType` so the protocol vocabulary lives in one place.
    """

    SET_LEFT = f"<<<<{HashLineType.SET}"
    """Left delimiter for a set_line op block."""
    SET_RIGHT = f"{HashLineType.SET}<<<<"
    """Right delimiter for a set_line op block."""

    RANGE_LEFT = f"<<<<{HashLineType.RANGE}"
    """Left delimiter for a replace_lines op block."""
    RANGE_RIGHT = f"{HashLineType.RANGE}<<<<"
    """Right delimiter for a replace_lines op block."""

    INSERT_LEFT = f"<<<<{HashLineType.INSERT_AFTER}"
    """Left delimiter for an insert_after op block."""
    INSERT_RIGHT = f"{HashLineType.INSERT_AFTER}<<<<"
    """Right delimiter for an insert_after op block."""

    REPLACE_LEFT = f"<<<<{HashLineType.REPLACE}"
    """Left delimiter for a fuzzy replace op block."""
    REPLACE_RIGHT = f"{HashLineType.REPLACE}<<<<"
    """Right delimiter for a fuzzy replace op block."""


def _build_hashline_capture(left: str, right: str) -> TextCapturer:
    r"""Build a `TextCapturer` for a hashline delimiter pair.

    Uses a custom regex `LEFT([^\n]*)\n(.*?)\nRIGHT` that:
      1. Tolerates an inline header on the same line as the opener
         (e.g. `<<<<SET 2:b2`) — captured as group 1.
      2. Captures the body between the first newline and the closer — group 2.
    The `ContentBlockParser.with_delimiters` regex `LEFT\n(.*?)\nRIGHT` would
    require the opener to be on its own line, which the LLM does not emit.
    The `(?smi)` flags are prepended automatically by `TextCapturer`.
    """
    pattern = f"{re.escape(left)}([^\\n]*)\\n(.*?)\\n{re.escape(right)}"
    return TextCapturer.with_pattern(pattern)


SearchCapture = ContentBlockParser.with_delimiters(Delimiters.SEARCH_LEFT, Delimiters.SEARCH_RIGHT)
"""Capture instance for search blocks."""
ReplaceCapture = ContentBlockParser.with_delimiters(Delimiters.REPLACE_LEFT, Delimiters.REPLACE_RIGHT)
"""Capture instance for replace blocks."""
HashlineSetCapture = _build_hashline_capture(HashlineDelimiters.SET_LEFT, HashlineDelimiters.SET_RIGHT)
"""Capture instance for `set_line` blocks within a hashline-diff response."""
HashlineRangeCapture = _build_hashline_capture(HashlineDelimiters.RANGE_LEFT, HashlineDelimiters.RANGE_RIGHT)
"""Capture instance for `replace_lines` blocks within a hashline-diff response."""
HashlineInsertAfterCapture = _build_hashline_capture(HashlineDelimiters.INSERT_LEFT, HashlineDelimiters.INSERT_RIGHT)
"""Capture instance for `insert_after` blocks within a hashline-diff response."""
HashlineReplaceCapture = _build_hashline_capture(HashlineDelimiters.REPLACE_LEFT, HashlineDelimiters.REPLACE_RIGHT)
"""Capture instance for `replace` blocks within a hashline-diff response."""


__all__ = [
    "Delimiters",
    "HashLineType",
    "HashlineDelimiters",
    "HashlineInsertAfterCapture",
    "HashlineRangeCapture",
    "HashlineReplaceCapture",
    "HashlineSetCapture",
    "ReplaceCapture",
    "SearchCapture",
]
