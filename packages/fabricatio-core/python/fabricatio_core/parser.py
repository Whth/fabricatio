"""A module for capturing patterns in text using regular expressions."""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Optional, Self, Type

import ujson
from json_repair import repair_json

from fabricatio_core.journal import logger
from fabricatio_core.rust import CONFIG


@dataclass(frozen=True)
class Capture:
    """A class to capture patterns in text using regular expressions.

    Attributes:
        pattern (str): The regex pattern to search for.
        flags (int): Flags to apply when compiling the regex.
        capture_type (Optional[str]): Optional hint for post-processing (e.g., 'json').
    """

    pattern: str
    """The regular expression pattern to search for."""
    flags: int = re.DOTALL | re.MULTILINE | re.IGNORECASE
    """Flags to control regex behavior (DOTALL, MULTILINE, IGNORECASE by default)."""
    capture_type: Optional[str] = None
    """Optional type identifier for post-processing (e.g., 'json' for JSON repair)."""

    def fix(self, text: str) -> str:
        """Fix the text based on capture_type (e.g., JSON repair)."""
        match self.capture_type:
            case "json" if CONFIG.general.use_json_repair:
                logger.debug("Applying JSON repair to text.")
                return repair_json(text, ensure_ascii=False)
            case _:
                return text

    def capture(self, text: str) -> Optional[str]:
        """Capture the first match of the pattern in the text."""
        compiled = re.compile(self.pattern, self.flags)
        match = compiled.match(text) or compiled.search(text)
        if match is None:
            logger.debug(f"Capture Failed: {text}")
            return None

        # Only consider the first group
        if match.groups():
            cap = self.fix(match.groups()[0])
            logger.debug(f"Captured text: \n{cap}")
            return cap
        return None

    def convert_with(
        self,
        text: str,
        convertor: Callable[[str], Any],
    ) -> Optional[Any]:
        """Convert captured text using a provided function."""
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
        deserializer: Callable[[str], K] = lambda x: ujson.loads(x),
    ) -> Optional[T]:
        """Deserialize and validate the captured text against expected types."""
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
        """Capture a code block of the given language."""
        return cls(pattern=f"```{language}(.*?)```", capture_type=language)

    @classmethod
    @lru_cache(32)
    def capture_generic_block(cls, language: str) -> Self:
        """Capture a generic block of the given language."""
        return cls(
            pattern=f"--- Start of {language} ---(.*?)--- End of {language} ---",
            capture_type=language,
        )

    @classmethod
    @lru_cache(32)
    def capture_content(cls, left_delimiter: str, right_delimiter: str | None = None) -> Self:
        """Capture content between delimiters."""
        return cls(pattern=f"{left_delimiter}(.*?){right_delimiter or left_delimiter}")


JsonCapture = Capture.capture_code_block("json")
PythonCapture = Capture.capture_code_block("python")
GenericCapture = Capture.capture_generic_block("String")
