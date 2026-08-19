"""Setting bible models: the novel's settings facts.

Design authority: docs/superpowers/specs/2026-08-08-novel-gen-overhaul-design.md §3,
simplified per user directive (2026-08-09): plain strings, no structured entries.
Characters are one prompt-ready string; every non-character fact is one plain
string in ``background_settings``.
"""

from typing import Any, ClassVar, Dict, List

from fabricatio_capabilities.models.generic import AsPrompt, FinalizedDumpAble, PersistentAble
from pydantic import Field

from fabricatio_novel.config import novel_config


class SeriesBible(FinalizedDumpAble, AsPrompt, PersistentAble):
    """The setting bible: the novel's settings facts."""

    rendering_template: ClassVar[str] = novel_config.setting_bible_context_template
    """Template used to render the bible into prompts via :meth:`as_prompt`."""

    characters: str = ""
    """The canonical character roster as a single prompt-ready string."""

    background_settings: List[str] = Field(default_factory=list)
    """All non-character settings facts (premise, tone, world rules, factions, terminology, foreshadowing), one plain string per fact."""

    def _as_prompt_inner(self) -> Dict[str, str] | Dict[str, Any] | Any:
        """Return the bible sections for the prompt template."""
        return self.model_dump()

    def is_empty(self) -> bool:
        """Return True when neither section carries content (fresh default bible)."""
        return not self.characters and not self.background_settings
