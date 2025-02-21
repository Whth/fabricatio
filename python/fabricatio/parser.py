"""A module to parse text using regular expressions."""

from typing import Any, Callable, Self, Tuple

import regex
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, PrivateAttr
from regex import Pattern, compile

from fabricatio.journal import logger


class Capture(BaseModel):
    """A class to capture patterns in text using regular expressions.

    Attributes:
        pattern (str): The regular expression pattern to search for.
        _compiled (Pattern): The compiled regular expression pattern.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)
    target_groups: Tuple[int, ...] = Field(default_factory=tuple)
    """The target groups to capture from the pattern."""
    pattern: str = Field(frozen=True)
    """The regular expression pattern to search for."""
    flags: PositiveInt = Field(default=regex.DOTALL | regex.MULTILINE | regex.IGNORECASE, frozen=True)
    """The flags to use when compiling the regular expression pattern."""
    _compiled: Pattern = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """Initialize the compiled regular expression pattern after the model is initialized.

        Args:
            __context (Any): The context in which the model is initialized.
        """
        self._compiled = compile(self.pattern, self.flags)

    def capture(self, text: str) -> Tuple[str, ...] | str | None:
        """Capture the first occurrence of the pattern in the given text.

        Args:
            text (str): The text to search the pattern in.

        Returns:
            str | None: The captured text if the pattern is found, otherwise None.

        """
        match = self._compiled.search(text)
        if match is None:
            return None

        if self.target_groups:
            cap = tuple(match.group(g) for g in self.target_groups)
            logger.debug(f"Captured text: {'\n\n'.join(cap)}")
            return cap
        cap = match.group(1)
        logger.debug(f"Captured text: \n{cap}")
        return cap

    def convert_with[T](self, text: str, convertor: Callable[[Tuple[str, ...]], T] | Callable[[str], T]) -> T | None:
        """Convert the given text using the pattern.

        Args:
            text (str): The text to search the pattern in.
            convertor (Callable[[Tuple[str, ...]], T] | Callable[[str], T]): The function to convert the captured text.

        Returns:
            str | None: The converted text if the pattern is found, otherwise None.
        """
        if (cap := self.capture(text)) is None:
            return None
        try:
            return convertor(cap)
        except (ValueError, SyntaxError) as e:
            logger.error(f"Failed to convert text using {convertor.__name__} to convert.\nerror: {e}\n {cap}")
            return None

    @classmethod
    def capture_code_block(cls, language: str) -> Self:
        """Capture the first occurrence of a code block in the given text.

        Args:
            language (str): The text containing the code block.

        Returns:
            Self: The instance of the class with the captured code block.
        """
        return cls(pattern=f"```{language}\n(.*?)\n```")


JsonCapture = Capture.capture_code_block("json")
PythonCapture = Capture.capture_code_block("python")
MarkdownCapture = Capture.capture_code_block("markdown")
CodeBlockCapture = Capture(pattern="```.*?\n(.*?)\n```")
