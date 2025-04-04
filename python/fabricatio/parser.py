"""A module to parse text using regular expressions."""

from typing import Any, Callable, Iterable, List, Optional, Self, Tuple, Type

import orjson
import regex
from json_repair import repair_json
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, PrivateAttr, ValidationError
from regex import Pattern, compile

from fabricatio.config import configs
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
    capture_type: Optional[str] = None
    """The type of capture to perform, e.g., 'json', which is used to dispatch the fixer accordingly."""
    _compiled: Pattern = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """Initialize the compiled pattern."""
        self._compiled = compile(self.pattern, self.flags)

    def fix[T](self, text: str | Iterable[str] | T) -> str | List[str] | T:
        """Fix the text using the pattern.

        Args:
            text (str | List[str]): The text to fix.

        Returns:
            str | List[str]: The fixed text with the same type as input.
        """
        match self.capture_type:
            case "json" if configs.general.use_json_repair:
                logger.debug("Applying json repair to text.")
                if isinstance(text, str):
                    return repair_json(text, ensure_ascii=False)  # pyright: ignore [reportReturnType]
                return [repair_json(item, ensure_ascii=False) for item in text]  # pyright: ignore [reportReturnType, reportGeneralTypeIssues]
            case _:
                return text  # pyright: ignore [reportReturnType]

    def capture(self, text: str) -> Tuple[str, ...] | str | None:
        """Capture the first occurrence of the pattern in the given text.

        Args:
            text (str): The text to search the pattern in.

        Returns:
            str | None: The captured text if the pattern is found, otherwise None.

        """
        if (match :=self._compiled.match(text) or self._compiled.search(text) ) is None:
            logger.debug(f"Capture Failed {type(text)}: \n{text}")
            return None
        groups = self.fix(match.groups())
        if self.target_groups:
            cap = tuple(groups[g - 1] for g in self.target_groups)
            logger.debug(f"Captured text: {'\n\n'.join(cap)}")
            return cap
        cap = groups[0]
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
            return convertor(cap)  # pyright: ignore [reportArgumentType]
        except (ValueError, SyntaxError, ValidationError) as e:
            logger.error(f"Failed to convert text using {convertor.__name__} to convert.\nerror: {e}\n {cap}")
            return None

    def validate_with[K, T, E](
        self,
        text: str,
        target_type: Type[T],
        elements_type: Optional[Type[E]] = None,
        length: Optional[int] = None,
        deserializer: Callable[[Tuple[str, ...]], K] | Callable[[str], K] = orjson.loads,
    ) -> T | None:
        """Validate the given text using the pattern.

        Args:
            text (str): The text to search the pattern in.
            target_type (Type[T]): The expected type of the output, dict or list.
            elements_type (Optional[Type[E]]): The expected type of the elements in the output dict keys or list elements.
            length (Optional[int]): The expected length of the output, bool(length)==False means no length validation.
            deserializer (Callable[[Tuple[str, ...]], K] | Callable[[str], K]): The function to deserialize the captured text.

        Returns:
            T | None: The validated text if the pattern is found and the output is of the expected type, otherwise None.
        """
        judges = [lambda output_obj: isinstance(output_obj, target_type)]
        if elements_type:
            judges.append(lambda output_obj: all(isinstance(e, elements_type) for e in output_obj))
        if length:
            judges.append(lambda output_obj: len(output_obj) == length)

        if (out := self.convert_with(text, deserializer)) and all(j(out) for j in judges):
            return out  # pyright: ignore [reportReturnType]
        return None

    @classmethod
    def capture_code_block(cls, language: str) -> Self:
        """Capture the first occurrence of a code block in the given text.

        Args:
            language (str): The text containing the code block.

        Returns:
            Self: The instance of the class with the captured code block.
        """
        return cls(pattern=f"```{language}(.*?)```", capture_type=language)

    @classmethod
    def capture_generic_block(cls, language: str) -> Self:
        """Capture the first occurrence of a generic code block in the given text.

        Returns:
            Self: The instance of the class with the captured code block.
        """
        return cls(pattern=f"--- Start of {language} ---(.*?)--- end of {language} ---", capture_type=language)


JsonCapture = Capture.capture_code_block("json")
PythonCapture = Capture.capture_code_block("python")
GenericCapture = Capture.capture_generic_block("String")
