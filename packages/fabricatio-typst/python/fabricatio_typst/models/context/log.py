"""Append-only article context: frozen entries and forkable logs.

The generic machinery lives in :mod:`fabricatio_context`; this module narrows it to
the article-tooling vocabulary and re-exports the typst-facing names.
"""

from enum import StrEnum, auto
from typing import Self

from fabricatio_context.models.context import ContextEntry as BaseContextEntry
from fabricatio_context.models.context import ContextLog as BaseContextLog


class EntryKind(StrEnum):
    """What composed one context block: the closed vocabulary of a prefix log.

    Every entry the pipeline seeds draws its kind from here, so the blocks a prompt
    walks — the article outline, the chapter and section headings, the composed
    subsection prose — are named once instead of being spelled out at each site. The
    ``is_*`` methods read a kind at the call site without repeating the comparison
    against a member.
    """

    ARTICLE_OUTLINE = auto()
    """The article outline, rendered once at the root and inherited by every descendant."""

    CHAPTER_HEADER = auto()
    """A chapter's heading, seeded into every descendant of that chapter."""

    SECTION_HEADER = auto()
    """A section's heading, seeded into every descendant of that section."""

    SUBSECTION_CONTENT = auto()
    """A subsection's composed prose; each following subsection inherits it through its prefix."""

    def is_article_outline(self) -> bool:
        """Whether the block is the seeded article outline."""
        return self is EntryKind.ARTICLE_OUTLINE

    def is_chapter_header(self) -> bool:
        """Whether the block is a chapter's heading."""
        return self is EntryKind.CHAPTER_HEADER

    def is_section_header(self) -> bool:
        """Whether the block is a section's heading."""
        return self is EntryKind.SECTION_HEADER

    def is_subsection_content(self) -> bool:
        """Whether the block is a subsection's composed prose."""
        return self is EntryKind.SUBSECTION_CONTENT


class ContextEntry(BaseContextEntry):
    """One immutable block of composed article text, kinded by the article vocabulary."""

    kind: EntryKind
    """What composed this block; a kind outside the vocabulary is a pipeline bug, not data."""


class ContextLog(BaseContextLog):
    """An append-only sequence of entries with fork and clear support.

    Entries are frozen and held in an immutable tuple, so logs share their history
    safely: `branch` copies in O(1) and both sides append independently afterwards.
    Pipeline code appends purely via `with_entry` and `with_entries`; the mutating
    `append` is reserved for single-owner code, since rebinding the tuple never
    disturbs other holders.
    """

    entries: tuple[ContextEntry, ...] = ()
    """The accumulated blocks, in composition order."""

    def append(self, entry: ContextEntry) -> Self:
        """Append one entry in place and return self; single-owner code only."""
        self.entries = (*self.entries, entry)
        return self


__all__ = ["ContextEntry", "ContextLog", "EntryKind"]
