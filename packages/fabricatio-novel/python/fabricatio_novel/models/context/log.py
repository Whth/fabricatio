"""Append-only manuscript context: frozen entries and forkable logs."""

from collections.abc import Iterable
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict


class ContextEntry(BaseModel):
    """One immutable block of composed manuscript."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["chapter_header", "scene_content", "setting_bible"]
    """What composed this block: a chapter's heading, a scene's prose, or the seeded setting bible."""

    title: str
    """The owning element's title."""

    body: str
    """The rendered text block."""


class ContextLog(BaseModel):
    """An append-only sequence of entries with fork and clear support.

    Entries are frozen and held in an immutable tuple, so logs share their
    history safely: `branch` copies in O(1) and both sides append
    independently afterwards. Pipeline code appends purely via `with_entry`
    and `with_entries`; the mutating `append` is reserved for single-owner
    code, since rebinding the tuple never disturbs other holders.
    """

    entries: tuple[ContextEntry, ...] = ()
    """The accumulated blocks, in composition order."""

    forked_at: int = 0
    """Length of the branched-from history at branch time; snapshot traceability only."""

    def with_entry(self, entry: ContextEntry) -> "ContextLog":
        """Return a new log with one entry appended; this log is unchanged."""
        return ContextLog(entries=(*self.entries, entry), forked_at=self.forked_at)

    def with_entries(self, entries: Iterable[ContextEntry]) -> "ContextLog":
        """Return a new log with every entry appended in sequence; this log is unchanged."""
        return ContextLog(entries=(*self.entries, *entries), forked_at=self.forked_at)

    def append(self, entry: ContextEntry) -> Self:
        """Append one entry in place and return self; single-owner code only."""
        self.entries = (*self.entries, entry)
        return self

    def branch(self) -> "ContextLog":
        """Return a fork sharing this history; both sides append independently."""
        return ContextLog(entries=self.entries, forked_at=len(self.entries))

    def clear(self) -> "ContextLog":
        """Return a fresh empty log; this log keeps its history intact."""
        return ContextLog()

    def render(self) -> str:
        """Join non-empty bodies with blank lines, matching the legacy prefix joins."""
        return "\n\n".join(entry.body for entry in self.entries if entry.body)
