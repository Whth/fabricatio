"""This module contains the capabilities for the novel."""

from abc import ABC
from typing import List, Optional, Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import detect_language
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.novel import Chapter, Novel, NovelDraft
from fabricatio_novel.models.scripting import Script
from fabricatio_novel.rust import text_to_xhtml_paragraphs


class NovelCompose(CharacterCompose, Propose, UseLLM, ABC):
    """This class contains the capabilities for the novel."""

    async def compose_novel(
        self,
        outline: str,
        language: Optional[str] = None,
        chapter_guidance: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[Novel]],
    ) -> Novel | None:
        """Main novel composition pipeline."""
        logger.info(f"Starting novel generation for outline: {outline[:100]}...")
        okwargs = override_kwargs(kwargs, default=None)

        # Step 1: Generate draft
        logger.debug("Step 1: Generating novel draft from outline")
        draft = ok(await self.create_draft(outline, language, **okwargs))
        if not draft:
            logger.warn("Failed to generate novel draft.")
            return None
        logger.info(f"Draft generated successfully: '{draft.title}' in {draft.language}")

        # Step 2: Generate characters
        logger.debug("Step 2: Generating character cards from draft")
        characters: List[CharacterCard] = [
            c for c in ok(await self.create_characters(draft, **okwargs)) if c is not None
        ]
        logger.info(f"Generated {len(characters)} valid character(s)")

        # Step 3: Generate scripts
        logger.debug("Step 3: Generating chapter scripts using draft and characters")
        scripts = ok(await self.create_scripts(draft, characters, **okwargs))
        clean_scripts = [s for s in scripts if s is not None]
        if not clean_scripts:
            logger.warn("No valid scripts were generated from the draft and characters.")
            return None
        logger.info(f"Successfully generated {len(clean_scripts)} script(s) for chapters")

        # Step 4: Generate chapter contents
        logger.debug("Step 4: Generating full chapter contents from scripts")
        chapter_contents = await self.create_chapters(draft, clean_scripts, characters, chapter_guidance, **okwargs)
        if not chapter_contents:
            logger.warn("Chapter content generation returned no results.")
            return None
        logger.info(f"Generated {len(chapter_contents)} chapter content(s)")

        # Step 5: Assemble final novel
        logger.debug("Step 5: Assembling final novel from components")
        novel = self.assemble_novel(draft, clean_scripts, chapter_contents)
        logger.info(f"Novel assembly complete: '{novel.title}', {len(novel.chapters)} chapters")
        return novel

    async def create_draft(
        self, outline: str, language: Optional[str] = None, **kwargs: Unpack[ValidateKwargs[NovelDraft]]
    ) -> NovelDraft | None:
        """Generate a draft for the novel based on the provided outline."""
        logger.debug(f"Creating draft with outline: {outline[:200]}...")
        detected_language = language or detect_language(outline)
        logger.debug(f"Detected language: {detected_language}")

        prompt = TEMPLATE_MANAGER.render_template(
            novel_config.novel_draft_requirement_template,
            {"outline": outline, "language": detected_language},
        )
        logger.debug(f"Rendered draft prompt:\n{prompt}")

        result = await self.propose(NovelDraft, prompt, **kwargs)
        if result:
            logger.info(f"Draft created successfully: '{result.title}' ({result.expected_word_count} words)")
        else:
            logger.warn("Draft generation returned None.")
        return result

    async def create_characters(
        self, draft: NovelDraft, **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> None | List[CharacterCard] | List[CharacterCard | None]:
        """Generate characters based on draft."""
        logger.debug(f"Generating characters for novel: '{draft.title}'")
        if not draft.character_descriptions:
            logger.warn("No character descriptions found in draft.")
            return []

        character_prompts = [
            {
                "novel_title": draft.title,
                "synopsis": draft.synopsis,
                "character_desc": c,
                "language": draft.language,
            }
            for c in draft.character_descriptions
        ]
        logger.debug(f"Prepared {len(character_prompts)} character prompts")

        character_requirement = TEMPLATE_MANAGER.render_template(
            novel_config.character_requirement_template, character_prompts
        )
        logger.debug(f"Character requirement template rendered (length: {len(character_requirement)})")

        result = await self.compose_characters(character_requirement, **kwargs)
        valid_chars = [c for c in (ok(result) or []) if c is not None]
        logger.info(f"Generated {len(valid_chars)} valid character(s) out of {len(result or [])}")
        return result

    async def create_scripts(
        self, draft: NovelDraft, characters: List[CharacterCard], **kwargs: Unpack[ValidateKwargs[Script]]
    ) -> List[Script] | List[Script | None] | None:
        """Generate chapter scripts based on draft and characters."""
        logger.debug(f"Generating {len(draft.chapter_synopses)} chapter scripts for '{draft.title}'")
        if not characters:
            logger.warn("No characters provided for script generation.")
            return []
        if not draft.chapter_synopses:
            logger.warn("No chapter synopses in draft.")
            return []

        character_prompt = dump_card(*characters)
        logger.debug(f"Serialized {len(characters)} character(s) into prompt format")

        script_prompts = [
            {
                "novel_title": draft.title,
                "characters": character_prompt,
                "synopsis": s,
                "language": draft.language,
                "expected_word_count": c,
            }
            for (s, c) in zip(draft.chapter_synopses, draft.chapter_expected_word_counts, strict=False)
        ]
        logger.debug(f"Created {len(script_prompts)} script input prompts")

        script_requirement = TEMPLATE_MANAGER.render_template(novel_config.script_requirement_template, script_prompts)
        logger.debug(f"Script requirement template rendered (length: {len(script_requirement)})")

        result = await self.propose(Script, script_requirement, **kwargs)
        if result is None:
            logger.warn("Script proposal returned None.")
        else:
            valid_scripts = [s for s in result if s is not None]
            logger.info(f"Generated {len(valid_scripts)} valid script(s) out of {len(result)}")
        return result

    async def create_chapters(
        self,
        draft: NovelDraft,
        scripts: List[Script],
        characters: List[CharacterCard],
        guidance: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[str] | List[str | None]:
        """Generate actual chapter contents from scripts."""
        logger.debug(f"Generating chapter contents for {len(scripts)} script(s)")
        if not scripts:
            logger.warn("No scripts provided for chapter generation.")
            return []

        character_prompt = dump_card(*characters)
        logger.debug(f"Using {len(characters)} character(s) context for chapter generation")

        chapter_prompts = [
            {
                "script": s.as_prompt(),
                "characters": character_prompt,
                "language": draft.language,
                "guidance": guidance,
                "expected_word_count": s.expected_word_count,
            }
            for s in scripts
        ]
        logger.debug(f"Prepared {len(chapter_prompts)} chapter generation prompts")

        chapter_requirement: List[str] = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_requirement_template, chapter_prompts
        )
        logger.debug(f"Chapter requirement template length: {len(chapter_requirement)}")

        response = ok(await self.aask(chapter_requirement, **kwargs))

        logger.info(f"Generated {len(response)} chapter content(s)")
        return response

    @staticmethod
    def assemble_novel(draft: NovelDraft, scripts: List[Script], chapter_contents: List[str]) -> Novel:
        """Assemble the final novel from components."""
        logger.debug("Assembling final novel from draft, scripts, and chapter contents")
        if len(chapter_contents) != len(scripts):
            logger.warn(
                f"Mismatch between number of scripts ({len(scripts)}) and chapter contents ({len(chapter_contents)})"
            )

        chapters = []
        for i, (content, script) in enumerate(zip(chapter_contents, scripts, strict=False)):
            title = script.title or f"Chapter {i + 1}"
            cleaned_content = text_to_xhtml_paragraphs(content)
            chapters.append(Chapter(title=title, content=cleaned_content, expected_word_count=0))
        logger.info(f"Assembled {len(chapters)} chapter(s) into the final novel structure")

        novel = Novel(
            title=draft.title,
            chapters=chapters,
            synopsis=draft.synopsis,
            expected_word_count=draft.expected_word_count,
        )
        logger.debug(f"Final novel assembled: '{novel.title}', total chapters: {len(novel.chapters)}")
        return novel
