"""This module contains the capabilities for the novel."""

from abc import ABC
from typing import List, Optional, Tuple, Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import PLAN, SLOW, SMOL, TASK, detect_language
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.novel import Chapter, Novel
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import ChapterSummary, Script


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

        result = await self.generate_draft_and_characters(outline, language, **okwargs)
        if not result:
            return None
        draft, characters = result

        plans = await self.generate_plans(draft, characters, **okwargs)
        if not plans:
            return None

        chapter_contents = await self.create_chapters(draft, plans, characters, chapter_guidance, **okwargs)
        if not chapter_contents:
            logger.warn("Chapter content generation returned no results.")
            return None
        logger.info(f"Generated {len(chapter_contents)} chapter content(s)")

        novel = self.assemble_novel(draft, plans, chapter_contents, characters)
        logger.info(f"Novel assembly complete: '{novel.title}', {len(novel.chapters)} chapters")
        return novel

    async def generate_draft_and_characters(
        self, outline: str, language: Optional[str] = None, **kwargs: Unpack[ValidateKwargs[NovelDraft]]
    ) -> Optional[Tuple[NovelDraft, List[CharacterCard]]]:
        """Steps 1-2: generate draft and characters."""
        logger.debug("Step 1: Generating novel draft from outline")
        draft = ok(await self.create_draft(outline, language, **kwargs))
        if not draft:
            logger.warn("Failed to generate novel draft.")
            return None
        logger.info(f"Draft generated successfully: '{draft.title}' in {draft.language}")

        logger.debug("Step 2: Generating character cards from draft")
        characters: List[CharacterCard] = [
            c for c in ok(await self.create_characters(draft, **kwargs)) if c is not None
        ]
        logger.info(f"Generated {len(characters)} valid character(s)")
        return draft, characters

    async def generate_plans(
        self, draft: NovelDraft, characters: List[CharacterCard], **kwargs: Unpack[ValidateKwargs[Script]]
    ) -> Optional[List[ChapterPlan]]:
        """Step 3: generate scripts and chapter plans."""
        logger.debug("Step 3: Generating chapter scripts using draft and characters")
        scripts = ok(await self.create_scripts(draft, characters, **kwargs))
        chapter_plans = ChapterPlan.from_draft(draft, scripts)
        if not chapter_plans:
            logger.warn("No valid scripts were generated from the draft and characters.")
            return None
        logger.info(f"Successfully generated {len(chapter_plans)} script(s) for chapters")
        return chapter_plans

    async def create_draft(
        self,
        outline: str,
        language: Optional[str] = None,
        send_to: str | None = PLAN,
        **kwargs: Unpack[ValidateKwargs[NovelDraft]],
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

        result = await self.propose(NovelDraft, prompt, send_to=send_to, **kwargs)
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
        self,
        draft: NovelDraft,
        characters: List[CharacterCard],
        send_to: str | None = SLOW,
        **kwargs: Unpack[ValidateKwargs[Script]],
    ) -> List[Script] | List[Script | None] | None:
        """Generate chapter scripts based on draft and characters."""
        logger.debug(f"Generating {len(draft.chapters)} chapter scripts for '{draft.title}'")
        if not characters:
            logger.warn("No characters provided for script generation.")
            return []
        if not draft.chapters:
            logger.warn("No chapter synopses in draft.")
            return []

        character_prompt = dump_card(*characters)
        logger.debug(f"Serialized {len(characters)} character(s) into prompt format")

        script_prompts = [
            {
                "novel_title": draft.title,
                "characters": character_prompt,
                "synopsis": c.synopsis,
                "language": draft.language,
                "expected_word_count": wc,
                "chapter_title": ct,
                "all_chapters_titles": draft.all_chapters_titles,
            }
            for ct, wc, c in draft.iter_ft_chap()
        ]
        logger.debug(f"Created {len(script_prompts)} script input prompts")

        script_requirement = TEMPLATE_MANAGER.render_template(novel_config.script_requirement_template, script_prompts)
        logger.debug(f"Script requirement template rendered (length: {len(script_requirement)})")

        return await self.propose(Script, script_requirement, send_to=send_to, **kwargs)

    async def create_chapters(
        self,
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        characters: List[CharacterCard],
        guidance: Optional[str] = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[str]:
        """Generate chapters sequentially with rolling summary context.

        Each chapter is generated one at a time. After each chapter, a structured
        summary is produced and passed to the next chapter's prompt to maintain
        narrative continuity across the entire novel.
        """
        logger.debug(f"Generating chapter contents sequentially for {len(chapter_plans)} script(s)")
        if not chapter_plans:
            logger.warn("No scripts provided for chapter generation.")
            return []

        character_prompt = dump_card(*characters)
        logger.debug(f"Using {len(characters)} character(s) context for chapter generation")

        chapter_contents: List[str] = []
        previous_summary: Optional[ChapterSummary] = None

        for i, cp in enumerate(chapter_plans):
            logger.debug(f"Generating chapter {i + 1}/{len(chapter_plans)}: {cp.formatted_chapter_title}")

            # 1. Build prompt context with cross-chapter information
            prompt_ctx = {
                "script": cp.script.as_prompt(),
                "characters": character_prompt,
                "language": draft.language,
                "guidance": guidance,
                "writing_constrain": cp.draft.writing_constrain,
                "expected_word_count": cp.expected_word_count,
                "chapter_title": cp.formatted_chapter_title,
                "novel_title": draft.title,
                "novel_synopsis": draft.synopsis,
                "all_chapters_titles": draft.all_chapters_titles,
                "previous_summary": previous_summary.as_prompt() if previous_summary else None,
            }
            rendered = TEMPLATE_MANAGER.render_template(novel_config.chapter_requirement_template, [prompt_ctx])

            # 2. Generate chapter content
            raw_chapter = ok(await self.aask(rendered, send_to=send_to, **kwargs))
            if not raw_chapter:
                logger.warn(f"Failed to generate content for {cp.formatted_chapter_title}")
                chapter_contents.append("")
                continue

            raw_text = raw_chapter[0]
            chapter_contents.append(raw_text)
            logger.info(f"Chapter {i + 1}/{len(chapter_plans)} generated ({len(raw_text)} chars)")

            # 3. Summarize chapter for next iteration's context
            previous_summary = await self.summarize_chapter(
                cp.formatted_chapter_title, raw_text, draft.language, previous_summary, **kwargs
            )
            if previous_summary:
                logger.debug(
                    f"Chapter {i + 1} summarized: {len(previous_summary.key_events)} events, "
                    f"{len(previous_summary.unresolved_threads)} open threads"
                )

        logger.info(f"Generated {len(chapter_contents)} chapter content(s) sequentially")
        return chapter_contents

    async def summarize_chapter(
        self,
        chapter_title: str,
        chapter_content: str,
        language: str,
        previous_summary: Optional["ChapterSummary"] = None,
        send_to: str | None = SMOL,
        **kwargs: Unpack[ValidateKwargs[ChapterSummary]],
    ) -> Optional["ChapterSummary"]:
        """Generate a structured summary of a chapter for cross-chapter context tracking.

        Args:
            chapter_title: The formatted title of the chapter.
            chapter_content: The raw text content of the generated chapter.
            language: The language of the novel.
            previous_summary: The previous chapter's summary, used as starting-state reference.
                For the first chapter this is None.
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            A ChapterSummary if successful, None otherwise.
        """
        prompt = TEMPLATE_MANAGER.render_template(
            novel_config.chapter_summarization_template,
            {
                "chapter_title": chapter_title,
                "chapter_content": chapter_content,
                "language": language,
                "previous_summary": previous_summary.as_prompt() if previous_summary else None,
            },
        )
        return await self.propose(ChapterSummary, prompt, send_to=send_to, **kwargs)

    @staticmethod
    def assemble_novel(
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        chapter_contents: List[str],
        characters: Optional[List[CharacterCard]] = None,
    ) -> Novel:
        """Assemble the final novel from components."""
        logger.debug("Assembling final novel from draft, scripts, and chapter contents")
        if len(chapter_contents) != len(chapter_plans):
            logger.warn(
                f"Mismatch between number of scripts ({len(chapter_plans)}) and chapter contents ({len(chapter_contents)})"
            )

        chapters = [
            Chapter.from_plan_and_raw_content(cp, content)
            for content, cp in zip(chapter_contents, chapter_plans, strict=True)
        ]
        logger.info(f"Assembled {len(chapters)} chapter(s) into the final novel structure")

        novel = Novel(
            title=draft.title,
            chapters=chapters,
            synopsis=draft.synopsis,
            expected_word_count=draft.expected_word_count,
            characters=characters,
        )
        logger.debug(f"Final novel assembled: '{novel.title}', total chapters: {len(novel.chapters)}")
        return novel
