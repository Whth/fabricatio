"""This module contains the capabilities for the novel."""

from abc import ABC
from typing import List, Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.novel import Chapter, Novel, NovelDraft
from fabricatio_novel.models.scripting import Script


class NovelCompose(CharacterCompose, Propose, UseLLM, ABC):
    """This class contains the capabilities for the novel."""

    async def novel(self, outline: str, **kwargs: Unpack[ValidateKwargs[Novel]]) -> Novel | None:
        """Main novel composition pipeline."""
        okwargs = override_kwargs(kwargs, default=None)

        # Step 1: Generate draft
        draft = ok(await self.create_draft(outline, **okwargs))

        # Step 2: Generate characters
        characters: List[CharacterCard] = [
            c for c in ok(await self.create_characters(draft, **okwargs)) if c is not None
        ]

        # Step 3: Generate scripts
        scripts = ok(await self.create_scripts(draft, characters, **okwargs))

        clean_scripts = [s for s in scripts if s is not None]

        # Step 4: Generate chapter contents
        chapter_contents = await self.create_chapters(clean_scripts, characters)

        # Step 5: Assemble final novel
        return self.assemble_novel(draft, clean_scripts, chapter_contents)

    async def create_draft(self, outline: str, **kwargs: Unpack[ValidateKwargs[NovelDraft]]) -> NovelDraft | None:
        """Create initial novel draft from outline."""
        return await self.propose(NovelDraft, outline, **kwargs)

    async def create_characters(
        self, draft: NovelDraft, **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> None | List[CharacterCard] | List[CharacterCard | None]:
        """Generate characters based on draft."""
        character_prompts = [
            {"novel_title": draft.title, "synopsis": draft.synopsis, "character_desc": c} for c in draft.character_desc
        ]

        character_requirement = TEMPLATE_MANAGER.render_template(
            novel_config.character_requirement_template, character_prompts
        )

        return await self.characters(character_requirement, **kwargs)

    async def create_scripts(
        self, draft: NovelDraft, characters: List[CharacterCard], **kwargs: Unpack[ValidateKwargs[Script]]
    ) -> List[Script] | List[Script | None] | None:
        """Generate chapter scripts based on draft and characters."""
        character_prompt = dump_card(*characters)

        script_prompts = [
            {
                "novel_title": draft.title,
                "characters": character_prompt,
                "synopsis": s,
            }
            for s in draft.chapter_synopses
        ]

        script_requirement = TEMPLATE_MANAGER.render_template(novel_config.script_requirement_template, script_prompts)

        return await self.propose(Script, script_requirement, **kwargs)

    async def create_chapters(self, scripts: List[Script], characters: List[CharacterCard]) -> List[str]:
        """Generate actual chapter contents from scripts."""
        character_prompt = dump_card(*characters)

        chapter_prompts = [{"script": s.as_prompt(), "characters": character_prompt} for s in scripts]

        chapter_requirement = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_requirement_template, chapter_prompts
        )

        return await self.aask(chapter_requirement)

    @staticmethod
    def assemble_novel(draft: NovelDraft, scripts: List[Script], chapter_contents: List[str]) -> Novel:
        """Assemble the final novel from components."""
        chapters = [
            Chapter(title=script.title, content=content)
            for content, script in zip(chapter_contents, scripts, strict=False)
        ]

        return Novel(title=draft.title, chapters=chapters)
