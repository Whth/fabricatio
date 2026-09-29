"""The plain staged novel pipeline: one action per ``compose_novel`` segment.

Every stage here mixes one composition capability into :class:`~fabricatio_novel.actions.stage.StageAction`
and wraps the chain segments that capability owns; the pipeline's specializations live in
:mod:`fabricatio_novel.actions.rag` (retrieval phases) and
:mod:`fabricatio_novel.actions.illustration` (scenes drawn before the export).
"""

from pathlib import Path
from typing import Any, ClassVar

from fabricatio_core import logger
from fabricatio_core.models.action import OUTPUT_KEY, Action
from fabricatio_core.rust import PLAN, TASK
from fabricatio_core.utils import ok

from fabricatio_novel.actions.stage import StageAction, StageName
from fabricatio_novel.capabilities.bible import BibleCompose
from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import ExportFormat, Novel
from fabricatio_novel.models.series_book import SeriesBible
from fabricatio_novel.models.story import Story

__all__ = [
    "AssembleNovelStage",
    "ComposeScenesStage",
    "DumpNovelStage",
    "InitNovelContext",
    "PlanChaptersStage",
    "PlanScenesStage",
    "PlanStoriesStage",
    "PrepareCharacterSpanStage",
    "ProposeNovelMetadataStage",
    "ProposeSettingBibleStage",
]


class InitNovelContext(StageAction, NovelCompose):
    """Build the novel context from the task init context, fire ``before_compose_novel_context``, persist."""

    output_key: str = "novel_ctx"
    stage: ClassVar[StageName] = "01_init"

    async def init_novel_context(
        self,
        outline: str,
        *,
        language: str | None = None,
        bible_path: Path | None = None,
        skills: list[str] | None = None,
        send_to: str | None = TASK,
    ) -> NovelContext:
        """Build the root from the run's settings and fire the before hook on it.

        The user's skills are resolved by name onto the root before the hook runs,
        so the hook — and every stage after it — sees a complete root; the hook's
        return replaces it, which is where a RAG run seals the context class
        itself and fetches the references the planning prompts render.
        """
        ctx = NovelContext.create(outline, language=language)
        if bible_path is not None:
            ctx.set_series_bible(SeriesBible.model_validate_json(bible_path.read_text(encoding="utf-8")))
        if skills:
            ctx = self.apply_skills(ctx, skills)
        ctx.seed_bible_prefix()
        return await self.before_compose_novel_context(ctx, send_to=send_to)

    async def _execute(
        self,
        *_: Any,
        novel_outline: str,
        novel_language: str | None = None,
        bible_path: Path | None = None,
        skills: list[str] | None = None,
        send_to: str | None = TASK,
        **cxt: Any,
    ) -> NovelContext:
        if self.held(cxt):
            return ok(cxt.get("novel_ctx"), "a resumed run continues from the state it carries in `novel_ctx`")
        ctx = await self.init_novel_context(
            ok(novel_outline, "`novel_outline` is required in the task init context"),
            language=novel_language,
            bible_path=bible_path,
            skills=skills,
            send_to=send_to,
        )
        await self.snapshot(ctx, cxt)
        return ctx


class ProposeNovelMetadataStage(StageAction, NovelCompose):
    """Propose the novel metadata plan and adopt it onto the context.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so the structured proposal follows the plan model
    unless the run routes it elsewhere.
    """

    output_key: str = "metadata_ok"
    stage: ClassVar[StageName] = "02_metadata"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        planned = await self.propose_novel_metadata(novel_ctx, send_to=send_to)
        await self.snapshot(novel_ctx, cxt)
        return planned


