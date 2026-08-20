"""Base context machinery: character spans and shared channel element behavior."""

from abc import ABC, abstractmethod
from typing import Generator, Self, final

from pydantic import Field

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_character.models.character import CharacterCard
from fabricatio_core.models.generic import JSONList, SketchedAble
from fabricatio_core.utils import ok
from fabricatio_novel.models.series_book import SeriesBible


def merge_writing_constraints(parent: str, own: str) -> str:
    """Accumulate a parent's writing constraint with this element's own allocation.

    The parent's constraint stays in force verbatim; the element's own allocation
    (empty when none) is appended on a new line. Both empty yields an empty string.
    """
    return "\n".join(part for part in (parent, own) if part)


class CharacterSpan(SketchedAble):
    start: CharacterCard
    """"""
    end: CharacterCard
    """"""

    @final
    def dump_to_prompt(self) -> str:
        return f"Initial State:\n{self.start.as_prompt()}\n\nfinalizing State:\n{self.end.as_prompt()}"


def derive_child_spans(parent: CharacterSpan, boundaries: list[CharacterCard]) -> list[CharacterSpan]:
    """Split a parent span into child spans at the given boundary cards.

    The parent's start opens the first child span and its end closes the
    last one; each boundary card closes one child and opens the next.
    ``len(boundaries) + 1`` child spans are returned, so with N children
    only N-1 intermediate cards need to be drafted.
    """
    chain = [parent.start, *boundaries, parent.end]
    return [CharacterSpan(start=chain[i], end=chain[i + 1]) for i in range(len(chain) - 1)]


class CharacterSpans(JSONList[CharacterSpan]): ...


class ContextBase[C: ContextBase](WordCount, PersistentAble, ABC):
    title: str = ""
    """The title of this element; the novel root keeps it empty until planned."""

    description: str = ""
    """A detailed description of this element's intent and content."""

    writing_style: str = ""
    """Writing technique guidance for this element's prose: voice, tone, rhythm, dialogue
    handling; proposed with the plan and carried down to the scene that is written."""

    writing_constraint: str = ""
    """Hard writing constraint allocated down from the novel (point of view, tense,
    prohibitions); the accumulated chain of the parent's constraint plus this element's own
    allocation. Empty when no constraint applies."""

    cast: list[str] = Field(default_factory=list)
    """Names of the characters on stage in this element, proposed with its plan."""

    language: str = ""
    """Written language; run-wide constant, set progressively during context creation."""

    series_bible: SeriesBible | None = None
    """The novel's setting bible; uninitialized until set or broadcast down from the novel context."""

    prefixed_content: str = ""
    """Everything composed before this element in the novel; injected by the parent before composition."""

    def set_language(self, language: str) -> Self:
        """Set the written language of this element and return self."""
        self.language = language
        return self

    def set_series_bible(self, series_bible: SeriesBible | None) -> Self:
        """Set the novel's setting bible on this element and return self."""
        self.series_bible = series_bible
        return self

    def set_writing_style(self, writing_style: str) -> Self:
        """Set the writing technique guidance carried down to the written scenes."""
        self.writing_style = writing_style
        return self

    def set_writing_constraint(self, writing_constraint: str) -> Self:
        """Set the accumulated writing constraint carried down to the written scenes."""
        self.writing_constraint = writing_constraint
        return self

    def set_cast(self, cast: list[str]) -> Self:
        """Set the on-stage character names of this element and return self."""
        self.cast = cast
        return self

    def access_settings_bible(self) -> SeriesBible:
        """Return the initialized settings bible.

        Raises:
            ValueError: if the settings bible was never initialized on this context.
        """
        return ok(self.series_bible, f"Settings bible is not initialized on {self.__class__.__name__}")

    def iter_child_contexts(self) -> Generator[C, None, None]:
        """Yield this context's child contexts, in composition order; leaf contexts yield nothing."""
        yield from ()

    def render_prefixed_header(self) -> str:
        """Render this element's own heading block, seeded into every child's prefix.

        Only the chapter renders its own title and description here; the novel's,
        story's and scene's own titles are not part of the running text.
        """
        return ""

    @final
    def iter_prefixed_contexts(self) -> Generator[C, None, None]:
        """Set each child's running prefixed content in place and yield it.

        The running prefix seeds with this element's incoming prefixed content
        plus its own heading block, so each child sees the exact text that will
        precede its content in the final manuscript. Composed content is read
        live at each step, so in-place updates made while iterating are
        reflected in the following children's prefixes.
        """
        prefix = "\n\n".join(p for p in (self.prefixed_content, self.render_prefixed_header()) if p)
        for child in self.iter_child_contexts():
            child.set_prefixed_content(prefix)
            yield child
            prefix = "\n\n".join(p for p in (prefix, child.render_prefixed_block()) if p)

    @abstractmethod
    def render_prefixed_block(self) -> str:
        """Render this element's block, appended to the prefixed content of every following sibling.

        Only the chapter renders its own title and description; stories render
        their children's blocks and scenes render their composed content.
        """
        ...

    def broadcast_settings_bible(self) -> Self:
        """Push this context's settings bible onto every child context."""
        for child in self.iter_child_contexts():
            child.set_series_bible(self.series_bible)
        return self

    def set_prefixed_content(self, prefixed_content: str) -> Self:
        """Set the composed text preceding this element in the novel and return self."""
        self.prefixed_content = prefixed_content
        return self
