"""This module contains the capabilities for the novel."""

from abc import ABC
from typing import List, Optional, Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import GenerateKwargs, ValidateKwargs
from fabricatio_core.rust import detect_language
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.novel import Chapter, Novel, NovelDraft
from fabricatio_novel.models.scripting import Script
from fabricatio_novel.rust import text_to_xhtml_paragraphs


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
        chapter_contents = await self.create_chapters(draft, clean_scripts, characters, **okwargs)

        # Step 5: Assemble final novel
        return self.assemble_novel(draft, clean_scripts, chapter_contents)

    async def create_draft(
        self, outline: str, language: Optional[str] = None, **kwargs: Unpack[ValidateKwargs[NovelDraft]]
    ) -> NovelDraft | None:
        """Generate a draft for the novel based on the provided outline.

        Args:
            outline (str): The outline of the novel.
            language (Optional[str]): The language of the novel. If not provided, it will be detected from the outline.
            **kwargs: Additional keyword arguments for validation.

        Returns:
            NovelDraft | None: The generated novel draft or None if generation fails.
        """
        return await self.propose(
            NovelDraft,
            TEMPLATE_MANAGER.render_template(
                novel_config.novel_draft_requirement_template,
                {"outline": outline, "language": language or detect_language(outline)},
            ),
            **kwargs,
        )

    async def create_characters(
        self, draft: NovelDraft, **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> None | List[CharacterCard] | List[CharacterCard | None]:
        """Generate characters based on draft."""
        character_prompts = [
            {"novel_title": draft.title, "synopsis": draft.synopsis, "character_desc": c, "language": draft.language}
            for c in draft.character_desc
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
            {"novel_title": draft.title, "characters": character_prompt, "synopsis": s, "language": draft.language}
            for s in draft.chapter_synopses
        ]

        script_requirement = TEMPLATE_MANAGER.render_template(novel_config.script_requirement_template, script_prompts)

        return await self.propose(Script, script_requirement, **kwargs)

    async def create_chapters(
        self,
        draft: NovelDraft,
        scripts: List[Script],
        characters: List[CharacterCard],
        **kwargs: Unpack[GenerateKwargs],
    ) -> List[str]:
        """Generate actual chapter contents from scripts."""
        character_prompt = dump_card(*characters)

        chapter_prompts = [
            {"script": s.as_prompt(), "characters": character_prompt, "language": draft.language} for s in scripts
        ]

        chapter_requirement = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_requirement_template, chapter_prompts
        )

        return await self.aask(chapter_requirement, **kwargs)

    @staticmethod
    def assemble_novel(draft: NovelDraft, scripts: List[Script], chapter_contents: List[str]) -> Novel:
        """Assemble the final novel from components."""
        chapters = [
            Chapter(title=script.title, content=text_to_xhtml_paragraphs(content), expected_word_count=0)
            for content, script in zip(chapter_contents, scripts, strict=False)
        ]

        return Novel(
            title=draft.title,
            chapters=chapters,
            synopsis=draft.synopsis,
            expected_word_count=draft.expected_word_count,
        )
