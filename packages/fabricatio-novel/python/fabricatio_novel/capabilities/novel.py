"""This module contains the capabilities for the novel."""

from abc import ABC
from typing import Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import override_kwargs

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.novel import Chapter, Novel, NovelDraft
from fabricatio_novel.models.scripting import Script


class NovelCompose(CharacterCompose, Propose, UseLLM, ABC):
    """This class contains the capabilities for the novel."""

    async def novel(self, outline: str, **kwargs: Unpack[ValidateKwargs[Novel]]) -> Novel | None:
        okwargs = override_kwargs(kwargs, default=None)

        draft = await self.propose(NovelDraft, outline, **okwargs)

        if draft is None:
            return None

        characters = await self.characters(
            TEMPLATE_MANAGER.render_template(
                novel_config.character_requirement_template,
                [
                    {"novel_title": draft.title, "synopsis": draft.synopsis, "character_desc": c}
                    for c in draft.character_desc
                ],
            ),
            **okwargs,
        )

        character_prompt = dump_card(*characters)

        scripts = await self.propose(
            Script,
            TEMPLATE_MANAGER.render_template(
                novel_config.script_requirement_template,
                [
                    {
                        "novel_title": draft.title,
                        "characters": character_prompt,
                        "synopsis": s,
                    }
                    for s in draft.chapter_synopses
                ],
            ),
        )

        if scripts is None:
            return None

        clean_scripts = [s for s in scripts if s is not None]

        chapter_contents = await self.aask(
            TEMPLATE_MANAGER.render_template(
                novel_config.chapter_requirement_template,
                [{"script": s.as_prompt(), "characters": character_prompt} for s in clean_scripts],
            )
        )
        return Novel(
            title=draft.title,
            chapters=[Chapter(title=s.title, content=c) for c,s in zip(chapter_contents, clean_scripts, strict=False)],
        )
