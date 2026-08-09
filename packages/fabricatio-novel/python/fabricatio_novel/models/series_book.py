"""Setting bible (设定集) models: the novel's settings facts.

Design authority: docs/superpowers/specs/2026-08-08-novel-gen-overhaul-design.md §3,
simplified per user directive (2026-08-09): plain strings, no structured entries.
Characters are one prompt-ready string; every non-character fact is one plain
string in ``background_settings``.
"""

from typing import List

from fabricatio_capabilities.models.generic import FinalizedDumpAble, PersistentAble
from pydantic import Field


class SeriesBible(FinalizedDumpAble, PersistentAble):
    """The setting bible (设定集): the novel's settings facts.

    Created skeleton-first from the outline (``fanvl bible create``), persists as
    BLAKE3-hashed JSON checkpoints (:class:`PersistentAble`) and exports to
    markdown. Consumed by scene generation via :mod:`fabricatio_novel.capabilities.bible`.
    """

    characters: str = ""
    """The canonical character roster as a single prompt-ready string."""

    background_settings: List[str] = Field(default_factory=list)
    """All non-character settings facts (premise, tone, world rules, factions, terminology, foreshadowing), one plain string per fact."""

    def is_empty(self) -> bool:
        """Return True when neither section carries content (fresh default bible)."""
        return not self.characters and not self.background_settings
