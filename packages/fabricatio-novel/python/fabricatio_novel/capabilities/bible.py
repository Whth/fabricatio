"""Setting bible capabilities: creation and update of the series bible.

Design authority: docs/superpowers/specs/2026-08-08-novel-gen-overhaul-design.md §3,
simplified per user directive: characters are proposed as a list of plain
strings, one per character, as are background settings. Consumption into
scene prompts rides the seeded prefix entry, not this capability.
"""

from abc import ABC
from typing import Iterable, Optional, Unpack, cast

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, detect_language

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.series_book import SeriesBible

_SECTIONS = ("characters", "background")


def parse_sections(sections: str | Iterable[str] | None) -> Optional[set[str]]:
    """Normalize a ``--sections`` option into a set of section names; None means all."""
    if sections is None:
        return None
    names = [s.strip() for s in sections.split(",") if s.strip()] if isinstance(sections, str) else list(sections)
    if not names or set(names) == {"all"}:
        return None
    invalid = [n for n in names if n not in _SECTIONS]
    if invalid:
        raise ValueError(f"Unknown bible section(s): {invalid}; expected one of {_SECTIONS}")
    return set(names)


class BibleCompose(SceneCompose, ABC):
    """Setting bible creation and update."""

    # --- creation / update (design §3.3) ---

    async def create_setting_bible(
        self,
        outline: str,
        language: str | None = None,
        send_to: str | None = TASK,
        sections: str | Iterable[str] | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> SeriesBible | None:
        """Propose a skeleton-first setting bible from the outline, per section."""
        logger.debug("Creating setting bible from outline")
        lang = language or detect_language(outline)
        names = parse_sections(sections)

        characters: list[str] = []
        if names is None or "characters" in names:
            proposed_characters = await self._propose_characters(outline, lang, send_to, **kwargs)
            if proposed_characters is None:
                return None
            characters = proposed_characters

        background: list[str] = []
        if names is None or "background" in names:
            proposed_background = await self._propose_background(outline, lang, send_to, **kwargs)
            if proposed_background is None:
                return None
            background = proposed_background

        return SeriesBible(characters=characters, background_settings=background)

    async def update_setting_bible(
        self,
        bible: SeriesBible,
        outline: str,
        language: str | None = None,
        send_to: str | None = TASK,
        sections: str | Iterable[str] | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> SeriesBible | None:
        """Re-propose the given sections from the outline, keeping the others."""
        logger.debug("Updating setting bible")
        lang = language or detect_language(outline)
        names = parse_sections(sections)

        characters = bible.characters
        if names is None or "characters" in names:
            new_characters = await self._propose_characters(outline, lang, send_to, **kwargs)
            if new_characters is None:
                return None
            characters = new_characters

        background = bible.background_settings
        if names is None or "background" in names:
            new_background = await self._propose_background(outline, lang, send_to, **kwargs)
            if new_background is None:
                return None
            background = new_background

        return bible.model_copy(update={"characters": characters, "background_settings": background})

    async def _propose_characters(
        self,
        outline: str,
        language: str,
        send_to: str | None,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[str] | None:
        """Propose the character roster as one string per character."""
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.setting_bible_characters_template,
            {"outline": outline, "language": language},
        )
        return cast(
            "list[str] | None",
            await self.alist_v(requirement, str, send_to=send_to, **kwargs),
        )

    async def _propose_background(
        self,
        outline: str,
        language: str,
        send_to: str | None,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[str] | None:
        """Propose the background settings as a list of plain strings."""
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.setting_bible_background_template,
            {"outline": outline, "language": language},
        )
        return cast(
            "list[str] | None",
            await self.alist_v(requirement, str, send_to=send_to, **kwargs),
        )
