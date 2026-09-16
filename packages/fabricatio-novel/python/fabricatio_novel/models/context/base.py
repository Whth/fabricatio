"""Base context machinery: character spans and shared channel element behavior."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Sequence
from typing import Self, final

from pydantic import Field, SerializeAsAny

from fabricatio_capabilities.models.generic import PersistentAble, UpdateFrom, WordCount
from fabricatio_character.models.character import CharacterCard, CharacterSpan
from fabricatio_core import logger
from fabricatio_core.models.generic import Described, JSONList, Titled
from fabricatio_core.rust import detect_language
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.plan import WeightedPlan


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
                f" but got {len(boundaries)}; skipping",
            )
            continue
        for child, span in zip(children, parent_span.derive_child_spans(boundaries), strict=True):
            spans_accessor(child).append(span)
    logger.debug(f"Stitched {level} spans from boundary cards")


class CharacterSpans(JSONList[CharacterSpan]):
    """An ordered list of character spans, one per roster character."""


class ContextBase[P: WeightedPlan](
    Described,
    Titled,
    WordCount,
    PersistentAble,
    UpdateFrom[P],
    ABC,
):
    """Base class for hierarchical novel contexts shared across chapter, story and scene levels."""

    plan: P | None = None

    charactor_span: list[CharacterSpan] = Field(default_factory=list)
    language: str = Field("", exclude=True)
    """Written language; run-wide constant, set progressively during context creation."""

    outline: str = Field("", exclude=True)
    """The raw novel outline; run-wide constant, copied down every creation chain so each
    planning prompt grounds on the full source text instead of compressed parent descriptions."""

    writing_styles: list[str] = Field(default_factory=list)
    """Writing style directives accumulated down the tree: inherited guidance first, this
    element's own plan entry last; RAG reference texts join the same list when enabled.
    Never filled by ``update_from`` — the composing capability seeds it explicitly."""

    writing_constraints: list[str] = Field(default_factory=list)
    """The hard writing constraints binding this element alone. The parent's entries are never
    merged in — they are shown to this element's planner as the rules in force, and the prose
    prompt of a scene renders only the scene's own list. Empty when no constraint applies.
    Never filled by ``update_from`` — the composing capability seeds it explicitly."""

    cast: list[str] = Field(default_factory=list)
    """Names of the characters on stage in this element, proposed with its plan."""

    prefix_log: ContextLog = Field(default_factory=ContextLog, exclude=True)
    """Everything composed before this element as an append-only entry log; injected by the
    parent before composition."""

    @classmethod
    def create(
            cls, outline: str, *, language: str | None = None, title: str | None = None, description: str | None = None
    ) -> Self:
        """Build a context from the run-wide outline, detecting the language when none is given."""
        return cls(
            outline=outline,
            language=language or detect_language(outline),
            title=title or "",
            description=description or "",
        )

    def update_pre_check(self, other: P) -> Self:
        """Reject update sources that are not the expected weighted plan."""
        if not isinstance(other, WeightedPlan):
            raise TypeError(f"Expected a {type(self).__name__} plan, got {type(other).__name__}")
        return self

    def update_from_inner(self, other: P) -> Self:
        """Adopt the plan's scalar fields onto this context: title, description and cast.

        The style and constraint channels are deliberately left alone — they are
        seeded explicitly by the composing capability through
        ``set_writing_styles`` / ``set_writing_constraints``, which know whether
        the plan's entries augment or replace what the context already carries.
        """
        self.title = other.title
        self.description = other.description
        self.set_cast(other.cast)
        return self

    def set_language(self, language: str) -> Self:
        """Set the written language of this element and return self."""
        self.language = language
        return self

    def set_outline(self, outline: str) -> Self:
        """Set the raw novel outline carried into this element's planning prompts and return self."""
        self.outline = outline
        return self

    def set_writing_styles(self, writing_styles: list[str]) -> Self:
        """Replace this element's accumulated writing style entries and return self."""
        self.writing_styles = writing_styles
        return self

    def add_writing_styles(self, styles: list[str]) -> Self:
        """Append non-empty writing style entries and return self."""
        self.writing_styles.extend(style for style in styles if style)
        return self

    def set_writing_constraints(self, writing_constraints: list[str]) -> Self:
        """Replace this element's own writing constraints, the ones binding it alone, and return self."""
        self.writing_constraints = writing_constraints
        return self

    def set_cast(self, cast: list[str]) -> Self:
        """Set the on-stage character names of this element and return self."""
        self.cast = cast
        return self

    def set_prefix_log(self, prefix_log: ContextLog) -> Self:
        """Set the append-only log of everything composed before this element and return self."""
        self.prefix_log = prefix_log
        return self

    def set_charactor_spans(self, spans: list[CharacterSpan]) -> Self:
        """Replace this chapter's character spans and return self."""
        self.charactor_span = spans
        return self

    def add_charactor_span(self, span: CharacterSpan) -> Self:
        """Append one character span to this chapter and return self."""
        self.charactor_span.append(span)
        return self

    def dump_characters(self) -> list[str]:
        """Render each character's start and end states as one prompt entry, in span order."""
        return [s.dump_to_prompt() for s in self.charactor_span]

    def cast_missing_spans(self) -> list[str]:
        """Return cast members that have no character span on this context.

        A non-empty result means the proposed cast names characters the
        roster does not know, so the rendered character prompt cannot cover
        them; this is the check that the character parse into the model
        carries the proper cast.
        """
        covered = {span.start.name for span in self.charactor_span}
        return [name for name in self.cast if name not in covered]

    def prefixed_header_entry(self) -> ContextEntry | None:
        """This element's heading block as an entry seeded into every child's prefix.

        The chapter renders its heading, and only its title: the chapter
        description is a whole-chapter synopsis, so seeding it would leak the
        beats of later scenes into every descendant prompt. A RAG-sealed story
        renders its retrieved style references as one shared entry. The novel's,
        plain story's and scene's own titles are not part of the running text.
        """
        return None

    @abstractmethod
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """This element's blocks contributed to every following sibling's prefix.

        Only the chapter contributes its heading entry; stories forward their
        scenes' entries and scenes contribute their composed content.
        """
        ...

    def set_plan(self, plan: P) -> Self:
        """Set the novel's plan and return self."""
        self.plan = plan
        return self


class ParentContextBase[C: ContextBase, P: WeightedPlan](ContextBase[P], ABC):
    """Base for non-leaf contexts: a plan-typed channel that owns and iterates child contexts."""

    child_contexts: list[SerializeAsAny[C]] = Field(default_factory=list)

    def add_context(self, child_ctx: C) -> Self:
        """Append one child context and return self."""
        self.child_contexts.append(child_ctx)
        return self

    def iter_child_contexts(self) -> Generator[C, None, None]:
        """Yield this context's child contexts, in composition order; leaf contexts yield nothing."""
        yield from self.child_contexts

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
            logger.trace(seed.render())
            yield child
            seed = seed.with_entries(child.prefixed_entries())
