"""Declarative response scripts for the dummy LLM router.

A :class:`MockScript` names every response it installs, installs them strictly
(no padding unless asked), and enriches the Rust-side ``DummyModel exhausted``
error with the declared script, so an under-provisioned test fails with its own
vocabulary instead of a bare queue error.

Limitation: the router exposes no way to read the remaining queue, so a script
cannot report responses that were declared but never consumed.
"""

from dataclasses import dataclass, replace
from types import TracebackType
from typing import Self

from pydantic import BaseModel, JsonValue

from fabricatio_mock.constants import DUMMY_LLM_GROUP
from fabricatio_mock.models.mock_router import Value, pad_responses
from fabricatio_mock.utils import clear_dummy_responses, setup_dummy_responses

type ScriptValue = Value[BaseModel] | Value[JsonValue] | Value[str]
"""A response value accepted by :class:`MockScript`."""

EXHAUSTED_MARKER: str = "DummyModel exhausted"
"""Substring of the error the Rust dummy model raises once its queue runs dry."""


class ScriptExhaustedError(RuntimeError):
    """Raised when the code under test consumes more responses than a script declared."""


@dataclass(frozen=True)
class MockScript:
    """Ordered dummy LLM responses for one test.

    Install it with a ``with`` block::

        from fabricatio_mock import MockScript, Value

        with MockScript.from_values(Value.from_model(plan, name="metadata")):
            result = await role.propose(NovelPlan, "outline...")

    Responses are consumed in declaration order (the Rust model pops LIFO; the
    installer reverses). Unlike the bare ``install_router_usage`` helper, an
    exhausted script raises :class:`ScriptExhaustedError` naming every declared
    response, and ``reset_on_exit`` empties the queue on the way out.
    """

    values: tuple[ScriptValue, ...] = ()
    """Responses, consumed in this order."""

    padding: int = 0
    """Extra copies of the last response appended for retries. Zero means strict."""

    group: str = DUMMY_LLM_GROUP
    """Route group the responses are deployed to."""

    reset_on_exit: bool = False
    """Whether to empty the group's queue when the ``with`` block exits."""

    @classmethod
    def from_values(
        cls,
        *values: ScriptValue,
        padding: int = 0,
        group: str = DUMMY_LLM_GROUP,
        reset_on_exit: bool = False,
    ) -> Self:
        """Build a script from values that already carry their labels.

        Args:
            *values: Responses in consumption order.
            padding: Extra copies of the last response appended for retries.
            group: Route group the responses are deployed to.
            reset_on_exit: Whether to empty the group's queue on exit.

        Returns:
            Self: The script.
        """
        return cls(values=values, padding=padding, group=group, reset_on_exit=reset_on_exit)

    @classmethod
    def from_texts(
        cls,
        *texts: str,
        padding: int = 0,
        group: str = DUMMY_LLM_GROUP,
        reset_on_exit: bool = False,
    ) -> Self:
        """Build a script from plain-text responses, auto-labelled ``text-1``, ``text-2``, ...

        Args:
            *texts: Response texts in consumption order.
            padding: Extra copies of the last response appended for retries.
            group: Route group the responses are deployed to.
            reset_on_exit: Whether to empty the group's queue on exit.

        Returns:
            Self: The script.
        """
        return cls.from_values(
            *(Value.from_text(text, name=f"text-{position}") for position, text in enumerate(texts, start=1)),
            padding=padding,
            group=group,
            reset_on_exit=reset_on_exit,
        )

    def with_value(self, value: ScriptValue) -> Self:
        """Return a script with one more response appended.

        Args:
            value: Response to append.

        Returns:
            Self: The extended script.
        """
        return replace(self, values=(*self.values, value))

    def with_values(self, *values: ScriptValue) -> Self:
        """Return a script with more responses appended.

        Args:
            *values: Responses to append, in order.

        Returns:
            Self: The extended script.
        """
        return replace(self, values=(*self.values, *values))

    def with_text(self, text: str, *, name: str = "") -> Self:
        """Return a script with one more plain-text response appended.

        Args:
            text: Response text.
            name: Optional label; defaults to ``text-<position>``.

        Returns:
            Self: The extended script.
        """
        return self.with_value(Value.from_text(text, name=name or f"text-{len(self.values) + 1}"))

    def with_padding(self, padding: int) -> Self:
        """Return a script that repeats its last response ``padding`` times.

        Args:
            padding: Number of extra copies appended after the declared responses.

        Returns:
            Self: The padded script.
        """
        return replace(self, padding=padding)

    def with_group(self, group: str) -> Self:
        """Return a script bound to another route group.

        Args:
            group: Route group name.

        Returns:
            Self: The rebound script.
        """
        return replace(self, group=group)

    def with_reset_on_exit(self, enabled: bool = True) -> Self:
        """Return a script that empties its group when the block exits.

        Args:
            enabled: Whether to clear the queue on exit.

        Returns:
            Self: The updated script.
        """
        return replace(self, reset_on_exit=enabled)

    def install(self) -> None:
        """Deploy the declared responses to the script's group, in FIFO order.

        Raises:
            ValueError: If the script declares no responses.
        """
        if not self.values:
            raise ValueError("MockScript requires at least one declared response.")
        contents = [value.to_string() for value in self.values]
        setup_dummy_responses(*pad_responses(*contents, padding=self.padding), group=self.group)

    def clear(self) -> None:
        """Empty the script's group so later calls fail loudly instead of consuming leftovers."""
        clear_dummy_responses(self.group)

    def describe(self) -> str:
        """List the declared responses, one per line.

        Returns:
            str: The declared script, prefixed with its group.
        """
        declared = "\n".join(
            f"  {position}. {self._label(value, position)}" for position, value in enumerate(self.values, start=1)
        )
        return f"MockScript(group={self.group!r}, padding={self.padding}):\n{declared}"

    @staticmethod
    def _label(value: ScriptValue, position: int) -> str:
        """Name a declared value for failure reports.

        Args:
            value: Declared response.
            position: One-based position in the script.

        Returns:
            str: The value's label, or a short excerpt of its content.
        """
        return value.name or f"response {position} ({MockScript._excerpt(value.to_string())})"

    @staticmethod
    def _excerpt(content: str, limit: int = 40) -> str:
        """Collapse and shorten a response for display.

        Args:
            content: Response text.
            limit: Maximum length of the excerpt.

        Returns:
            str: The excerpt.
        """
        collapsed = " ".join(content.split())
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[: limit - 3]}..."

    def __enter__(self) -> Self:
        """Install the script.

        Returns:
            Self: The installed script.
        """
        self.install()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Clear the queue when requested and label exhaustion failures.

        Args:
            exc_type: Exception type raised inside the block, if any.
            exc: Exception raised inside the block, if any.
            traceback: Traceback of the exception, if any.

        Raises:
            ScriptExhaustedError: If the block failed because the dummy queue ran dry.
        """
        if self.reset_on_exit:
            self.clear()
        if exc is not None and EXHAUSTED_MARKER in str(exc):
            raise ScriptExhaustedError(
                f"MockScript exhausted: the code under test requested more LLM responses than the "
                f"{len(self.values)} declared for group {self.group!r}:\n"
                f"{self.describe()}\n"
                "Declare the missing response, or opt into silent repeats with .with_padding(n)."
            ) from exc
