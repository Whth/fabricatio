"""A module for capturing patterns in text using regular expressions."""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Iterable, List, Optional, Self, Tuple, Type, Union

import ujson
from json_repair import repair_json

from fabricatio.journal import logger
from fabricatio.rust import CONFIG


@dataclass(frozen=True)
class Capture:
    """A class to capture patterns in text using regular expressions.

    Attributes:
        target_groups (Tuple[int, ...]): The target groups to extract from the match.
        pattern (str): The regex pattern to search for.
        flags (int): Flags to apply when compiling the regex.
        capture_type (Optional[str]): Optional hint for post-processing (e.g., 'json').
    """

    pattern: str = field()
    """The regular expression pattern to search for."""
    flags: int = re.DOTALL | re.MULTILINE | re.IGNORECASE
    """Flags to control regex behavior (DOTALL, MULTILINE, IGNORECASE by default)."""
    capture_type: Optional[str] = None
    """Optional type identifier for post-processing (e.g., 'json' for JSON repair)."""
    target_groups: Tuple[int, ...] = field(default_factory=tuple)
    """Tuple of group indices to extract from the match (1-based indexing)."""

    def fix(self, text: Union[str, Iterable[str], Any]) -> Union[str, List[str], Any]:
        """Fix the text based on capture_type (e.g., JSON repair)."""
        match self.capture_type:
            case "json" if CONFIG.general.use_json_repair:
                logger.debug("Applying JSON repair to text.")
                if isinstance(text, str):
                    return repair_json(text, ensure_ascii=False)
                return [repair_json(item, ensure_ascii=False) for item in text]
            case _:
                return text

    def capture(self, text: str) -> Optional[Union[str, Tuple[str, ...]]]:
        """Capture the first match of the pattern in the text."""
        compiled = re.compile(self.pattern, self.flags)
        match = compiled.match(text) or compiled.search(text)
        if match is None:
            logger.debug(f"Capture Failed: {text}")
            return None

        groups = self.fix(match.groups())
        if self.target_groups:
            cap = tuple(groups[g - 1] for g in self.target_groups)
            logger.debug(f"Captured texts: {'\n==\n'.join(cap)}")
            return cap
        cap = groups[0]
        logger.debug(f"Captured text: \n{cap}")
        return cap

    def convert_with(
        self,
        text: str,
        convertor: Callable[[Union[str, Tuple[str, ...]]], Any],
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
        deserializer: Callable[[Union[str, Tuple[str, ...]]], K] = lambda x: ujson.loads(x) if isinstance(x, str) else ujson.loads(x[0]),
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


JsonCapture = Capture.capture_code_block("json")
PythonCapture = Capture.capture_code_block("python")
GenericCapture = Capture.capture_generic_block("String")
