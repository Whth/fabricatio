"""Branch-based append-only context for prefix-stable prompt assembly.

A :class:`ContextLog` is an append-only sequence of frozen :class:`ContextEntry`
blocks. Entries live in an immutable tuple, so logs share their history safely:
``branch`` copies in O(1) and both sides append independently afterwards.

The intended use is prompt prefix management: stable boilerplate enters the log
first (the *head*), per-request content branches off it, and ``render`` joins
bodies deterministically — identical logs always render byte-identical text,
which keeps provider prefix caches warm.
"""

from collections.abc import Iterable
from typing import Self

from pydantic import BaseModel, ConfigDict


class ContextEntry(BaseModel):
    """One immutable block of composed prompt context."""

    model_config = ConfigDict(frozen=True)

    kind: str
    """What composed this block; free-form so packages can define their own vocabularies."""

    title: str
    """The owning element's title."""

    body: str
    """The rendered text block."""


class ContextLog(BaseModel):
    """An append-only sequence of entries with fork and clear support.

    Entries are frozen and held in an immutable tuple, so logs share their
    history safely: :meth:`branch` copies in O(1) and both sides append
    independently afterwards. Pipeline code appends purely via
    :meth:`with_entry` and :meth:`with_entries`; the mutating
    :meth:`append` is reserved for single-owner code, since rebinding the
    tuple never disturbs other holders.
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
        """Join non-empty bodies with blank lines; identical logs render identical bytes."""
        return "\n\n".join(entry.body for entry in self.entries if entry.body)


__all__ = ["ContextEntry", "ContextLog"]
