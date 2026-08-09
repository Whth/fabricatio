from abc import ABC
from typing import ClassVar, Generator, Self, final

from pydantic import Field

from fabricatio_capabilities.models.generic import WordCount, PersistentAble
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff
from fabricatio_character.utils import dump_card
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok

from fabricatio_novel.models.series_book import SeriesBible


class CharactorTrace(SketchedAble):
    start: CharacterCard
    end: CharacterCard

    interpolates: list[CharacterCardDiff] = Field(default_factory=list)

    @final
    def iter_charactor_cards(self) -> Generator[CharacterCard, None, None]:
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
        self.interpolates = diffs
        return self


class ContextBase(WordCount, PersistentAble, ABC):
    title: str = ""
    """The title of this element; the novel root keeps it empty until planned."""

    description: str = ""
    """A short description of this element's intent and content."""

    content: str = ""
    """The composed content of this element; containers keep it empty and render children instead."""

    charactor_trace: list[CharactorTrace] = Field(default_factory=list)

    language: str = ""
    """Written language; run-wide constant, set progressively during context creation."""

    series_bible: SeriesBible | None = None
    """The novel's setting bible; uninitialized until set or broadcast down from the novel context."""

    prefixed_content: str = ""
    """Everything composed before this element in the novel; injected by the parent before composition."""

    heading_level: ClassVar[str] = ""
    """Markdown heading marker used when this element's block is rendered into a prefixed content."""

    def set_language(self, language: str) -> Self:
        self.language = language
        return self

    def set_series_bible(self, series_bible: SeriesBible | None) -> Self:
        self.series_bible = series_bible
        return self

    def set_content(self, content: str) -> Self:
        self.content = content
        return self

    def set_charactor_traces(self, traces: list[CharactorTrace]) -> Self:
        self.charactor_trace = traces
        return self

    def dump_charactors(self) -> str:
        """Render every character's state chain for prompts, in trace order."""
        return "\n\n".join(dump_card(*trace.iter_charactor_cards()) for trace in self.charactor_trace)

    def access_settings_bible(self) -> SeriesBible:
        """Return the initialized settings bible.

        Raises:
            ValueError: if the settings bible was never initialized on this context.
        """
        return ok(self.series_bible, f"Settings bible is not initialized on {self.__class__.__name__}")

    def iter_child_contexts(self) -> Generator["ContextBase", None, None]:
        """Yield this context's child contexts, in composition order; leaf contexts yield nothing."""
        yield from ()

    @final
    def iter_prefixed_contexts(self) -> Generator["ContextBase", None, None]:
        """Set each child's running prefixed content in place and yield it.

        Composed content is read live at each step, so in-place updates made
        while iterating are reflected in the following children's prefixes.
        """
        prefix = self.prefixed_content
        for child in self.iter_child_contexts():
            child.set_prefixed_content(prefix)
            yield child
            prefix = "\n\n".join(p for p in (prefix, child.render_prefixed_block()) if p)

    @final
    def render_prefixed_block(self) -> str:
        """Render this element's title, description, and composed content as a markdown block.

        Container elements render their children's blocks recursively; leaf
        elements render their own composed content. The rendered block is
        appended to the prefixed content of every following sibling.
        """
        parts: list[str] = []
        if self.title:
            parts.append(f"{self.heading_level} {self.title}")
        if self.description:
            parts.append(f"> {self.description}")
        children = list(self.iter_child_contexts())
        if children:
            parts.extend(child.render_prefixed_block() for child in children)
        elif self.content:
            parts.append(self.content)
        return "\n\n".join(parts)

    def broadcast_settings_bible(self) -> Self:
        """Push this context's settings bible onto every child context."""
        for child in self.iter_child_contexts():
            child.set_series_bible(self.series_bible)
        return self

    def set_prefixed_content(self, prefixed_content: str) -> Self:
        self.prefixed_content = prefixed_content
        return self