class ProposeSettingBibleStage(StageAction, BibleCompose):
    """Propose the setting bible from the outline; skipped when the context already holds one.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so the structured proposal follows the plan model
    unless the run routes it elsewhere.
    """

    output_key: str = "bible_ok"
    stage: ClassVar[StageName] = "03_bible"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        bible = novel_ctx.series_bible
        if bible is not None and not bible.is_empty():
            logger.debug("Setting bible already present; skipping proposal")
            await self.snapshot(novel_ctx, cxt)
            return True
        proposed = await self.compose_setting_bible(
            novel_ctx.outline,
            novel_ctx.language,
            novel_ctx.skill_section(),
            send_to=send_to,
        )
        if proposed is None:
            logger.error("Setting bible proposal failed; aborting novel generation")
            await self.snapshot(novel_ctx, cxt)
            return False
        novel_ctx.set_series_bible(proposed).seed_bible_prefix()
        logger.info("Proposed the setting bible from the outline")
        await self.snapshot(novel_ctx, cxt)
        return True


class PrepareCharacterSpanStage(StageAction, NovelCompose):
    """Propose the novel roster character spans from the bible; skipped when the bible is empty.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so the structured proposal follows the plan model
    unless the run routes it elsewhere.
    """

    output_key: str = "characters_ok"
    stage: ClassVar[StageName] = "04_characters"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        await self.prepare_character_span(novel_ctx, send_to=send_to)
        await self.snapshot(novel_ctx, cxt)
        return True


class PlanChaptersStage(StageAction, NovelCompose):
    """Plan chapters and draft per-chapter character spans.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so planning follows the plan model unless the run routes
    it elsewhere.
    """

    output_key: str = "chapter_plan_ok"
    stage: ClassVar[StageName] = "05_chapter_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        planned = await self.plan_chapters_phase(novel_ctx, send_to=send_to)
        await self.snapshot(novel_ctx, cxt)
        return planned


class PlanStoriesStage(StageAction, ChapterCompose):
    """Fire ``before_compose_chapter_context`` per chapter, then plan its stories and draft their spans.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so planning follows the plan model unless the run routes
    it elsewhere.
    """

    output_key: str = "story_plan_ok"
    stage: ClassVar[StageName] = "06_story_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        for chapter in novel_ctx.iter_prefixed_contexts():
            chapter_ctx = await self.before_compose_chapter_context(chapter, send_to=send_to)
            if not await self.plan_stories_phase(chapter_ctx, send_to=send_to):
                await self.snapshot(novel_ctx, cxt)
                return False
        await self.snapshot(novel_ctx, cxt)
        return True


class PlanScenesStage(StageAction, StoryCompose):
    """Fire ``before_compose_story_context`` per story, then plan its scenes.

    Calls ride the run's ``send_to`` group when the context names one and fall back to the
    ``PLAN`` agent variant otherwise, so planning follows the plan model unless the run routes
    it elsewhere.
    """

    output_key: str = "scene_plan_ok"
    stage: ClassVar[StageName] = "07_scene_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = PLAN, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        for chapter in novel_ctx.iter_prefixed_contexts():
            for story in chapter.iter_prefixed_contexts():
                story_ctx = await self.before_compose_story_context(story, send_to=send_to)
                if not await self.plan_scenes_phase(story_ctx, send_to=send_to):
                    await self.snapshot(novel_ctx, cxt)
                    return False
        await self.snapshot(novel_ctx, cxt)
        return True


