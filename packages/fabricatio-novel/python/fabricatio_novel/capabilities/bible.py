"""Setting bible capability: composing the series bible from the outline.

Design authority: docs/superpowers/specs/2026-08-08-novel-gen-overhaul-design.md §3,
simplified per user directive: characters are proposed as a list of plain
strings, one per character, as are background settings. Consumption into
scene prompts rides the seeded prefix entry, not this capability. The bible
is composed once and never updated: it is immutable for the whole run.
"""

from abc import ABC
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, detect_language

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.series_book import SeriesBible


class BibleCompose(SceneCompose[SceneContext], ABC):
    """Setting bible composition: the one bible per run, composed once from the outline."""

    async def compose_setting_bible(
        self,
        outline: str,
        language: str | None = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> SeriesBible | None:
        """Compose the full setting bible from the outline, per section."""
        logger.debug("Composing setting bible from outline")
        lang = language or detect_language(outline)
        characters = await self._compose_characters(outline, lang, send_to, **kwargs)
        if characters is None:
            return None
        background = await self._compose_background(outline, lang, send_to, **kwargs)
        if background is None:
            return None
        return SeriesBible(characters=characters, background_settings=background)

    async def _compose_characters(
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
        return await self.alist_v(requirement, str, send_to=send_to, **kwargs)

    async def _compose_background(
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
        return await self.alist_v(requirement, str, send_to=send_to, **kwargs)
