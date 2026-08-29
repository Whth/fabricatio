"""Append-only manuscript context: frozen entries and forkable logs.

The generic machinery lives in :mod:`fabricatio_context`; this module narrows it
to the manuscript vocabulary and re-exports the novel-facing names.
"""

from typing import Literal, Self

from fabricatio_context.models.context import ContextEntry as BaseContextEntry
from fabricatio_context.models.context import ContextLog as BaseContextLog


class ContextEntry(BaseContextEntry):
    """One immutable block of composed manuscript."""

    kind: Literal["chapter_header", "scene_content", "setting_bible"]
    """What composed this block: a chapter's heading, a scene's prose, or the seeded setting bible."""


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


__all__ = ["ContextEntry", "ContextLog"]
