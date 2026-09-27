"""Setting bible models: the novel's settings facts.

Design authority: docs/superpowers/specs/2026-08-08-novel-gen-overhaul-design.md §3,
simplified per user directive (2026-08-09): plain strings, no structured entries.
Characters and background settings are both one plain string per entry.
"""

from typing import Any, ClassVar

from fabricatio_capabilities.models.generic import AsPrompt, FinalizedDumpAble, PersistentAble
from pydantic import Field

from fabricatio_novel.config import novel_config


class SeriesBible(FinalizedDumpAble, AsPrompt, PersistentAble):
    """The setting bible: the novel's settings facts."""

    rendering_template: ClassVar[str] = novel_config.setting_bible_context_template
    """Template used to render the bible into prompts via :meth:`as_prompt`."""

    characters: list[str] = Field(default_factory=list)
    """The canonical character roster, one entry per character."""

    background_settings: list[str] = Field(default_factory=list)
    """All non-character settings facts (premise, tone, world rules, factions, terminology, foreshadowing), one plain string per fact."""

    def _as_prompt_inner(self) -> dict[str, str] | dict[str, Any] | Any:
        """Return the bible sections for the prompt template."""
        return self.model_dump()

    def is_empty(self) -> bool:
        """Return True when neither section carries content (fresh default bible)."""
        return not self.characters and not self.background_settings