class ComposeScenesStage(StageAction, ChapterCompose):
    """Write every scene serially in prefix order, then close each story and chapter out.

    Mirrors the chain tail per unit: after a story's scenes are composed, its
    after-context hook fires and the story is assembled and handed to
    ``post_process_story``; once a chapter's stories are done, its after-context
    hook fires and the chapter is assembled and handed to
    ``post_process_chapter``. A ``None`` post-process return fails the stage,
    exactly like the chain's compose loops do.
    """

    output_key: str = "scenes_ok"
    stage: ClassVar[StageName] = "08_scenes"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = TASK, **cxt: Any) -> bool:
        if self.held(cxt):
            return True
        for chapter in novel_ctx.iter_prefixed_contexts():
            for story in chapter.iter_prefixed_contexts():
                await self.prepare_scene_write(story, send_to=send_to)
                if not await self.compose_scenes_phase(story, send_to=send_to):
                    await self.snapshot(novel_ctx, cxt)
                    return False
                story_ctx = await self.after_compose_story_context(story, send_to=send_to)
                story_artifact = Story.from_context(story_ctx)
                logger.info(
                    f"Story '{story_artifact.title}' composed ({len(story_artifact.scenes)} scene(s),"
                    f"  word count satisfaction: {story_artifact.satisfy_ratio()}",
                )
                if await self.post_process_story(story_ctx, story_artifact) is None:
                    await self.snapshot(novel_ctx, cxt)
                    return False
            chapter_ctx = await self.after_compose_chapter_context(chapter, send_to=send_to)
            chapter_artifact = Chapter.from_context(chapter_ctx)
            logger.info(
                f"Chapter '{chapter_artifact.title}' composed ({len(chapter_artifact.story)} story(s),"
                f"  word count satisfaction: {chapter_artifact.satisfy_ratio()}",
            )
            if await self.post_process_chapter(chapter_ctx, chapter_artifact) is None:
                await self.snapshot(novel_ctx, cxt)
                return False
        await self.snapshot(novel_ctx, cxt)
        return True


class AssembleNovelStage(StageAction, NovelCompose):
    """Fire ``after_compose_novel_context``, then materialize the composed context tree as a Novel."""

    output_key: str = "novel"
    stage: ClassVar[StageName] = "09_novel"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, send_to: str | None = TASK, **cxt: Any) -> Novel:
        ctx = await self.after_compose_novel_context(novel_ctx, send_to=send_to)
        novel = self.assemble_novel(ctx)
        await self.snapshot(ctx, cxt)
        return novel


class DumpNovelStage(Action, NovelCompose):
    """Fire ``post_process_novel``, then export the novel to JSON plus EPUB and/or per-chapter texts.

    The task init context is unpacked straight into the parameters below — each knob is
    declared once, with its default — and the hook is called with exactly what the novel
    capability declares, ``(ctx, novel)``. A pipeline whose chain declares more brings its
    own dump action (:class:`fabricatio_novel.actions.illustration.IllustrateNovelStage`)
    instead of smuggling keywords here.
    """

    output_key: str = OUTPUT_KEY

    async def _execute(
        self,
        novel_ctx: NovelContext,
        novel: Novel,
        *,
        persist_dir: Path,
        export_format: ExportFormat = ExportFormat.EPUB,
        output_path: str | None = None,
        font: str | Path | None = None,
        cover: str | Path | None = None,
        **_: Any,
    ) -> Path:
        """Fire the post-process hook this chain resolves, then export the JSON snapshot and the artifacts."""
        novel = await self.post_process_novel(novel_ctx, novel)
        return self.export(
            novel, persist_dir, export_format=export_format, output_path=output_path, font=font, cover=cover
        )

    def export(
        self,
        novel: Novel,
        persist_dir: Path,
        *,
        export_format: ExportFormat = ExportFormat.EPUB,
        output_path: str | None = None,
        font: str | Path | None = None,
        cover: str | Path | None = None,
    ) -> Path:
        """Persist the novel and write the artifacts the run selected, returning the exported path."""
        persist_dir.mkdir(parents=True, exist_ok=True)
        epub_path = persist_dir / output_path if output_path else persist_dir / "novel.epub"
        texts_dir = persist_dir / "chapters"
        novel.persist(persist_dir)
        match export_format:
            case ExportFormat.TXT:
                novel.dump_texts(texts_dir)
                logger.info(f"Chapter texts dumped to {texts_dir}")
                return texts_dir
            case ExportFormat.EPUB:
                novel.dump_epub(epub_path, font=font, cover=cover)
                logger.info(f"EPUB dumped to {epub_path}")
                return epub_path
            case ExportFormat.BOTH:
                novel.dump_epub(epub_path, font=font, cover=cover)
                logger.info(f"EPUB dumped to {epub_path}")
                novel.dump_texts(texts_dir)
                logger.info(f"Chapter texts dumped to {texts_dir}")
                return epub_path
