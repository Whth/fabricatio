"""A module for capturing patterns in text using regular expressions."""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Optional, Self, Type

import orjson
from json_repair import repair_json

from fabricatio_core.journal import logger
from fabricatio_core.rust import CONFIG


@dataclass(frozen=True)
class Capture:
    """A class to capture patterns in text using regular expressions.

    This class provides methods for capturing specific patterns in text and performing
    additional processing such as fixing, converting, and validating the captured text.

    Note:
        - The `fix` method can be used to apply specific fixes to the captured text based on `capture_type`.
    """

    pattern: str
    """The regular expression pattern to search for."""
    flags: int = re.DOTALL | re.MULTILINE | re.IGNORECASE
    """Flags to control regex behavior (DOTALL, MULTILINE, IGNORECASE by default)."""
    capture_type: Optional[str] = None
    """Optional type identifier for post-processing (e.g., 'json' for JSON repair)."""

    def __post_init__(self) -> None:
        """Post Initialize the Capture instance."""
        if not self.pattern:
            raise ValueError("Pattern cannot be empty.")

    def fix(self, text: str) -> str:
        """Fix the text based on capture_type (e.g., JSON repair).

        Args:
            text (str): The input text to be fixed.

        Returns:
            str: The fixed text.

        Note:
            - If `capture_type` is 'json', this method applies JSON repair to the text.
        """
        match self.capture_type:
            case "json" if CONFIG.general.use_json_repair:
                logger.debug("Applying JSON repair to text.")
                return repair_json(text, ensure_ascii=False)
            case _:
                return text

    def capture(self, text: str) -> Optional[str]:
        """Capture the first match of the pattern in the text.

        Args:
            text (str): The input text to search within.

        Returns:
            Optional[str]: The captured text or None if no match is found.

        Raises:
            ValueError: If the pattern does not match any part of the text.

        Note:
            - This method uses both `match` and `search` to find the pattern in the text.
            - It only considers the first group of the match.
        """
        compiled = re.compile(self.pattern, self.flags)
        match = compiled.match(text) or compiled.search(text)
        if match is None:
            logger.debug(f"Capture Failed: {text!r}")
            return None
        cap = self.fix(match.groups()[0] if match.groups() else match.group())
        logger.debug(f"Captured text: \n{cap}")
        return cap

    def convert_with(
        self,
        text: str,
        convertor: Callable[[str], Any],
    ) -> Optional[Any]:
        """Convert captured text using a provided function.

        Args:
            text (str): The input text to capture and convert.
            convertor (Callable[[str], Any]): The function to convert the captured text.

        Returns:
            Optional[Any]: The converted result or None if conversion fails.

        Raises:
            Exception: If the conversion function raises an exception.

        Note:
            - This method captures the text and then applies the provided conversion function.
        """
        if (cap := self.capture(text)) is None:
            return None
        try:
            return convertor(cap)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to convert text using {convertor.__name__}: {e}\n{cap}")
            return None

    def validate_with[T, K, E](
        self,
        text: str,
        target_type: Type[T],
        elements_type: Optional[Type[E]] = None,
        length: Optional[int] = None,
        deserializer: Callable[[str], K] = lambda x: orjson.loads(x),
    ) -> Optional[T]:
        """Deserialize and validate the captured text against expected types.

        Args:
            text (str): The input text to capture and validate.
            target_type (Type[T]): The expected type of the deserialized object.
            elements_type (Optional[Type[E]]): The expected type of elements in the deserialized object.
            length (Optional[int]): The expected length of the deserialized object.
            deserializer (Callable[[str], K]): The function to deserialize the captured text.

        Returns:
            Optional[T]: The validated object or None if validation fails.

        Note:
            - This method captures the text, deserializes it, and validates it against the specified criteria.
        """
        judges = [lambda obj: isinstance(obj, target_type)]
        if elements_type:
            judges.append(lambda obj: all(isinstance(e, elements_type) for e in obj))
        if length:
            judges.append(lambda obj: len(obj) == length)

        if (out := self.convert_with(text, deserializer)) and all(j(out) for j in judges):
            return out  # type: ignore
        return None

    @classmethod
    @lru_cache(32)
    def capture_code_block(cls, language: str) -> Self:
        """Capture a code block of the given language.

        Args:
            language (str): The programming language of the code block.

        Returns:
            Self: An instance of Capture configured to capture code blocks.

        Note:
            - This method creates a Capture instance with a pattern specific to code blocks.
        """
        return cls(pattern=f"```{language}\n(.*?)\n```", capture_type=language)

    @classmethod
    @lru_cache(32)
    def capture_generic_block(cls, language: str) -> Self:
        """Capture a generic block of the given language.

        Args:
            language (str): The language or identifier of the generic block.

        Returns:
            Self: An instance of Capture configured to capture generic blocks.

        Note:
            - This method creates a Capture instance with a pattern specific to generic blocks.
        """
        return cls(
            pattern=f"--- Start of {language} ---\n(.*?)\n--- End of {language} ---",
            capture_type=language,
        )

    @classmethod
    @lru_cache(32)
    def capture_content(cls, left_delimiter: str, right_delimiter: str | None = None) -> Self:
        """Capture content between delimiters.

        Args:
            left_delimiter (str): The left delimiter marking the start of the content.
            right_delimiter (str | None): The right delimiter marking the end of the content.

        Returns:
            Self: An instance of Capture configured to capture content between delimiters.

        Note:
            - If `right_delimiter` is not provided, it defaults to `left_delimiter`.
        """
        return cls(pattern=f"{left_delimiter}(.*?){right_delimiter or left_delimiter}")


JsonCapture = Capture.capture_code_block("json")
PythonCapture = Capture.capture_code_block("python")
GenericCapture = Capture.capture_generic_block("String")
