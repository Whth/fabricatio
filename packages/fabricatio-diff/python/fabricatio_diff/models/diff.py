"""Diff module providing a dataclass for managing text diffs."""

from fabricatio_core.models.generic import Display

from fabricatio_diff.rust import (
    apply_replace_lines,
    format_hashes,
    match_lines,
    show_diff,
)
from fabricatio_diff.utils import Delimiters


class Diff(Display):
    """A dataclass representing a text diff operation."""

    search: str
    """The text pattern to search for."""
    replace: str
    """The text to replace the matched pattern with."""
    start_anchor: str | None = None
    """Hashline anchor for the range start (LINE:HASH format)."""
    end_anchor: str | None = None
    """Hashline anchor for the range end (LINE:HASH format)."""
    start_line: int | None = None
    """1-indexed line number for range start."""
    end_line: int | None = None
    """1-indexed line number for range end."""

    def apply(self, text: str, match_precision: float = 1.0) -> str | None:
        """Applies the diff operation to the given text.

        Supports three modes:
        1. Anchor-based: Uses start_anchor and end_anchor to define a line range
        2. Line-number-based: Uses start_line and end_line to define a line range
        3. Pattern matching: Uses search/replace for fuzzy line matching

        Args:
            text (str): The original text to apply the diff on.
            match_precision (float): The precision threshold for matching lines (default is 1.0).

        Returns:
            str | None: The modified text if a match is found and replaced; otherwise None.
        """
        # Mode 1: Anchor-based line range
        if self.start_anchor and self.end_anchor:
            return apply_replace_lines(text, self.start_anchor, self.end_anchor, self.replace)

        # Mode 2: Line-number-based line range
        if self.start_line is not None and self.end_line is not None:
            formatted = format_hashes(text)
            lines = formatted.split("\n")
            num_lines = len(lines)
            # Validate bounds: 1-indexed, start <= end, within range
            if not (
                1 <= self.start_line <= num_lines
                and 1 <= self.end_line <= num_lines
                and self.start_line <= self.end_line
            ):
                return None
            # Extract anchors at start_line-1 and end_line-1 indices (0-indexed)
            start_anchor = lines[self.start_line - 1].split("|")[0]
            end_anchor = lines[self.end_line - 1].split("|")[0]
            return apply_replace_lines(text, start_anchor, end_anchor, self.replace)

        # Mode 3: Existing pattern matching (search/replace)
        match: str | None = match_lines(text, self.search, match_precision)
        if match:
            return text.replace(match, self.replace)
        return None

    @property
    def diff(self) -> str:
        """Returns the diff between the search and replace patterns."""
        return show_diff(self.search, self.replace)

    def reverse(self) -> "Diff":
        """Reverses the diff operation.

        Returns:
            Diff: A new Diff object with the reversed search and replace patterns.
        """
        return Diff(
            search=self.replace,
            replace=self.search,
            start_anchor=self.end_anchor,
            end_anchor=self.start_anchor,
            start_line=self.end_line,
            end_line=self.start_line,
        )

    @classmethod
    def from_anchors(cls, start_anchor: str, end_anchor: str, replace: str) -> "Diff":
        """Create a line-range Diff from hashline anchors (LINE:HASH format).

        Args:
            start_anchor (str): The hashline anchor for range start (e.g., "42:ab123def").
            end_anchor (str): The hashline anchor for range end (e.g., "45:cd456789").
            replace (str): The replacement text for the lines range.

        Returns:
            Diff: A new Diff object configured for anchor-based line replacement.
        """
        return cls(search="", replace=replace, start_anchor=start_anchor, end_anchor=end_anchor)

    @classmethod
    def from_line_range(cls, start: int, end: int, replace: str) -> "Diff":
        """Create a line-range Diff from line numbers (1-indexed inclusive).

        Args:
            start (int): The 1-indexed line number for range start.
            end (int): The 1-indexed line number for range end.
            replace (str): The replacement text for the lines range.

        Returns:
            Diff: A new Diff object configured for line-number-based line replacement.
        """
        return cls(search="", replace=replace, start_line=start, end_line=end)

    def format_with_hashes(self, content: str) -> str:
        """Formats content with LINE:HASH anchors for LLM context.

        Args:
            content (str): The text content to format.

        Returns:
            str: A string where each line is prefixed with its line number and hash.
        """
        return format_hashes(content)

    def display(self) -> str:
        """Returns a string representation of the Diff object.

        Returns:
            str: A string representation of the Diff object.
        """
        return (
            f"{Delimiters.SEARCH_LEFT}\n{self.search}\n{Delimiters.SEARCH_RIGHT}\n"
            f"{Delimiters.REPLACE_LEFT}\n{self.replace}\n{Delimiters.REPLACE_RIGHT}"
        )
