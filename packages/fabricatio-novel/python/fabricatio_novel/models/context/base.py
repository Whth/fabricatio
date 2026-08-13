"""Base context machinery: character traces and shared channel element behavior."""

from abc import ABC, abstractmethod
from typing import Generator, Self, final

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from pydantic import Field

from fabricatio_novel.models.series_book import SeriesBible


class CharacterTrace(SketchedAble):
    """A character's evolution across the novel: start card, end card and interpolated diffs."""

    start: CharacterCard
    end: CharacterCard

    interpolates: list[CharacterCardDiff] = Field(default_factory=list)

    @final
    def iter_character_cards(self) -> Generator[CharacterCard, None, None]:
        """Iterate over the character cards along this trace, in evolution order.

        Yields the `start` card, then one card per interpolated diff applied
        to the previous state, and finally the `end` card.
        """
        card = self.start
        yield card
        for diff in self.interpolates:
            card = card.apply(diff)
            yield card
        yield self.end

    @final
    def intepl(self, diffs: list[CharacterCardDiff]) -> Self:
        """Store the interpolate diffs describing the trace's evolution and return self."""
        self.interpolates = diffs
        return self

    @final
    def dump_to_prompt(self) -> str:
        """Render the trace as a natural-language description of the evolution.

        The starting card is rendered once; each interpolated diff then
        describes only its changed fields (before → after), with the cause
        stated explicitly as a labeled `reason:` clause instead of a bare
        separator, skipping redundant repeats of unchanged fields to save
        tokens.
        """
        card = self.start
        lines = [
            f"{card.name} — {card.role}. look: {card.look} | act: {card.act} | want: {card.want} | flaw: {card.flaw}"
        ]
        for index, diff in enumerate(self.interpolates, start=1):
            changes = diff.model_dump(exclude_none=True, exclude={"reason"})
            steps = "; ".join(f"{field}: {getattr(card, field)} → {value}" for field, value in changes.items())
            lines.append(f"{index}. {steps}; reason: {diff.reason}" if steps else f"{index}. reason: {diff.reason}")
            card = card.apply(diff)
        return "\n".join(lines)


class ContextBase[C: ContextBase](WordCount, PersistentAble, ABC):
    """Base class of every pipeline channel element, carrying writing state and child contexts."""

    title: str = ""
    """The title of this element; the novel root keeps it empty until planned."""

    description: str = ""
    """A detailed description of this element's intent and content."""

    writing_style: str = ""
    """Writing technique guidance for this element's prose: voice, tone, rhythm, dialogue
    handling; proposed with the plan and carried down to the scene that is written."""

    character_trace: list[CharacterTrace] = Field(default_factory=list)

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

    def set_charactor_traces(self, traces: list[CharacterTrace]) -> Self:
        """Replace this element's character traces and return self."""
        self.character_trace = traces
        return self

    def add_charactor_trace(self, trace: CharacterTrace) -> Self:
        """Append one character trace to this element and return self."""
        self.character_trace.append(trace)
        return self

    def dump_charactors(self) -> str:
        """Render every character's evolution for prompts, in trace order."""
        return "\n\n".join(trace.dump_to_prompt() for trace in self.character_trace)

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
