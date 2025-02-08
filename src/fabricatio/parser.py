from typing import Any, Self, Tuple

from pydantic import Field, PrivateAttr
from regex import Pattern, compile

from fabricatio.models.generic import Base


class Capture(Base):
    """
    A class to capture patterns in text using regular expressions.

    Attributes:
        pattern (str): The regular expression pattern to search for.
        _compiled (Pattern): The compiled regular expression pattern.
    """

    target_groups: Tuple[int, ...] = Field(default_factory=tuple)
    """The target groups to capture from the pattern."""
    pattern: str = Field(frozen=True)
    """The regular expression pattern to search for."""
    _compiled: Pattern = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """
        Initialize the compiled regular expression pattern after the model is initialized.

        Args:
            __context (Any): The context in which the model is initialized.
        """
        self._compiled = compile(self.pattern)

    def capture(self, text: str) -> Tuple[str, ...] | None:
        """
        Capture the first occurrence of the pattern in the given text.

        Args:
            text (str): The text to search the pattern in.

        Returns:
            str | None: The captured text if the pattern is found, otherwise None.

        """
        match = self._compiled.search(text)
        if match is None:
            return None

        if self.target_groups:
            return tuple(match.group(g) for g in self.target_groups)
        else:
            return (match.group(),)

    @classmethod
    def capture_code_block(cls, language: str) -> Self:
        """
        Capture the first occurrence of a code block in the given text.
        Args:
            language (str): The text containing the code block.

        Returns:
            Self: The instance of the class with the captured code block.
        """
        return cls(pattern=f"```{language}\n(.*?)\n```", target_groups=(1,))


JsonCapture = Capture.capture_code_block("json")
PythonCapture = Capture.capture_code_block("python")
