from typing import Any

from pydantic import PrivateAttr
from regex import Pattern, compile

from fabricatio.models.generic import Base


class Capture(Base):
    """
    A class to capture patterns in text using regular expressions.

    Attributes:
        pattern (str): The regular expression pattern to search for.
        _compiled (Pattern): The compiled regular expression pattern.
    """

    pattern: str
    _compiled: Pattern = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """
        Initialize the compiled regular expression pattern after the model is initialized.

        Args:
            __context (Any): The context in which the model is initialized.
        """
        self._compiled = compile(self.pattern)

    def capture(self, text: str) -> str | None:
        """
        Capture the first occurrence of the pattern in the given text.

        Args:
            text (str): The text to search the pattern in.

        Returns:
            str | None: The captured text if the pattern is found, otherwise None.

        Examples:
            >>> Capture(pattern=r"(\d+)").capture("123")
            "123"
            >>> Capture(pattern=r"(\d+)").capture("abc")
            None
        """
        if match := self._compiled.search(text):
            return match.group()
