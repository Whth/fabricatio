"""Novel composition capabilities — the NovelCompose base class."""

from abc import ABC
from typing import Any, Dict, List, Optional, Tuple, Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCard
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import PLAN, SLOW, SMOL, TASK, detect_language
from fabricatio_core.utils import no_default, ok

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter_context import ChapterContext
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
        okwargs = no_default(kwargs)

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
        **kwargs: Unpack[ValidateKwargs[NovelDraft | None]],
    ) -> NovelDraft:
        """Generate a draft for the novel based on the provided outline."""
        logger.debug(f"Creating draft with outline: {outline[:200]}...")
        detected_language = language or detect_language(outline)
        logger.debug(f"Detected language: {detected_language}")

        prompt = await self.prepare_draft_prompt(detected_language, outline)

        result = ok(await self.propose(NovelDraft, prompt, send_to=send_to, **kwargs))
        logger.info(f"Draft created successfully: '{result.title}' ({result.expected_word_count} words)")
        return await self.post_draft_gen(result)

    async def prepare_draft_prompt(self, detected_language: str, outline: str) -> str:
        """Build and render the draft prompt from the outline.

        Subclasses override to replace the template, inject extra context, or
        call out to external services before the draft is proposed.
        """
        prompt: str = TEMPLATE_MANAGER.render_template(
            novel_config.novel_draft_requirement_template,
            {"outline": outline, "language": detected_language},
        )
        logger.debug(f"Rendered draft prompt:\n{prompt}")
        return prompt

    async def post_draft_gen(self, novel_draft: NovelDraft) -> NovelDraft:
        """Post-process the generated draft before it is returned.

        Subclasses override to mutate or replace the draft (e.g. inject
        metadata, adjust titles). Default is a no-op passthrough.
        """
        return novel_draft

    async def create_characters(
        self, draft: NovelDraft, **kwargs: Unpack[ValidateKwargs[CharacterCard]]
    ) -> List[CharacterCard] | List[CharacterCard | None] | None:
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
        *,
        context: Optional[ChapterContext] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[str]:
        """Generate chapters sequentially with rolling context.

        Each chapter is generated one at a time. After each chapter, a structured
        summary is produced and passed to the next chapter's prompt alongside the
        last paragraph of the prior chapter (``previous_chapter_tail``, default-on
        when non-empty) — the structured summary alone is too lossy to anchor
        the next chapter's opening beat, so we also hand the writer the closing
        paragraph of what came before.

        ``context`` is the sealed per-chapter channel: the loop sets its inputs
        once per run via chainable setters (``set_draft`` / ``set_chapter_plans``
        / ``set_characters`` / ``set_guidance``) and accumulates every chapter
        via ``add_summary`` / ``add_content`` as self-describing ``(index, item)``
        tuples in ``chapter_summaries`` / ``chapter_contents`` — hooks see ALL
        chapters, past, present and planned. The current position is
        ``len(context.chapter_contents)`` (one tuple per completed chapter);
        per-chapter views (``chapter_plan()``, ``previous_summary()``,
        ``previous_chapter_tail()``, ``current_summary()``) are plain methods
        accepting a chapter index (default -1), not stored fields, so no field
        duplicates another. Mixins may subclass the channel to carry their own
        cross-hook state (default ``None`` → a base ``ChapterContext`` is
        created for the run). The capability itself stays stateless — all
        per-run state lives in the caller-owned context. The returned list is
        ``context.contents()`` — the unpacked chapter contents, in order.
        """
        logger.debug(f"Generating chapter contents sequentially for {len(chapter_plans)} script(s)")
        if not chapter_plans:
            logger.warn("No scripts provided for chapter generation.")
            return []

        context = context or ChapterContext()
        # Run-wide inputs: set once via chainable setters (they never change across iterations).
        context.set_draft(draft).set_chapter_plans(chapter_plans).set_characters(characters).set_guidance(guidance)

        for i, cp in enumerate(chapter_plans):
            logger.debug(f"Generating chapter {i + 1}/{len(chapter_plans)}: {cp.formatted_chapter_title}")

            # 1. Hook: subclass builds the prompt context AND renders the final prompt.
            #    chapter_index() == i here (the content tuple is appended last).
            rendered = await self.prepare_chapter_prompt(context)
            # 2. Generate chapter content
            raw_chapter = ok(await self.aask(rendered, send_to=send_to, **kwargs))

            logger.info(f"Chapter {i + 1}/{len(chapter_plans)} generated ({len(raw_chapter)} chars)")

            # 3. Summarize chapter into the channel history
            summary = await self.summarize_chapter(
                cp.formatted_chapter_title, raw_chapter, draft.language, context.previous_summary(), **kwargs
            )
            if summary:
                context.add_summary(i, summary)
                logger.debug(
                    f"Chapter {i + 1} summarized: {len(summary.key_events)} events, "
                    f"{len(summary.unresolved_threads)} open threads, "
                    f"{len(summary.numerical_stat)} numerical stats"
                )
                # 3b. Hook: allow subclass to react to each chapter summary
                await self.after_chapter_summarize(context)

            # 4. Record the content LAST: chapter_index() is len(chapter_contents),
            #    so recording at iteration end keeps the position at chapter i
            #    for the whole iteration (both hooks see the same current chapter).
            context.add_content(i, raw_chapter)

        logger.info(f"Generated {len(context.chapter_contents)} chapter content(s) sequentially")
        return context.contents()

    # ── Chapter pipeline hooks (override in subclasses) ──

    async def prepare_chapter_prompt(self, ctx: ChapterContext) -> str:
        """Hook: build and render the chapter prompt.

        Sealed inside the hook by design — the base loop hands it the run's
        inputs plus full history via the ``ctx`` channel (all chapter plans,
        all summaries and contents so far, current position) and takes back
        only the final prompt string. The default builds the base vars via
        :meth:`_chapter_prompt_vars`, merges the :meth:`extra_chapter_prompt_vars`
        contributions, and renders ``novel_config.chapter_requirement_template``.

        Subclasses override to swap the template, inject extra fields, mutate
        caller-owned inputs, or call external services before render — and
        SHOULD delegate to ``await super().prepare_chapter_prompt(ctx)`` so
        sibling mixins still contribute through the same seam.

        Args:
            ctx: The sealed per-chapter context (inputs set by the loop).
        """
        prompt_vars = self._chapter_prompt_vars(ctx)
        prompt_vars.update(self.extra_chapter_prompt_vars(ctx))
        return TEMPLATE_MANAGER.render_template(
            novel_config.chapter_requirement_template,
            prompt_vars,
        )

    def extra_chapter_prompt_vars(self, ctx: ChapterContext) -> Dict[str, Any]:
        """Hook: contribute extra template vars for the chapter requirement prompt.

        No-op default. Mixins override to add feature-specific context
        (mental states, writing style docs, …) to the rendered chapter prompt
        without re-implementing the render — the default
        :meth:`prepare_chapter_prompt` merges the returned dict into
        :meth:`_chapter_prompt_vars` before rendering. Called once per chapter
        with the same ``ctx`` channel as the prompt hook.

        Args:
            ctx: The sealed per-chapter context (inputs set by the loop).
        """
        return {}

    def _chapter_prompt_vars(self, ctx: ChapterContext) -> dict:
        """Build the base template variables for the chapter requirement.

        Internal helper: the default :meth:`prepare_chapter_prompt` renders
        with these vars; subclasses reuse it when they need the base fields
        plus their own additions.
        """
        if ctx.draft is None or ctx.chapter_plans is None or ctx.characters is None:
            raise RuntimeError("ChapterContext inputs must be populated by create_chapters before hooks fire")
        plan = ctx.chapter_plan()
        if plan is None:
            raise RuntimeError("ChapterContext inputs must be populated by create_chapters before hooks fire")
        previous_summary = ctx.previous_summary()
        return {
            "script": plan.script.as_prompt(),
            "characters": dump_card(*ctx.characters),
            "language": ctx.draft.language,
            "global_writing_constraint": ctx.draft.global_writing_constraint,
            "guidance": ctx.guidance,
            "writing_constrain": plan.draft.writing_constrain,
            "expected_word_count": plan.expected_word_count,
            "chapter_title": plan.formatted_chapter_title,
            "novel_title": ctx.draft.title,
            "novel_synopsis": ctx.draft.synopsis,
            "all_chapters_titles": ctx.draft.all_chapters_titles,
            "previous_summary": previous_summary.as_prompt() if previous_summary else None,
            "previous_chapter_tail": ctx.previous_chapter_tail(),
        }

    async def after_chapter_summarize(self, ctx: ChapterContext) -> None:
        """React to each chapter summary after it is generated.

        Default no-op. The just-generated summary is already appended to the
        channel as :attr:`ChapterContext.current_summary` when this fires.
        Subclasses override to evolve per-run state carried in ``ctx`` (mutate
        the caller-owned channel in place — the capability itself stays
        stateless).
        """
        pass

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
            send_to: The model group to use to get the summerization
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
        characters: List[CharacterCard],
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
