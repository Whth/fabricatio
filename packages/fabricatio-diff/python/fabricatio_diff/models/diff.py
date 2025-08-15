"""Diff module providing a dataclass for managing text diffs."""

from fabricatio_core.models.generic import Display

from fabricatio_diff.rust import match_lines, show_diff
from fabricatio_diff.utils import Delimiters


class Diff(Display):
    """A dataclass representing a text diff operation."""

    search: str
    """The text pattern to search for."""
    replace: str
    """The text to replace the matched pattern with."""

    def apply(self, text: str, match_precision: float = 1.0) -> str | None:
        """Applies the diff operation to the given text.

        Args:
            text (str): The original text to apply the diff on.
            match_precision (float): The precision threshold for matching lines (default is 1.0).

        Returns:
            str | None: The modified text if a match is found and replaced; otherwise None.
        """
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
        return Diff(search=self.replace, replace=self.search)

    def display(self) -> str:
        """Returns a string representation of the Diff object.

        Returns:
            str: A string representation of the Diff object.
        """
        return (
            f"{Delimiters.SEARCH_LEFT}{self.search}{Delimiters.SEARCH_RIGHT}\n"
            f"{Delimiters.REPLACE_LEFT}{self.replace}{Delimiters.REPLACE_RIGHT}"
        )
