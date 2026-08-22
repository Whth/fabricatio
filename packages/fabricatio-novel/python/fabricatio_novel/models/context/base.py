"""Base context machinery: character spans and shared channel element behavior."""

from abc import ABC, abstractmethod
from typing import Callable, Generator, Self, Sequence, final

from fabricatio_capabilities.models.generic import PersistentAble, WordCount
from fabricatio_character.models.character import CharacterCard
from fabricatio_core import logger
from fabricatio_core.models.generic import JSONList, SketchedAble
from fabricatio_core.utils import ok
from pydantic import Field

from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.series_book import SeriesBible


def merge_writing_constraints(parent: str, own: str) -> str:
    """Accumulate a parent's writing constraint with this element's own allocation.

    The parent's constraint stays in force verbatim; the element's own allocation
    (empty when none) is appended on a new line. Both empty yields an empty string.
    """
    return "\n".join(part for part in (parent, own) if part)


def merge_writing_styles(inherited: list[str], own: str) -> list[str]:
    """Extend inherited writing style entries with this element's own allocation; empty adds none."""
    return [*inherited, own] if own else list(inherited)


class CharacterSpan(SketchedAble):
    """A character's state arc between two cards: the start card and the end card."""

    start: CharacterCard
    """The character state at the beginning of this span."""
    end: CharacterCard
    """The character state at the end of this span."""

    @final
    def dump_to_prompt(self) -> str:
        """Render this span as the Initial State / finalizing State prompt pair."""
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


def stitch_boundaries[C](
    parent_spans: list[CharacterSpan],
    children: Sequence[C],
    spans_accessor: Callable[[C], list[CharacterSpan]],
    proposed: list[list[CharacterCard]],
    expected_boundaries: int,
    level: str,
) -> None:
    """Stitch one child span per element from the parent spans and proposed boundaries.

    For every roster character the parent span opens the first child and
    closes the last; the proposed boundary cards are the intermediate
    states. A character whose boundary count does not match the expected
    number is skipped so a malformed proposal never yields a broken
    chain.
    """
    for char_index, parent_span in enumerate(parent_spans):
        boundaries = proposed[char_index] if char_index < len(proposed) else []
        if len(boundaries) != expected_boundaries:
            logger.warn(
                f"Expected {expected_boundaries} {level} boundary card(s) for '{parent_span.start.name}'"
                f" but got {len(boundaries)}; skipping"
            )
            continue
        for child, span in zip(children, derive_child_spans(parent_span, boundaries), strict=True):
            spans_accessor(child).append(span)
    logger.debug(f"Stitched {level} spans from boundary cards")


class CharacterSpans(JSONList[CharacterSpan]):
    """An ordered list of character spans, one per roster character."""


class ContextBase[C: ContextBase](WordCount, PersistentAble, ABC):
    """Base class for hierarchical novel contexts shared across chapter, story and scene levels."""

    title: str = ""
    """The title of this element; the novel root keeps it empty until planned."""

    description: str = ""
    """A detailed description of this element's intent and content."""

    writing_styles: list[str] = Field(default_factory=list)
    """Writing style directives accumulated down the tree: inherited guidance first, this
    element's own plan entry last; RAG reference texts join the same list when enabled."""

    writing_constraint: str = ""
    """Hard writing constraint allocated down from the novel (point of view, tense,
    prohibitions); the accumulated chain of the parent's constraint plus this element's own
    allocation. Empty when no constraint applies."""

    cast: list[str] = Field(default_factory=list)
    """Names of the characters on stage in this element, proposed with its plan."""

    language: str = ""
    """Written language; run-wide constant, set progressively during context creation."""

    outline: str = ""
    """The raw novel outline; run-wide constant, copied down every creation chain so each
    planning prompt grounds on the full source text instead of compressed parent descriptions."""

    series_bible: SeriesBible | None = None
    """The novel's setting bible; uninitialized until set or broadcast down from the novel context."""

    prefix_log: ContextLog = Field(default_factory=ContextLog)
    """Everything composed before this element as an append-only entry log; injected by the
    parent before composition."""

    def set_language(self, language: str) -> Self:
        """Set the written language of this element and return self."""
        self.language = language
        return self

    def set_outline(self, outline: str) -> Self:
        """Set the raw novel outline carried into this element's planning prompts and return self."""
        self.outline = outline
        return self

    def set_series_bible(self, series_bible: SeriesBible | None) -> Self:
        """Set the novel's setting bible on this element and return self."""
        self.series_bible = series_bible
        return self

    def set_writing_styles(self, writing_styles: list[str]) -> Self:
        """Replace this element's accumulated writing style entries and return self."""
        self.writing_styles = writing_styles
        return self

    def add_writing_styles(self, styles: list[str]) -> Self:
        """Append non-empty writing style entries and return self."""
        self.writing_styles.extend(style for style in styles if style)
        return self

    def dump_writing_styles(self) -> str:
        """Render the style entries as bullet lines for prompts."""
        return "\n".join(f"- {style}" for style in self.writing_styles if style)

    def set_writing_constraint(self, writing_constraint: str) -> Self:
        """Set the accumulated writing constraint carried down to the written scenes."""
        self.writing_constraint = writing_constraint
        return self

    def set_cast(self, cast: list[str]) -> Self:
        """Set the on-stage character names of this element and return self."""
        self.cast = cast
        return self

    def set_prefix_log(self, prefix_log: ContextLog) -> Self:
        """Set the append-only log of everything composed before this element and return self."""
        self.prefix_log = prefix_log
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

    def prefixed_header_entry(self) -> ContextEntry | None:
        """This element's heading block as an entry seeded into every child's prefix.

        Only the chapter renders its own title and description here; the novel's,
        story's and scene's own titles are not part of the running text.
        """
        return None

    @abstractmethod
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """This element's blocks contributed to every following sibling's prefix.

        Only the chapter contributes its heading entry; stories forward their
        scenes' entries and scenes contribute their composed content.
        """
        ...

    @final
    def iter_prefixed_contexts(self) -> Generator[C, None, None]:
        """Set each child's running prefix log in place and yield it.

        The running log seeds with this element's incoming prefix plus its own
        heading entry, so each child sees exactly the history that precedes its
        content in the final manuscript. Seeding is pure — logs rebind fresh
        tuples — so repeated walks are idempotent and readers holding an earlier
        log never observe later appends.
        """
        seed = self.prefix_log
        if header := self.prefixed_header_entry():
            seed = seed.with_entry(header)
        for child in self.iter_child_contexts():
            child.set_prefix_log(seed)
            yield child
            seed = seed.with_entries(child.prefixed_entries())

    def broadcast_settings_bible(self) -> Self:
        """Push this context's settings bible onto every child context."""
        for child in self.iter_child_contexts():
            child.set_series_bible(self.series_bible)
        return self
