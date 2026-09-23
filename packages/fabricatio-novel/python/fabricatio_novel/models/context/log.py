"""Append-only manuscript context: frozen entries and forkable logs.

The generic machinery lives in :mod:`fabricatio_context`; this module narrows it
to the manuscript vocabulary and re-exports the novel-facing names.
"""

from enum import StrEnum, auto
from typing import Self

from fabricatio_context.models.context import ContextEntry as BaseContextEntry
from fabricatio_context.models.context import ContextLog as BaseContextLog


class EntryKind(StrEnum):
    """What composed one manuscript block: the closed vocabulary of a prefix log.

    Every entry the pipeline seeds draws its kind from here, so the blocks a
    prompt walks — headings, composed prose, the seeded bible, retrieved style
    references — are named once instead of being spelled out at each site. The
    ``is_*`` methods read a kind at the call site without repeating the
    comparison against a member.
    """

    CHAPTER_HEADER = auto()
    """A chapter's heading, seeded into every descendant of that chapter."""

    SCENE_CONTENT = auto()
    """A scene's composed prose; each following scene inherits it through its prefix."""

    SETTING_BIBLE = auto()
    """The setting bible, rendered once at the novel root and inherited by every descendant."""

    STYLE_REFERENCES = auto()
    """Writing style references retrieved for one RAG-bound level."""

    def is_chapter_header(self) -> bool:
        """Whether the block is a chapter's heading."""
        return self is EntryKind.CHAPTER_HEADER

    def is_scene_content(self) -> bool:
        """Whether the block is a scene's composed prose."""
        return self is EntryKind.SCENE_CONTENT

    def is_setting_bible(self) -> bool:
        """Whether the block is the seeded setting bible."""
        return self is EntryKind.SETTING_BIBLE

    def is_style_references(self) -> bool:
        """Whether the block holds one level's retrieved style references."""
        return self is EntryKind.STYLE_REFERENCES


class ContextEntry(BaseContextEntry):
    """One immutable block of composed manuscript, kinded by the manuscript vocabulary."""

    kind: EntryKind
    """What composed this block; a kind outside the vocabulary is a pipeline bug, not data."""


class ContextLog(BaseContextLog):
    """An append-only sequence of entries with fork and clear support.

    Entries are frozen and held in an immutable tuple, so logs share their
    history safely: `branch` copies in O(1) and both sides append
    independently afterwards. Pipeline code appends purely via `with_entry`
    and `with_entries`; the mutating `append` is reserved for single-owner
    code, since rebinding the tuple never disturbs other holders.
    """

    entries: tuple[ContextEntry, ...] = ()
    """The accumulated blocks, in composition order."""

    def append(self, entry: ContextEntry) -> Self:
        """Append one entry in place and return self; single-owner code only."""
        self.entries = (*self.entries, entry)
        return self


__all__ = ["ContextEntry", "ContextLog", "EntryKind"]
